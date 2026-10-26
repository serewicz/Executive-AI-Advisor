"""Expose Executive AI Advisor capabilities to MCP clients.

The MCP server is a thin adapter over the existing service layer. Every tool
delegates to the same functions the FastAPI routes call, so retrieval,
citation, scoring, and LLM-provider behavior stay identical across the REST
API, the Streamlit UI, and MCP clients such as Claude Desktop or Cursor.

Provider API keys are never accepted as tool arguments. Configure providers
through environment variables (see ``.env.example``) so keys stay out of
model context and client logs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Annotated, Any, TypeVar
from uuid import UUID

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.advisor import service as advisor_service
from app.advisor.providers.base import LLMError
from app.advisor.schemas import (
    AdvisorAskResponse,
    BoardSummaryResponse,
    LLMProviderName,
    SummaryType,
)
from app.api.routes.document_sets import _document_set_detail, list_document_sets
from app.compliance import cra_service
from app.compliance.cra_schemas import CRAReadinessResponse
from app.core.config import settings
from app.diligence import service as diligence_service
from app.diligence.schemas import TechnologyDiligenceReport
from app.executive import service as executive_service
from app.executive.schemas import (
    AIGovernanceAssessmentResponse,
    AIReplicabilityRiskAssessmentResponse,
    BoardBriefResponse,
    TechnologyRiskScorecardResponse,
)
from app.governance import ai_knowledge_service
from app.governance.ai_knowledge_schemas import AIKnowledgeGovernanceResponse
from app.models.document import DocumentSet
from app.planning.schemas import HundredDayPlanResponse, PlanType
from app.retrieval import vector_search
from app.schemas.document_set import DocumentSetListResponse

SessionFactory = Callable[[], Session]
T = TypeVar("T")

SERVER_INSTRUCTIONS = """\
Executive AI Advisor turns technical evidence into cited, board-ready decisions.

Typical workflow:
1. Call `list_investigations` (or read `eaia://investigations`) to find a document_set_id.
2. Use `search_evidence` or `ask_advisor` to explore the evidence with citations.
3. Produce deliverables: `technology_risk_scorecard`, `board_brief`,
   `hundred_day_plan`, `technology_due_diligence_report`, or a specialized
   assessment (AI governance, AI replicability, AI knowledge governance, CRA readiness).

Every output carries citations, confidence, and limitations. Present them to the
user rather than overstating certainty. Outputs support human judgment and are
not legal advice.
"""

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
# LLM-backed tools may call an external model provider, so they are not closed-world.
READ_ONLY_LLM = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True)

DocumentSetId = Annotated[UUID, Field(description="Investigation (document set) ID from list_investigations.")]
TopK = Annotated[int, Field(ge=1, le=50, description="Number of evidence chunks to retrieve per query.")]
Provider = Annotated[
    LLMProviderName | None,
    Field(description="LLM provider override (mock, openai, anthropic, grok). Defaults to LLM_PROVIDER."),
]
Model = Annotated[str | None, Field(max_length=120, description="Optional model name override for the provider.")]

_EXPECTED_ERRORS: tuple[type[Exception], ...] = (
    advisor_service.AdvisorDocumentNotFoundError,
    advisor_service.AdvisorValidationError,
    diligence_service.DiligenceDocumentSetNotFoundError,
    diligence_service.DiligenceValidationError,
    cra_service.CRADocumentSetNotFoundError,
    ai_knowledge_service.AIKnowledgeGovernanceDocumentSetNotFoundError,
    LLMError,
    ValueError,
    RuntimeError,
)


class EvidenceHit(BaseModel):
    document_id: UUID
    document_title: str
    chunk_id: UUID
    page_start: int
    page_end: int
    similarity_score: float
    source_type: str
    classification: str
    content: str


class EvidenceSearchResult(BaseModel):
    query: str
    results: list[EvidenceHit]


def create_server(session_factory: SessionFactory | None = None) -> MCPServer:
    """Build the Executive AI Advisor MCP server.

    ``session_factory`` returns a SQLAlchemy session; it defaults to the app's
    configured ``SessionLocal`` and is injectable for tests.
    """
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    @contextmanager
    def db_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def run(operation: Callable[[Session], T]) -> T:
        with db_session() as db:
            try:
                return operation(db)
            except _EXPECTED_ERRORS as exc:
                raise ToolError(str(exc)) from exc

    mcp = MCPServer(
        name="executive-ai-advisor",
        title=settings.app_name,
        instructions=SERVER_INSTRUCTIONS,
        website_url="https://github.com/serewicz/Executive-AI-Advisor",
    )

    # ------------------------------------------------------------------ tools

    @mcp.tool(title="List investigations", annotations=READ_ONLY)
    def list_investigations() -> DocumentSetListResponse:
        """List investigation workspaces (document sets) with their document counts."""
        return run(list_document_sets)

    @mcp.tool(title="Search evidence", annotations=READ_ONLY)
    def search_evidence(
        query: Annotated[str, Field(min_length=1, max_length=settings.max_search_query_chars)],
        document_set_id: Annotated[UUID | None, Field(description="Limit search to one investigation.")] = None,
        document_id: Annotated[UUID | None, Field(description="Limit search to one document.")] = None,
        top_k: TopK = 5,
    ) -> EvidenceSearchResult:
        """Semantic search over ingested evidence. Returns cited source excerpts without calling an LLM."""

        def _search(db: Session) -> EvidenceSearchResult:
            hits = vector_search.search_similar_chunks(
                query=query, db=db, top_k=top_k, document_id=document_id, document_set_id=document_set_id
            )
            return EvidenceSearchResult(
                query=query,
                results=[
                    EvidenceHit(
                        document_id=hit.document_id,
                        document_title=hit.document_title,
                        chunk_id=hit.chunk_id,
                        page_start=hit.page_start,
                        page_end=hit.page_end,
                        similarity_score=hit.similarity_score,
                        source_type=hit.source_type,
                        classification=hit.classification,
                        content=hit.content,
                    )
                    for hit in hits
                ],
            )

        return run(_search)

    @mcp.tool(title="Ask the advisor", annotations=READ_ONLY_LLM)
    def ask_advisor(
        question: Annotated[str, Field(min_length=3, max_length=2000)],
        document_set_id: Annotated[UUID | None, Field(description="Answer from one investigation.")] = None,
        document_id: Annotated[UUID | None, Field(description="Answer from one document.")] = None,
        top_k: TopK = 5,
        llm_provider: Provider = None,
        llm_model: Model = None,
    ) -> AdvisorAskResponse:
        """Answer an executive question with cited evidence, confidence, and stated limitations."""
        return run(
            lambda db: advisor_service.answer_executive_question(
                question=question,
                db=db,
                top_k=top_k,
                document_id=document_id,
                document_set_id=document_set_id,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        )

    @mcp.tool(title="Board summary", annotations=READ_ONLY_LLM)
    def board_summary(
        summary_type: SummaryType = "board_brief",
        document_set_id: Annotated[UUID | None, Field(description="Summarize one investigation.")] = None,
        document_id: Annotated[UUID | None, Field(description="Summarize one document.")] = None,
        top_k: TopK = 8,
        llm_provider: Provider = None,
        llm_model: Model = None,
    ) -> BoardSummaryResponse:
        """Generate a cited board memo for a document or investigation."""
        return run(
            lambda db: advisor_service.generate_board_summary(
                document_id=document_id,
                document_set_id=document_set_id,
                summary_type=summary_type,
                top_k=top_k,
                db=db,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        )

    def _register_assessment(
        name: str, title: str, func: Callable[..., Any], response_model: type[BaseModel], doc: str
    ) -> None:
        def tool(
            document_set_id: DocumentSetId,
            top_k: TopK = 20,
            llm_provider: Provider = None,
            llm_model: Model = None,
        ):
            return run(
                lambda db: func(
                    document_set_id=document_set_id,
                    db=db,
                    top_k=top_k,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
            )

        tool.__name__ = name
        tool.__annotations__["return"] = response_model
        tool.__doc__ = doc
        mcp.tool(name=name, title=title, description=doc, annotations=READ_ONLY_LLM)(tool)

    _register_assessment(
        "technology_risk_scorecard",
        "Technology risk scorecard",
        executive_service.generate_risk_scorecard,
        TechnologyRiskScorecardResponse,
        "Rate architecture, security, AI governance, cloud cost, delivery, technical debt, and key-person "
        "risk (red/yellow/green) with business impact, owners, timelines, and citations.",
    )
    _register_assessment(
        "board_brief",
        "Board brief",
        executive_service.generate_board_brief,
        BoardBriefResponse,
        "Produce a board brief: executive summary, top five technology risks, board actions, key decisions, "
        "and questions for management, each tied to evidence.",
    )
    _register_assessment(
        "ai_governance_assessment",
        "AI governance assessment",
        executive_service.generate_ai_governance_assessment,
        AIGovernanceAssessmentResponse,
        "Assess AI governance maturity across use cases, data, evaluation, human review, cost, vendors, and auditability.",
    )
    _register_assessment(
        "ai_replicability_risk_assessment",
        "AI replicability risk assessment",
        executive_service.generate_ai_replicability_risk_assessment,
        AIReplicabilityRiskAssessmentResponse,
        "Evaluate whether AI capabilities are a durable advantage or easily replicated by competitors.",
    )
    _register_assessment(
        "ai_knowledge_governance_assessment",
        "AI knowledge governance assessment",
        ai_knowledge_service.generate_ai_knowledge_governance_assessment,
        AIKnowledgeGovernanceResponse,
        "Assess governance of the knowledge and data assets that AI systems depend on.",
    )
    _register_assessment(
        "cra_readiness_assessment",
        "EU Cyber Resilience Act readiness",
        cra_service.generate_cra_readiness_assessment,
        CRAReadinessResponse,
        "EU Cyber Resilience Act readiness review with findings, missing evidence, and a 90-day plan. Not legal advice.",
    )

    @mcp.tool(title="Technology due diligence report", annotations=READ_ONLY_LLM)
    def technology_due_diligence_report(
        document_set_id: DocumentSetId,
        top_k: TopK = 20,
        include_100_day_plan: bool = True,
        llm_provider: Provider = None,
        llm_model: Model = None,
    ) -> TechnologyDiligenceReport:
        """Full technology due diligence report with findings, risk heatmap, and optional 100-day plan."""
        return run(
            lambda db: diligence_service.generate_technology_due_diligence_report(
                document_set_id=document_set_id,
                db=db,
                top_k=top_k,
                include_100_day_plan=include_100_day_plan,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        )

    @mcp.tool(title="100-day technology plan", annotations=READ_ONLY_LLM)
    def hundred_day_plan(
        document_set_id: DocumentSetId,
        plan_type: PlanType = "growth_equity",
        llm_provider: Provider = None,
        llm_model: Model = None,
    ) -> HundredDayPlanResponse:
        """Sequenced 30/60/90-day plan with owners, outcomes, dependencies, and board checkpoints."""
        return run(
            lambda db: executive_service.generate_executive_100_day_plan(
                document_set_id=document_set_id,
                plan_type=plan_type,
                db=db,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        )

    # -------------------------------------------------------------- resources

    @mcp.resource("eaia://investigations", name="investigations", mime_type="application/json")
    def investigations_resource() -> str:
        """All investigation workspaces with document counts."""
        with db_session() as db:
            return list_document_sets(db).model_dump_json(indent=2)

    @mcp.resource("eaia://investigations/{document_set_id}", name="investigation", mime_type="application/json")
    def investigation_resource(document_set_id: str) -> str:
        """One investigation workspace and its documents."""
        with db_session() as db:
            try:
                document_set = db.get(DocumentSet, UUID(document_set_id))
            except ValueError as exc:
                raise ResourceNotFoundError(f"Invalid investigation id: {document_set_id}") from exc
            if document_set is None:
                raise ResourceNotFoundError(f"Investigation not found: {document_set_id}")
            return _document_set_detail(document_set, db).model_dump_json(indent=2)

    # ---------------------------------------------------------------- prompts

    @mcp.prompt(title="Prepare for a board meeting")
    def board_meeting_prep(document_set_id: str, meeting_focus: str = "technology risk") -> str:
        """Guide the assistant through building a board pre-read from one investigation."""
        return (
            f"Prepare a board pre-read on {meeting_focus} for investigation {document_set_id}.\n"
            "1. Call technology_risk_scorecard and board_brief for this investigation.\n"
            "2. Lead with the decisions the board must make, then the top risks and their business impact.\n"
            "3. Cite evidence for every claim and state confidence and limitations plainly.\n"
            "4. End with the questions directors should ask management."
        )

    @mcp.prompt(title="Technology due diligence review")
    def diligence_review(document_set_id: str, deal_type: PlanType = "growth_equity") -> str:
        """Guide the assistant through an investor-grade technology diligence review."""
        return (
            f"Run a technology due diligence review for investigation {document_set_id} ({deal_type}).\n"
            "1. Call technology_due_diligence_report, then hundred_day_plan with the same plan type.\n"
            "2. Separate findings supported by evidence from gaps that need management interviews.\n"
            "3. Summarize deal-relevant risks, value-creation levers, and the first 30 days of action."
        )

    return mcp

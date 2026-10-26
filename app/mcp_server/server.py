"""Expose Executive AI Advisor capabilities to MCP clients.

The MCP server is a thin adapter over the existing service layer. Every tool
delegates to the same functions the FastAPI routes call, so retrieval,
citation, scoring, and LLM-provider behavior stay identical across the REST
API, the Streamlit UI, and MCP clients such as Claude Desktop or Cursor.

Provider API keys are never accepted as tool arguments. Configure providers
through environment variables (see ``.env.example``) so keys stay out of
model context and client logs.

Every call goes through ``CallGuard``, which applies the rate limit and model
allowlist, converts exceptions to client-safe messages, and writes one audit
record. See docs/adr/0001-mcp-hardening-and-audit-log.md.
"""

from __future__ import annotations

import getpass
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Annotated, Any, Literal, TypeVar
from uuid import UUID, uuid4

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.types import CallToolResult, TextContent, ToolAnnotations
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
from app.compliance import cra_service
from app.compliance.cra_schemas import CRAReadinessResponse
from app.core.config import Settings, settings
from app.core.errors import AuditUnavailable, Denied, Internal, InvalidInput, NotFound, ProviderUnavailable, PublicError, RateLimited
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
from app.ingestion.embeddings.base import EmbeddingError
from app.mcp_server.audit import (
    AuditRecord,
    AuditSink,
    AuditWriteError,
    DatabaseAuditSink,
    FallbackAuditFile,
    LoggingAuditSink,
    redact_arguments,
)
from app.mcp_server.model_policy import ModelPolicy, load_model_policy
from app.mcp_server.rate_limit import LimitPolicy, RateLimiter
from app.planning.schemas import HundredDayPlanResponse, PlanType
from app.retrieval import vector_search
from app.schemas.document_set import DocumentSetListResponse
from app.services import document_sets as document_set_service

SessionFactory = Callable[[], Session]
T = TypeVar("T")
Transport = Literal["stdio", "http"]

logger = logging.getLogger("eaia.mcp")

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
    Field(description="LLM provider override (mock, openai, anthropic, grok, local). Defaults to LLM_PROVIDER."),
]
Model = Annotated[str | None, Field(max_length=120, description="Optional model name override for the provider.")]
AcceptUnaudited = Annotated[
    bool,
    Field(
        description=(
            "Leave false. Set true only after a call was blocked because it could not be audited and the user "
            "still wants the answer. The answer is then returned marked UNAUDITED."
        )
    ),
]

# Domain errors whose messages are string literals in this codebase. Their text
# is safe to return. tests/test_mcp_hardening.py enforces the literal rule.
_NOT_FOUND_ERRORS: tuple[type[Exception], ...] = (
    advisor_service.AdvisorDocumentNotFoundError,
    diligence_service.DiligenceDocumentNotFoundError,
    diligence_service.DiligenceDocumentSetNotFoundError,
    cra_service.CRADocumentSetNotFoundError,
    ai_knowledge_service.AIKnowledgeGovernanceDocumentSetNotFoundError,
)
_VALIDATION_ERRORS: tuple[type[Exception], ...] = (
    advisor_service.AdvisorValidationError,
    diligence_service.DiligenceValidationError,
    cra_service.CRAValidationError,
    ai_knowledge_service.AIKnowledgeGovernanceValidationError,
)
# Errors that can carry upstream text (provider responses, driver messages).
_PROVIDER_ERRORS: tuple[type[Exception], ...] = (LLMError, EmbeddingError)

READ_POLICY = "read"
LLM_POLICY = "llm"


def to_public_error(exc: Exception, correlation_id: UUID) -> PublicError:
    """Map any exception to a client-safe error. Unknown exceptions never expose their text."""
    if isinstance(exc, PublicError):
        exc.correlation_id = exc.correlation_id or correlation_id
        return exc
    if isinstance(exc, _NOT_FOUND_ERRORS):
        return NotFound(str(exc))
    if isinstance(exc, _VALIDATION_ERRORS):
        return InvalidInput(str(exc))
    if isinstance(exc, _PROVIDER_ERRORS):
        return ProviderUnavailable("The model provider request failed.", correlation_id)
    return Internal("Internal error.", correlation_id)


def default_model_for(provider: str, config: Settings) -> str:
    return {
        "mock": "mock",
        "openai": config.openai_chat_model,
        "anthropic": config.anthropic_chat_model,
        "grok": config.xai_chat_model,
        "local": config.local_llm_model,
    }.get(provider, "")


class CallGuard:
    """Applies rate limits and the model allowlist, maps errors, and audits every call."""

    def __init__(
        self,
        *,
        transport: Transport,
        audit_sink: AuditSink,
        rate_limiter: RateLimiter,
        model_policy: ModelPolicy,
        config: Settings,
        fallback: FallbackAuditFile | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.fallback = fallback
        self.transport = transport
        self.audit_sink = audit_sink
        self.rate_limiter = rate_limiter
        self.model_policy = model_policy
        self.config = config
        self._clock = clock

    def client_id(self) -> str:
        token = get_access_token()
        if token is not None:
            return token.client_id
        if self.transport == "stdio":
            return f"stdio:{getpass.getuser()}"
        return "http:unauthenticated-local"

    def call(
        self,
        *,
        kind: str,
        name: str,
        arguments: dict[str, Any],
        operation: Callable[[], T],
        policy: str,
        uses_model: bool = False,
    ) -> T | CallToolResult:
        arguments = dict(arguments)
        accept_unaudited = bool(arguments.pop("accept_unaudited", False))
        correlation_id = uuid4()
        client_id = self.client_id()
        started = self._clock()
        record = AuditRecord(
            correlation_id=correlation_id,
            client_id=client_id,
            transport=self.transport,
            kind=kind,
            name=name,
            arguments=redact_arguments(arguments, self.config.mcp_audit_store_text),
            document_set_id=arguments.get("document_set_id"),
        )
        if accept_unaudited:
            record.detail = "accept_unaudited requested"
        failure: PublicError | None = None
        result: Any = None
        try:
            decision = self.rate_limiter.check(client_id, policy)
            if not decision.allowed:
                record.outcome = "rate_limited"
                raise RateLimited(decision.retry_after_seconds)
            if uses_model:
                provider = (arguments.get("llm_provider") or self.config.llm_provider or "mock").lower().strip()
                model = arguments.get("llm_model") or default_model_for(provider, self.config)
                record.provider, record.model = provider, model
                if not self.model_policy.is_allowed(provider, model):
                    record.outcome = "denied"
                    raise Denied("Model not allowed for this provider.")
            result = operation()
        except Exception as exc:  # noqa: BLE001 - every failure is mapped and audited
            failure = to_public_error(exc, correlation_id)
            if record.outcome == "ok":
                record.outcome = "error"
            record.error_class = type(exc).__name__
            if isinstance(failure, (Internal, ProviderUnavailable)):
                logger.exception("MCP %s %s failed. correlation_id=%s", kind, name, correlation_id)

        record.duration_ms = int((self._clock() - started) * 1000)
        try:
            self.audit_sink.write(record)
        except AuditWriteError as exc:
            return self._unaudited(record, failure, result, accept_unaudited, exc)

        if failure is not None:
            raise ToolError(failure.client_text()) from None
        return result

    def _unaudited(
        self,
        record: AuditRecord,
        failure: PublicError | None,
        result: Any,
        accept_unaudited: bool,
        exc: AuditWriteError,
    ) -> Any:
        """Fail closed. Return a result only on an explicit, permitted, durably recorded override."""
        db_error_class = type(exc.__cause__).__name__ if exc.__cause__ else None
        override_allowed = (
            accept_unaudited and record.kind == "tool" and self.config.mcp_audit_allow_unaudited_override
        )
        if not override_allowed:
            # Best effort: leave a trace of the refusal. The call is refused either way.
            self._append_fallback("audit_refused", record, db_error_class)
            raise ToolError(self._refusal_text(record)) from None

        record.detail = "accept_unaudited override; result returned without a database audit record"
        if not self._append_fallback("unaudited_override", record, db_error_class):
            # Nowhere durable to record the override, so the answer is withheld.
            raise ToolError(
                AuditUnavailable(
                    "The call was blocked. The audit log and the fallback audit file are both unavailable, "
                    "so an override cannot be recorded.",
                    record.correlation_id,
                ).client_text()
            ) from None
        logger.warning(
            "Unaudited override accepted. correlation_id=%s client_id=%s name=%s",
            record.correlation_id,
            record.client_id,
            record.name,
        )
        if failure is not None:
            raise ToolError(f"{failure.client_text()} {UNAUDITED_NOTICE}") from None
        return unaudited_result(result, record.correlation_id)

    def _refusal_text(self, record: AuditRecord) -> str:
        message = "The call was blocked because it could not be written to the audit log."
        if record.kind == "tool" and self.config.mcp_audit_allow_unaudited_override:
            message += (
                " If you still want the answer, call the tool again with the same arguments and "
                "accept_unaudited=true. The server will try the audit log again, record the override "
                "in its fallback audit file, and mark the answer as unaudited."
            )
        elif record.kind == "tool":
            message += " Overrides are disabled on this server. Try again later or contact the operator."
        else:
            message += f" A {record.kind} cannot be overridden. Try again later or contact the operator."
        return AuditUnavailable(message, record.correlation_id).client_text()

    def _append_fallback(self, event: str, record: AuditRecord, db_error_class: str | None) -> bool:
        if self.fallback is None:
            return False
        try:
            self.fallback.append(event, record, db_error_class)
        except Exception:  # noqa: BLE001 - reported to the caller as "no durable record"
            logger.exception("Fallback audit write failed. correlation_id=%s", record.correlation_id)
            return False
        return True


UNAUDITED_NOTICE = "UNAUDITED: this response has no audit log record. The override was recorded in the fallback audit file."


def unaudited_result(result: Any, correlation_id: UUID) -> CallToolResult:
    """Wrap a tool result so the client sees, in text and in _meta, that it was not audited."""
    if isinstance(result, BaseModel):
        structured = result.model_dump(mode="json", by_alias=True)
        body = result.model_dump_json(indent=2, by_alias=True)
    else:
        structured = None
        body = str(result)
    return CallToolResult(
        content=[
            TextContent(type="text", text=f"{UNAUDITED_NOTICE} Reference: {correlation_id}"),
            TextContent(type="text", text=body),
        ],
        structured_content=structured,
        _meta={"eaia/audit": {"audited": False, "reference": str(correlation_id)}},
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


def create_server(
    session_factory: SessionFactory | None = None,
    *,
    transport: Transport = "stdio",
    audit_sink: AuditSink | None = None,
    rate_limiter: RateLimiter | None = None,
    model_policy: ModelPolicy | None = None,
    token_verifier: TokenVerifier | None = None,
    public_url: str | None = None,
    config: Settings | None = None,
    fallback_audit: FallbackAuditFile | None = None,
) -> MCPServer:
    """Build the Executive AI Advisor MCP server.

    ``session_factory`` returns a SQLAlchemy session; it defaults to the app's
    configured ``SessionLocal``. The other arguments are injectable for tests.
    ``token_verifier`` enables bearer authentication on HTTP transport;
    ``public_url`` is the URL clients use to reach the server.
    """
    config = config or settings
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    guard = CallGuard(
        transport=transport,
        audit_sink=LoggingAuditSink(audit_sink or DatabaseAuditSink(session_factory)),
        fallback=fallback_audit if fallback_audit is not None else FallbackAuditFile(config.mcp_audit_fallback_file),
        rate_limiter=rate_limiter
        or RateLimiter(
            {
                READ_POLICY: LimitPolicy(per_minute=config.mcp_rate_limit_read_per_minute),
                LLM_POLICY: LimitPolicy(
                    per_minute=config.mcp_rate_limit_llm_per_minute,
                    per_day=config.mcp_rate_limit_llm_per_day,
                ),
            }
        ),
        model_policy=model_policy or load_model_policy(config),
        config=config,
    )

    @contextmanager
    def db_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def guarded(name: str, arguments: dict[str, Any], operation: Callable[[Session], T], *, uses_model: bool) -> T:
        def _run() -> T:
            with db_session() as db:
                return operation(db)

        return guard.call(
            kind="tool",
            name=name,
            arguments=arguments,
            operation=_run,
            policy=LLM_POLICY if uses_model else READ_POLICY,
            uses_model=uses_model,
        )

    def run(name: str, arguments: dict[str, Any], operation: Callable[[Session], T]) -> T:
        return guarded(name, arguments, operation, uses_model=False)

    def run_llm(name: str, arguments: dict[str, Any], operation: Callable[[Session], T]) -> T:
        return guarded(name, arguments, operation, uses_model=True)

    auth_kwargs: dict[str, Any] = {}
    if token_verifier is not None:
        resource_url = public_url or "http://127.0.0.1:8765"
        auth_kwargs = {
            "token_verifier": token_verifier,
            "auth": AuthSettings(
                issuer_url=resource_url,
                resource_server_url=resource_url,
                validate_token_resource=False,
            ),
        }

    mcp = MCPServer(
        name="executive-ai-advisor",
        title=settings.app_name,
        instructions=SERVER_INSTRUCTIONS,
        website_url="https://github.com/serewicz/Executive-AI-Advisor",
        **auth_kwargs,
    )
    mcp.call_guard = guard  # exposed for tests and operators; not part of the MCP surface

    # ------------------------------------------------------------------ tools

    @mcp.tool(title="List investigations", annotations=READ_ONLY)
    def list_investigations(accept_unaudited: AcceptUnaudited = False) -> DocumentSetListResponse:
        """List investigation workspaces (document sets) with their document counts."""
        return run(
            "list_investigations", {"accept_unaudited": accept_unaudited}, document_set_service.list_document_sets
        )

    @mcp.tool(title="Search evidence", annotations=READ_ONLY)
    def search_evidence(
        query: Annotated[str, Field(min_length=1, max_length=settings.max_search_query_chars)],
        document_set_id: Annotated[UUID | None, Field(description="Limit search to one investigation.")] = None,
        document_id: Annotated[UUID | None, Field(description="Limit search to one document.")] = None,
        top_k: TopK = 5,
        accept_unaudited: AcceptUnaudited = False,
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

        return run(
            "search_evidence",
            {
                "query": query,
                "document_set_id": document_set_id,
                "document_id": document_id,
                "top_k": top_k,
                "accept_unaudited": accept_unaudited,
            },
            _search,
        )

    @mcp.tool(title="Ask the advisor", annotations=READ_ONLY_LLM)
    def ask_advisor(
        question: Annotated[str, Field(min_length=3, max_length=2000)],
        document_set_id: Annotated[UUID | None, Field(description="Answer from one investigation.")] = None,
        document_id: Annotated[UUID | None, Field(description="Answer from one document.")] = None,
        top_k: TopK = 5,
        llm_provider: Provider = None,
        llm_model: Model = None,
        accept_unaudited: AcceptUnaudited = False,
    ) -> AdvisorAskResponse:
        """Answer an executive question with cited evidence, confidence, and stated limitations."""
        return run_llm(
            "ask_advisor",
            {
                "question": question,
                "document_set_id": document_set_id,
                "document_id": document_id,
                "top_k": top_k,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "accept_unaudited": accept_unaudited,
            },
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
        accept_unaudited: AcceptUnaudited = False,
    ) -> BoardSummaryResponse:
        """Generate a cited board memo for a document or investigation."""
        return run_llm(
            "board_summary",
            {
                "summary_type": summary_type,
                "document_set_id": document_set_id,
                "document_id": document_id,
                "top_k": top_k,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "accept_unaudited": accept_unaudited,
            },
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
            accept_unaudited: AcceptUnaudited = False,
        ):
            return run_llm(
                name,
                {
                    "document_set_id": document_set_id,
                    "top_k": top_k,
                    "llm_provider": llm_provider,
                    "llm_model": llm_model,
                },
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
        accept_unaudited: AcceptUnaudited = False,
    ) -> TechnologyDiligenceReport:
        """Full technology due diligence report with findings, risk heatmap, and optional 100-day plan."""
        return run_llm(
            "technology_due_diligence_report",
            {
                "document_set_id": document_set_id,
                "top_k": top_k,
                "include_100_day_plan": include_100_day_plan,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "accept_unaudited": accept_unaudited,
            },
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
        accept_unaudited: AcceptUnaudited = False,
    ) -> HundredDayPlanResponse:
        """Sequenced 30/60/90-day plan with owners, outcomes, dependencies, and board checkpoints."""
        return run_llm(
            "hundred_day_plan",
            {
                "document_set_id": document_set_id,
                "plan_type": plan_type,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "accept_unaudited": accept_unaudited,
            },
            lambda db: executive_service.generate_executive_100_day_plan(
                document_set_id=document_set_id,
                plan_type=plan_type,
                db=db,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        )

    # -------------------------------------------------------------- resources

    def audited_resource(name: str, arguments: dict[str, Any], operation: Callable[[], str]) -> str:
        try:
            return guard.call(kind="resource", name=name, arguments=arguments, operation=operation, policy=READ_POLICY)
        except ToolError as exc:
            # Resources report errors through the resource error type, not ToolError.
            raise ResourceError(str(exc)) from None

    @mcp.resource("eaia://investigations", name="investigations", mime_type="application/json")
    def investigations_resource() -> str:
        """All investigation workspaces with document counts."""

        def _read() -> str:
            with db_session() as db:
                return document_set_service.list_document_sets(db).model_dump_json(indent=2)

        return audited_resource("eaia://investigations", {}, _read)

    @mcp.resource("eaia://investigations/{document_set_id}", name="investigation", mime_type="application/json")
    def investigation_resource(document_set_id: str) -> str:
        """One investigation workspace and its documents."""

        def _read() -> str:
            try:
                set_id = UUID(document_set_id)
            except ValueError:
                raise InvalidInput("Invalid investigation id.") from None
            with db_session() as db:
                document_set = document_set_service.get_document_set(set_id, db)
                if document_set is None:
                    raise NotFound("Investigation not found.")
                return document_set_service.document_set_detail(document_set, db).model_dump_json(indent=2)

        return audited_resource("eaia://investigations/{document_set_id}", {"document_set_id": document_set_id}, _read)

    # ---------------------------------------------------------------- prompts

    @mcp.prompt(title="Prepare for a board meeting")
    def board_meeting_prep(document_set_id: str, meeting_focus: str = "technology risk") -> str:
        """Guide the assistant through building a board pre-read from one investigation."""
        return guard.call(
            kind="prompt",
            name="board_meeting_prep",
            arguments={"document_set_id": document_set_id, "meeting_focus": meeting_focus},
            policy=READ_POLICY,
            operation=lambda: (
            f"Prepare a board pre-read on {meeting_focus} for investigation {document_set_id}.\n"
            "1. Call technology_risk_scorecard and board_brief for this investigation.\n"
            "2. Lead with the decisions the board must make, then the top risks and their business impact.\n"
            "3. Cite evidence for every claim and state confidence and limitations plainly.\n"
            "4. End with the questions directors should ask management."
            ),
        )

    @mcp.prompt(title="Technology due diligence review")
    def diligence_review(document_set_id: str, deal_type: PlanType = "growth_equity") -> str:
        """Guide the assistant through an investor-grade technology diligence review."""
        return guard.call(
            kind="prompt",
            name="diligence_review",
            arguments={"document_set_id": document_set_id, "deal_type": deal_type},
            policy=READ_POLICY,
            operation=lambda: (
            f"Run a technology due diligence review for investigation {document_set_id} ({deal_type}).\n"
            "1. Call technology_due_diligence_report, then hundred_day_plan with the same plan type.\n"
            "2. Separate findings supported by evidence from gaps that need management interviews.\n"
            "3. Summarize deal-relevant risks, value-creation levers, and the first 30 days of action."
            ),
        )

    return mcp

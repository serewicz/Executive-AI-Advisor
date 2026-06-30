import json
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisor.providers.base import SourceContext
from app.advisor.providers.factory import get_llm_provider
from app.advisor.schemas import Citation
from app.advisor.text import normalize_text_field
from app.core.config import settings
from app.governance.ai_knowledge_prompts import (
    AI_KNOWLEDGE_GOVERNANCE_SYSTEM_PROMPT,
    build_ai_knowledge_governance_prompt,
)
from app.governance.ai_knowledge_schemas import (
    AIKnowledgeGovernanceCategory,
    AIKnowledgeGovernanceFinding,
    AIKnowledgeGovernancePlan,
    AIKnowledgeGovernanceResponse,
)
from app.governance.ai_knowledge_scoring import (
    confidence_for_results,
    missing_evidence_for_category,
    overall_confidence,
    overall_readiness,
    readiness_for_category,
)
from app.models.document import Document, DocumentChunk, DocumentSet, DocumentSetDocument
from app.retrieval.evidence import extract_relevant_excerpt, is_low_value_chunk, relevance_reason
from app.retrieval.vector_search import SearchResult, search_similar_chunks


class AIKnowledgeGovernanceDocumentSetNotFoundError(ValueError):
    pass


class AIKnowledgeGovernanceValidationError(ValueError):
    pass


AI_KNOWLEDGE_CATEGORY_QUERIES: dict[AIKnowledgeGovernanceCategory, str] = {
    "knowledge_classification": "data classification public internal confidential restricted regulated proprietary IP AI usage policy",
    "data_lake_readiness": "data lake document repository metadata catalog knowledge source inventory retention lifecycle ownership",
    "rag_readiness": "RAG retrieval augmented generation vector search citations grounding chunking embeddings stale content evaluation",
    "enterprise_search": "OpenSearch enterprise search internal knowledge search staff self service permissions search data lake document discovery",
    "sensitive_ip_protection": "sensitive IP proprietary information protected knowledge public LLM leakage prompt policy data handling redaction masking",
    "slm_private_model_readiness": "SLM small language model local model private model endpoint data residency inference cost model ownership",
    "access_controls": "RBAC access control permissions document access least privilege identity integration SSO",
    "auditability": "audit logs prompt logs retrieved sources model provider output logging monitoring review trail",
    "vendor_and_provider_risk": "LLM provider vendor risk SaaS AI data retention contractual protections third party AI model risk",
    "cost_governance": "AI cost token cost inference cost provider usage chargeback showback budget controls",
    "employee_enablement": "approved AI tools employee training AI usage policy shadow AI internal knowledge discovery",
    "ai_incident_response": "AI incident response escalation board notification legal compliance customer notification provider incident post-incident review audit trail",
}

AI_KNOWLEDGE_CATEGORY_ORDER: tuple[AIKnowledgeGovernanceCategory, ...] = (
    "knowledge_classification",
    "data_lake_readiness",
    "rag_readiness",
    "enterprise_search",
    "sensitive_ip_protection",
    "slm_private_model_readiness",
    "access_controls",
    "auditability",
    "vendor_and_provider_risk",
    "cost_governance",
    "employee_enablement",
    "ai_incident_response",
)


def generate_ai_knowledge_governance_assessment(
    document_set_id: UUID,
    db: Session,
    top_k: int = 20,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
) -> AIKnowledgeGovernanceResponse:
    document_set = db.get(DocumentSet, document_set_id)
    if document_set is None:
        raise AIKnowledgeGovernanceDocumentSetNotFoundError("Document set not found.")

    results_by_category = _retrieve_results_by_category(document_set.id, top_k, db)
    all_results = _dedupe_results(
        result
        for results in results_by_category.values()
        for result in results
    )
    if not all_results:
        raise AIKnowledgeGovernanceValidationError("Document set has no chunks to analyze.")

    citation_map = _build_citation_map(all_results)
    findings = [
        _build_finding(category, results_by_category[category], citation_map)
        for category in AI_KNOWLEDGE_CATEGORY_ORDER
    ]
    readiness_values = [finding.readiness for finding in findings]
    confidence_values = [finding.confidence for finding in findings]
    draft = _draft_with_provider(
        all_results[: min(top_k, 20)],
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
    )

    return AIKnowledgeGovernanceResponse(
        document_set_id=document_set.id,
        overall_readiness=overall_readiness(readiness_values),
        confidence=overall_confidence(confidence_values),
        executive_summary=draft.get("executive_summary") or _executive_summary(findings),
        findings=findings,
        top_gaps=draft.get("top_gaps") or _top_gaps(findings),
        evidence_needed=_evidence_needed(findings),
        management_questions=draft.get("management_questions") or _management_questions(findings),
        board_discussion_points=draft.get("board_discussion_points") or _board_discussion_points(findings),
        recommended_actions=draft.get("recommended_actions") or _recommended_actions(findings),
        ninety_day_readiness_plan=_readiness_plan(findings),
        limitations=[
            "AI Knowledge Governance Assessment is limited to documents in the selected investigation workspace.",
            "This framework is not legal advice.",
            "Regulated data handling should be reviewed with legal and compliance leaders.",
            "Local SLMs and private model endpoints reduce some leakage risks but still require access controls, monitoring, testing, evaluation, and governance.",
            "RAG improves grounding but does not guarantee correctness.",
            "Reporting obligations vary by jurisdiction, company role, system type, and incident type. Legal and compliance counsel should confirm applicable obligations.",
            "Management should validate cited evidence and provide corroborating artifacts before relying on findings.",
            *draft.get("limitations", []),
        ],
        citations=list(citation_map.values()),
    )


def _retrieve_results_by_category(
    document_set_id: UUID,
    top_k: int,
    db: Session,
) -> dict[AIKnowledgeGovernanceCategory, list[SearchResult]]:
    per_category_k = max(2, min(6, top_k // max(1, len(AI_KNOWLEDGE_CATEGORY_QUERIES)) + 1))
    results_by_category = {}
    for category, query in AI_KNOWLEDGE_CATEGORY_QUERIES.items():
        try:
            results = search_similar_chunks(
                query=query,
                db=db,
                top_k=per_category_k,
                document_set_id=document_set_id,
            )
        except Exception:
            results = []
        if not results:
            results = _load_ordered_chunks_for_set(document_set_id, per_category_k, db)
        results_by_category[category] = _dedupe_results(results)[:per_category_k]
    return results_by_category


def _load_ordered_chunks_for_set(document_set_id: UUID, top_k: int, db: Session) -> list[SearchResult]:
    statement = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(DocumentSetDocument, DocumentSetDocument.document_id == Document.id)
        .where(DocumentSetDocument.document_set_id == document_set_id)
        .order_by(Document.uploaded_at.desc(), DocumentChunk.chunk_index)
        .limit(top_k)
    )
    rows = db.execute(statement).all()
    return [
        SearchResult(
            document_id=document.id,
            document_title=document.title or document.filename,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            similarity_score=0.0,
            source_type=document.source_type,
            classification=document.classification,
            chunk_metadata=chunk.chunk_metadata or {},
        )
        for chunk, document in rows
        if _is_useful_chunk(chunk)
    ]


def _is_useful_chunk(chunk: DocumentChunk) -> bool:
    normalized = " ".join(chunk.content.split())
    if not normalized:
        return False
    return not bool((chunk.chunk_metadata or {}).get("low_value")) and not is_low_value_chunk(normalized)


def _dedupe_results(results: Iterable[SearchResult]) -> list[SearchResult]:
    deduped = []
    seen = set()
    for result in results:
        if result.chunk_id in seen or result.low_value or is_low_value_chunk(result.content):
            continue
        seen.add(result.chunk_id)
        deduped.append(result)
    return deduped


def _build_citation_map(results: list[SearchResult]) -> dict[UUID, Citation]:
    citation_map = {}
    for index, result in enumerate(results, start=1):
        query = _query_for_result(result)
        excerpt = extract_relevant_excerpt(result.content, query, max_chars=500)
        citation_map[result.chunk_id] = Citation(
            source_label=f"S{index}",
            document_id=result.document_id,
            document_title=result.document_title,
            chunk_id=result.chunk_id,
            page_start=result.page_start,
            page_end=result.page_end,
            excerpt=excerpt,
            relevance_reason=relevance_reason(excerpt, query),
            full_source_text=result.content,
        )
    return citation_map


def _query_for_result(result: SearchResult) -> str:
    text = result.content.lower()
    return " ".join(
        query
        for query in AI_KNOWLEDGE_CATEGORY_QUERIES.values()
        if any(term in text for term in query.lower().split()[:4])
    ) or "AI knowledge governance"


def _build_finding(
    category: AIKnowledgeGovernanceCategory,
    results: list[SearchResult],
    citation_map: dict[UUID, Citation],
) -> AIKnowledgeGovernanceFinding:
    readiness = readiness_for_category(category, results)
    confidence = confidence_for_results(results)
    citations = [citation_map[result.chunk_id] for result in results if result.chunk_id in citation_map][:3]
    label_text = _citation_label_text(citations)

    return AIKnowledgeGovernanceFinding(
        category=category,
        title=_finding_title(category, readiness),
        readiness=readiness,
        confidence=confidence,
        business_impact=_business_impact(category, readiness, label_text),
        evidence_summary=_evidence_summary(category, results, label_text),
        missing_evidence=missing_evidence_for_category(category, results),
        recommended_action=_recommended_action(category, readiness),
        recommended_owner=_recommended_owner(category),
        citations=citations,
    )


def _draft_with_provider(
    results: list[SearchResult],
    llm_provider: str | None,
    llm_model: str | None,
    llm_api_key: str | None,
) -> dict[str, list[str] | str]:
    provider = get_llm_provider(llm_provider)
    if getattr(provider, "provider_name", "mock") == "mock":
        return {}

    source_contexts = [
        SourceContext(
            label=f"[S{index}]",
            content=result.content,
            document_title=result.document_title,
            page_start=result.page_start,
            page_end=result.page_end,
        )
        for index, result in enumerate(results, start=1)
    ]
    content = provider.generate(
        system_prompt=AI_KNOWLEDGE_GOVERNANCE_SYSTEM_PROMPT,
        user_prompt=build_ai_knowledge_governance_prompt(source_contexts),
        api_key_override=llm_api_key,
        model_override=llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return {"executive_summary": normalize_text_field(content)}
    if not isinstance(payload, dict):
        return {}
    return {
        "executive_summary": normalize_text_field(payload.get("executive_summary", "")),
        "top_gaps": _list_field(payload.get("top_gaps")),
        "management_questions": _list_field(payload.get("management_questions")),
        "board_discussion_points": _list_field(payload.get("board_discussion_points")),
        "recommended_actions": _list_field(payload.get("recommended_actions")),
        "limitations": _list_field(payload.get("limitations")),
    }


def _list_field(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_text_field(item) for item in value if normalize_text_field(item)]
    normalized = normalize_text_field(value)
    return [normalized] if normalized else []


def _citation_label_text(citations: list[Citation]) -> str:
    if not citations:
        return ""
    return " ".join(f"[{citation.source_label}]" for citation in citations[:3])


def _finding_title(category: AIKnowledgeGovernanceCategory, readiness: str) -> str:
    category_title = category.replace("_", " ").title()
    if readiness == "red":
        return f"Material {category_title} Gap"
    if readiness == "yellow":
        return f"Partial {category_title} Readiness"
    return f"Defined {category_title} Readiness"


def _business_impact(category: AIKnowledgeGovernanceCategory, readiness: str, labels: str) -> str:
    impacts = {
        "knowledge_classification": "Unclear knowledge classification can send sensitive information to the wrong AI architecture.",
        "data_lake_readiness": "Weak source inventory and metadata can limit governed knowledge access and increase key-person dependency.",
        "rag_readiness": "Immature RAG controls can produce poorly grounded answers or expose documents outside intended permissions.",
        "enterprise_search": "Weak enterprise search can push employees toward unsanctioned AI tools to find internal knowledge.",
        "sensitive_ip_protection": "Poor IP handling can expose proprietary knowledge, source code, product strategy, or trade secrets.",
        "slm_private_model_readiness": "Unclear SLM/private model strategy can create cost, data residency, ownership, and evaluation risk.",
        "access_controls": "Weak access control can allow AI-assisted retrieval to bypass normal document permissions.",
        "auditability": "Missing logs make it difficult to investigate AI-assisted knowledge access, leakage, or misuse.",
        "vendor_and_provider_risk": "Unreviewed providers can create data retention, contractual, continuity, and third-party AI risk.",
        "cost_governance": "Untracked AI usage can create unmanaged token, inference, and internal model operating cost.",
        "employee_enablement": "Poor enablement increases shadow AI usage and reduces adoption of governed knowledge workflows.",
        "ai_incident_response": "Weak AI incident response can delay containment, legal/compliance review, customer communications, executive escalation, and board visibility.",
    }
    prefix = "Material" if readiness == "red" else "Moderate" if readiness == "yellow" else "Limited"
    return f"{prefix} concern: {impacts[category]} {labels}".strip()


def _evidence_summary(
    category: AIKnowledgeGovernanceCategory,
    results: list[SearchResult],
    labels: str,
) -> str:
    if not results:
        return f"No direct evidence was retrieved for {category.replace('_', ' ')}."
    documents = sorted({result.document_title for result in results})
    return (
        f"Retrieved {len(results)} relevant evidence passage(s) across "
        f"{len(documents)} document(s): {', '.join(documents[:3])}. {labels}"
    ).strip()


def _recommended_action(category: AIKnowledgeGovernanceCategory, readiness: str) -> str:
    actions = {
        "knowledge_classification": "Define AI knowledge classes and data handling rules before approving AI architectures.",
        "data_lake_readiness": "Create a knowledge source inventory with ownership, metadata, classification, and lifecycle expectations.",
        "rag_readiness": "Document RAG retrieval, permissions, citation, evaluation, and stale-content controls.",
        "enterprise_search": "Evaluate OpenSearch or similar enterprise search for permissions-aware internal knowledge discovery.",
        "sensitive_ip_protection": "Document controls that keep sensitive IP out of public LLMs and route it through controlled retrieval or private model paths.",
        "slm_private_model_readiness": "Create a decision record for SLM/private model use cases, environment, ownership, cost, evaluation, and monitoring.",
        "access_controls": "Connect identity, RBAC, document permissions, and least-privilege reviews to retrieval workflows.",
        "auditability": "Log prompts, retrieved sources, users, model/provider, outputs, and exceptions for review and investigation.",
        "vendor_and_provider_risk": "Review AI providers for data handling, retention, contractual protections, continuity, and third-party model risk.",
        "cost_governance": "Implement AI cost tracking for provider spend, token/inference usage, private model operations, and budget ownership.",
        "employee_enablement": "Publish approved AI tool guidance and train staff on safe knowledge discovery workflows.",
        "ai_incident_response": "Define AI incident criteria, escalation paths, board notification triggers, legal/compliance involvement, model/provider handling, and post-incident review process.",
    }
    if readiness == "green":
        return f"Maintain evidence and review cadence. {actions[category]}"
    return actions[category]


def _recommended_owner(category: AIKnowledgeGovernanceCategory):
    owners = {
        "knowledge_classification": "CTO",
        "data_lake_readiness": "Data Leader",
        "rag_readiness": "CTO",
        "enterprise_search": "Operations",
        "sensitive_ip_protection": "CISO",
        "slm_private_model_readiness": "VP Engineering",
        "access_controls": "CISO",
        "auditability": "CISO",
        "vendor_and_provider_risk": "Legal",
        "cost_governance": "Operations",
        "employee_enablement": "Product",
        "ai_incident_response": "CISO",
    }
    return owners[category]


def _executive_summary(findings: list[AIKnowledgeGovernanceFinding]) -> str:
    overall = overall_readiness(finding.readiness for finding in findings)
    red_count = sum(1 for finding in findings if finding.readiness == "red")
    yellow_count = sum(1 for finding in findings if finding.readiness == "yellow")
    return (
        f"AI knowledge governance is assessed as {overall.upper()} based on retrieved evidence. "
        f"The assessment identified {red_count} material gap(s) and {yellow_count} partial readiness area(s). "
        "The core issue is whether enterprise knowledge is classified and routed to appropriate AI architectures. "
        "Public knowledge may use external LLMs with policy controls, internal knowledge may use governed RAG, "
        "and sensitive IP or regulated data should use controlled retrieval, private endpoints, local SLMs, "
        "and legal/compliance review where appropriate."
    )


def _top_gaps(findings: list[AIKnowledgeGovernanceFinding]) -> list[str]:
    ordered = sorted(findings, key=lambda finding: {"red": 0, "yellow": 1, "green": 2}[finding.readiness])
    return [f"{finding.category.replace('_', ' ').title()}: {finding.title}" for finding in ordered[:5]]


def _evidence_needed(findings: list[AIKnowledgeGovernanceFinding]) -> list[str]:
    evidence = []
    for finding in findings:
        evidence.extend(finding.missing_evidence)
    return list(dict.fromkeys(evidence))[:14]


def _management_questions(findings: list[AIKnowledgeGovernanceFinding]) -> list[str]:
    return [
        "What enterprise knowledge is safe to use with public LLMs?",
        "What sensitive IP must stay inside controlled systems?",
        "Do employees have a governed way to find internal knowledge without unsanctioned AI tools?",
        "How are retrieval permissions enforced for confidential or restricted documents?",
        "How are AI provider usage, model choice, outputs, and costs logged and reviewed?",
        "What qualifies as an AI incident?",
        "Who owns AI incident response?",
        "When is legal or compliance engaged?",
        "What AI incidents require executive or board escalation?",
        "How are model/provider incidents tracked?",
        "Are post-incident reviews documented?",
    ]


def _board_discussion_points(findings: list[AIKnowledgeGovernanceFinding]) -> list[str]:
    material_findings = [finding for finding in findings if finding.readiness in {"red", "yellow"}]
    return [
        "Whether AI knowledge use creates material IP, customer data, compliance, or operating risk.",
        "Which knowledge classes can use external LLMs and which require governed retrieval or private/local models.",
        "Whether the organization has enough auditability to investigate AI-assisted knowledge exposure.",
        "Whether management has an AI incident response plan.",
        "Which AI incidents would be reported to the board.",
        "How the company detects, contains, and remediates AI-related failures.",
        "Whether AI incident trends are reviewed alongside cybersecurity and operational risk.",
        f"Management should address the highest-priority knowledge governance areas: {', '.join(f.category.replace('_', ' ') for f in material_findings[:4])}.",
    ]


def _recommended_actions(findings: list[AIKnowledgeGovernanceFinding]) -> list[str]:
    return [finding.recommended_action for finding in findings if finding.readiness in {"red", "yellow"}][:9]


def _readiness_plan(findings: list[AIKnowledgeGovernanceFinding]) -> AIKnowledgeGovernancePlan:
    red_findings = [finding for finding in findings if finding.readiness == "red"]
    yellow_findings = [finding for finding in findings if finding.readiness == "yellow"]
    return AIKnowledgeGovernancePlan(
        days_1_30=[
            "Inventory AI tools and enterprise knowledge sources.",
            "Classify sensitive data and proprietary IP.",
            "Identify high-risk shadow AI usage.",
            "Define approved AI usage policy and data handling rules.",
            "Define AI incident criteria, severity levels, and escalation owners.",
            *[finding.recommended_action for finding in red_findings[:2]],
        ],
        days_31_60=[
            "Implement a pilot RAG workflow over low/medium-risk internal knowledge.",
            "Evaluate OpenSearch/vector store options for governed enterprise search.",
            "Define retrieval access controls and audit logging.",
            "Create AI incident response runbook and board escalation criteria.",
            "Identify SLM/private model candidates for sensitive IP workflows.",
            "Create AI cost tracking approach.",
            *[finding.recommended_action for finding in yellow_findings[:2]],
        ],
        days_61_90=[
            "Expand governed retrieval to priority workflows.",
            "Pilot SLM/private model pattern for a sensitive IP workflow.",
            "Train staff on approved AI usage and knowledge discovery workflows.",
            "Run an AI incident tabletop and document lessons learned.",
            "Create board-level AI knowledge governance report.",
            "Review policy compliance and refine controls.",
        ],
    )

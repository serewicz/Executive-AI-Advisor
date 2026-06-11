import json
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisor.providers.base import SourceContext
from app.advisor.providers.factory import get_llm_provider
from app.advisor.schemas import Citation
from app.advisor.text import normalize_text_field
from app.compliance.cra_prompts import CRA_READINESS_SYSTEM_PROMPT, build_cra_readiness_prompt
from app.compliance.cra_schemas import (
    CRAReadinessCategory,
    CRAReadinessFinding,
    CRAReadinessPlan,
    CRAReadinessResponse,
)
from app.compliance.cra_scoring import (
    confidence_for_cra_results,
    missing_evidence_for_category,
    overall_confidence,
    overall_readiness,
    readiness_for_category,
)
from app.core.config import settings
from app.models.document import Document, DocumentChunk, DocumentSet, DocumentSetDocument
from app.retrieval.evidence import extract_relevant_excerpt, is_low_value_chunk, relevance_reason
from app.retrieval.vector_search import SearchResult, search_similar_chunks


class CRADocumentSetNotFoundError(ValueError):
    pass


class CRAValidationError(ValueError):
    pass


CRA_CATEGORY_QUERIES: dict[CRAReadinessCategory, str] = {
    "scope": "EU market product with digital elements software product classification product scope customers geography",
    "secure_by_design": "secure by design threat model secure development lifecycle security requirements secure defaults hardening least privilege",
    "vulnerability_management": "vulnerability management CVE scanning remediation SLA disclosure exploited vulnerability security backlog",
    "sbom": "SBOM software bill of materials dependency inventory open source components EOL libraries package inventory",
    "security_updates": "security updates patching release process update delivery rollback customer notification support window",
    "incident_reporting": "incident response severe incident exploited vulnerability reporting ENISA CSIRT notification escalation",
    "technical_documentation": "technical documentation architecture security design risk assessment conformity evidence product security documentation",
    "supplier_risk": "supplier risk vendor risk third party components open source dependencies cloud provider payment provider KYC provider",
    "user_transparency": "user documentation secure configuration vulnerability disclosure support policy update instructions known limitations",
    "lifecycle_support": "maintenance support lifecycle end of life security patching product sunset version support",
}


CRA_CATEGORY_ORDER: tuple[CRAReadinessCategory, ...] = (
    "scope",
    "secure_by_design",
    "vulnerability_management",
    "sbom",
    "security_updates",
    "incident_reporting",
    "technical_documentation",
    "supplier_risk",
    "user_transparency",
    "lifecycle_support",
)


def generate_cra_readiness_assessment(
    document_set_id: UUID,
    db: Session,
    top_k: int = 20,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
) -> CRAReadinessResponse:
    document_set = db.get(DocumentSet, document_set_id)
    if document_set is None:
        raise CRADocumentSetNotFoundError("Document set not found.")

    results_by_category = _retrieve_results_by_category(document_set.id, top_k, db)
    all_results = _dedupe_results(
        result
        for results in results_by_category.values()
        for result in results
    )
    if not all_results:
        raise CRAValidationError("Document set has no chunks to analyze.")

    citation_map = _build_citation_map(all_results)
    findings = [
        _build_finding(category, results_by_category[category], citation_map)
        for category in CRA_CATEGORY_ORDER
    ]
    readiness_values = [finding.readiness for finding in findings]
    confidence_values = [finding.confidence for finding in findings]
    draft = _draft_with_provider(
        all_results[: min(top_k, 20)],
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
    )

    return CRAReadinessResponse(
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
            "CRA Readiness Assessment is limited to documents in the selected investigation workspace.",
            "This is a readiness assessment, not legal advice.",
            "Legal counsel should confirm CRA applicability, product classification, conformity assessment pathway, and reporting obligations.",
            "September 2026 reporting readiness and December 2027 full-readiness planning are included as planning milestones, not legal conclusions.",
            "Management should validate cited evidence and provide corroborating artifacts before relying on findings.",
            *draft.get("limitations", []),
        ],
        citations=list(citation_map.values()),
    )


def _retrieve_results_by_category(
    document_set_id: UUID,
    top_k: int,
    db: Session,
) -> dict[CRAReadinessCategory, list[SearchResult]]:
    per_category_k = max(2, min(6, top_k // max(1, len(CRA_CATEGORY_QUERIES)) + 1))
    results_by_category = {}
    for category, query in CRA_CATEGORY_QUERIES.items():
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
        for query in CRA_CATEGORY_QUERIES.values()
        if any(term in text for term in query.lower().split()[:4])
    ) or "Cyber Resilience Act readiness"


def _build_finding(
    category: CRAReadinessCategory,
    results: list[SearchResult],
    citation_map: dict[UUID, Citation],
) -> CRAReadinessFinding:
    readiness = readiness_for_category(category, results)
    confidence = confidence_for_cra_results(results)
    citations = [citation_map[result.chunk_id] for result in results if result.chunk_id in citation_map][:3]
    label_text = _citation_label_text(citations)

    return CRAReadinessFinding(
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
        system_prompt=CRA_READINESS_SYSTEM_PROMPT,
        user_prompt=build_cra_readiness_prompt(source_contexts),
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


def _finding_title(category: CRAReadinessCategory, readiness: str) -> str:
    category_title = category.replace("_", " ").title()
    if readiness == "red":
        return f"Material {category_title} Readiness Gap"
    if readiness == "yellow":
        return f"Partial {category_title} Readiness"
    return f"Defined {category_title} Readiness"


def _business_impact(category: CRAReadinessCategory, readiness: str, labels: str) -> str:
    impacts = {
        "scope": "Unclear scope can delay CRA applicability analysis, product classification, and go-to-market planning.",
        "secure_by_design": "Weak security-by-design evidence can increase remediation cost, product risk, and customer trust exposure.",
        "vulnerability_management": "Immature vulnerability handling can create reporting, customer notification, and operational risk.",
        "sbom": "Limited component visibility can weaken software supply chain transparency and vulnerability response.",
        "security_updates": "Unclear update processes can slow security patch delivery and customer communication.",
        "incident_reporting": "Weak reporting readiness can affect severe incident escalation and regulatory response planning.",
        "technical_documentation": "Missing technical documentation can slow conformity planning and board-level readiness review.",
        "supplier_risk": "Supplier and component gaps can increase third-party, OSS, and cloud dependency exposure.",
        "user_transparency": "Weak user-facing security guidance can reduce customer ability to configure and operate products safely.",
        "lifecycle_support": "Unclear support periods can create patching, maintenance, and customer obligation risk.",
    }
    prefix = "Material" if readiness == "red" else "Moderate" if readiness == "yellow" else "Limited"
    return f"{prefix} concern: {impacts[category]} {labels}".strip()


def _evidence_summary(category: CRAReadinessCategory, results: list[SearchResult], labels: str) -> str:
    if not results:
        return f"No direct evidence was retrieved for {category.replace('_', ' ')}."
    documents = sorted({result.document_title for result in results})
    return (
        f"Retrieved {len(results)} relevant evidence passage(s) across "
        f"{len(documents)} document(s): {', '.join(documents[:3])}. {labels}"
    ).strip()


def _recommended_action(category: CRAReadinessCategory, readiness: str) -> str:
    actions = {
        "scope": "Ask Legal, Product, and CTO leadership to document EU market exposure, product scope, and classification assumptions.",
        "secure_by_design": "Create or update secure development lifecycle evidence, threat models, security requirements, and hardening standards.",
        "vulnerability_management": "Document vulnerability intake, scanning, triage, remediation SLAs, disclosure, and exploited vulnerability escalation.",
        "sbom": "Produce an SBOM and dependency inventory with ownership for third-party, OSS, license, and EOL component tracking.",
        "security_updates": "Document the security update, patch release, rollback, release note, support window, and customer notification process.",
        "incident_reporting": "Create a severe incident and exploited vulnerability reporting runbook, including escalation and 24-hour readiness planning where applicable.",
        "technical_documentation": "Assemble product security documentation, architecture evidence, risk assessment, and conformity planning artifacts.",
        "supplier_risk": "Review supplier, cloud, payment, security, OSS, and third-party component obligations and risk ownership.",
        "user_transparency": "Publish secure configuration, update instructions, known limitations, support policy, and vulnerability disclosure channel guidance.",
        "lifecycle_support": "Define product support periods, maintenance commitments, EOL process, and security patching expectations.",
    }
    if readiness == "green":
        return f"Maintain evidence and review cadence. {actions[category]}"
    return actions[category]


def _recommended_owner(category: CRAReadinessCategory):
    owners = {
        "scope": "Legal",
        "secure_by_design": "CTO",
        "vulnerability_management": "CISO",
        "sbom": "VP Engineering",
        "security_updates": "VP Engineering",
        "incident_reporting": "CISO",
        "technical_documentation": "Compliance",
        "supplier_risk": "Compliance",
        "user_transparency": "Product",
        "lifecycle_support": "Product",
    }
    return owners[category]


def _executive_summary(findings: list[CRAReadinessFinding]) -> str:
    overall = overall_readiness(finding.readiness for finding in findings)
    red_count = sum(1 for finding in findings if finding.readiness == "red")
    yellow_count = sum(1 for finding in findings if finding.readiness == "yellow")
    return (
        f"CRA readiness is assessed as {overall.upper()} based on retrieved evidence. "
        f"The assessment identified {red_count} material gap(s) and {yellow_count} partial readiness area(s). "
        "Priority should be given to evidence for scope, vulnerability handling, SBOM/component visibility, "
        "incident reporting, technical documentation, and security update processes. "
        "September 2026 reporting readiness and December 2027 full-readiness planning should be treated as management planning milestones."
    )


def _top_gaps(findings: list[CRAReadinessFinding]) -> list[str]:
    ordered = sorted(findings, key=lambda finding: {"red": 0, "yellow": 1, "green": 2}[finding.readiness])
    return [f"{finding.category.replace('_', ' ').title()}: {finding.title}" for finding in ordered[:5]]


def _evidence_needed(findings: list[CRAReadinessFinding]) -> list[str]:
    evidence = []
    for finding in findings:
        evidence.extend(finding.missing_evidence)
    return list(dict.fromkeys(evidence))[:12]


def _management_questions(findings: list[CRAReadinessFinding]) -> list[str]:
    return [
        "Which products or product components may be placed on the EU market as products with digital elements?",
        "Who owns CRA readiness across Product, Engineering, Security, Legal, and Compliance?",
        "Can management produce evidence for SBOM, vulnerability handling, security updates, incident reporting, and technical documentation?",
        "What must be ready by September 2026 for reporting readiness planning?",
        "What work must be funded and governed before December 2027 full-readiness planning?",
    ]


def _board_discussion_points(findings: list[CRAReadinessFinding]) -> list[str]:
    material_findings = [finding for finding in findings if finding.readiness in {"red", "yellow"}]
    return [
        "Whether CRA readiness creates diligence, go-to-market, product, or operating risk.",
        "Which readiness gaps require executive ownership, budget, or board monitoring.",
        "Whether legal counsel has confirmed applicability, product classification, conformity pathway, and reporting obligations.",
        f"Management should address the highest-priority readiness areas: {', '.join(f.category.replace('_', ' ') for f in material_findings[:4])}.",
    ]


def _recommended_actions(findings: list[CRAReadinessFinding]) -> list[str]:
    return [finding.recommended_action for finding in findings if finding.readiness in {"red", "yellow"}][:8]


def _readiness_plan(findings: list[CRAReadinessFinding]) -> CRAReadinessPlan:
    red_findings = [finding for finding in findings if finding.readiness == "red"]
    yellow_findings = [finding for finding in findings if finding.readiness == "yellow"]
    return CRAReadinessPlan(
        days_1_30=[
            "Confirm CRA applicability assumptions, EU market exposure, product scope, and product classification path with legal counsel.",
            *[finding.recommended_action for finding in red_findings[:3]],
        ],
        days_31_60=[
            "Create evidence pack for September 2026 reporting readiness planning, including escalation, incident, and vulnerability handling artifacts.",
            *[finding.recommended_action for finding in yellow_findings[:3]],
        ],
        days_61_90=[
            "Build board-visible roadmap for December 2027 full-readiness planning, including owners, artifacts, milestones, and open legal questions.",
            "Review readiness status with Product, Engineering, Security, Legal, Compliance, and the Board.",
        ],
    )

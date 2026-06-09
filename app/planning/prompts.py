from app.planning.schemas import PlanType


PLAN_TYPE_FOCUS: dict[PlanType, list[str]] = {
    "growth_equity": [
        "scalability",
        "governance",
        "delivery predictability",
        "security",
    ],
    "acquisition_integration": [
        "knowledge transfer",
        "identity integration",
        "deployment standardization",
        "documentation",
        "support transition",
    ],
    "turnaround": [
        "risk reduction",
        "cost control",
        "operational stability",
        "ownership clarity",
    ],
}


PLAN_TYPE_SUMMARY: dict[PlanType, str] = {
    "growth_equity": "support growth equity scaling by improving governance, delivery predictability, security, and platform readiness",
    "acquisition_integration": "reduce acquisition integration risk through knowledge transfer, identity and deployment standardization, documentation, and support handoff",
    "turnaround": "stabilize operations, reduce urgent technology risk, improve cost control, and clarify ownership",
}

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


PLAN_TYPE_OUTCOMES: dict[PlanType, list[str]] = {
    "growth_equity": [
        "improve delivery predictability",
        "support scale",
        "improve platform leverage",
        "enable growth initiatives",
    ],
    "acquisition_integration": [
        "reduce integration execution risk",
        "preserve operational continuity",
        "transfer critical knowledge",
        "identify integration blockers before close or post-close",
    ],
    "turnaround": [
        "reduce immediate operational risk",
        "stabilize production ownership",
        "identify cost savings",
        "stop uncontrolled technology spend",
    ],
}


SCENARIO_ACTIONS: dict[PlanType, dict[str, list[str]]] = {
    "growth_equity": {
        "days_1_30": [
            "Create feature flag rollout plan for high-risk releases",
            "Establish observability baseline for critical workflows",
            "Review delivery cadence and engineering OKRs",
            "Select initial AI pilot with governance guardrails",
        ],
        "days_31_60": [
            "Complete capacity planning for growth scenarios",
            "Run architecture scalability review",
            "Approve engineering hiring and coverage plan",
            "Launch cloud cost allocation and FinOps review",
        ],
        "days_61_90": [
            "Pilot platform modernization for the highest-leverage bottleneck",
            "Implement release automation improvements",
            "Create technical debt burn-down plan",
            "Launch board operating dashboard for delivery and reliability",
        ],
        "days_91_100": [
            "Present growth-readiness scorecard and next-quarter roadmap to the board",
        ],
    },
    "acquisition_integration": {
        "days_1_30": [
            "Run joint technical workshops with acquirer",
            "Create parallel runbooks for critical systems",
            "Map identity and access integration paths",
            "Map core data model and migration dependencies",
            "Create support handoff plan with acquirer-side owners",
        ],
        "days_31_60": [
            "Standardize deployment and release handoff process",
            "Complete knowledge transfer for top key-person dependencies",
            "Validate integration blocker register with acquirer",
        ],
        "days_61_90": [
            "Run integration readiness rehearsal for identity, data, support, and deployment",
            "Resolve priority documentation and operational continuity gaps",
            "Create post-close technology operating dashboard",
        ],
        "days_91_100": [
            "Deliver board readout on integration blockers, continuity risk, and post-close decisions",
        ],
    },
    "turnaround": {
        "days_1_30": [
            "Freeze non-critical technology spend pending review",
            "Validate emergency backup and restore process",
            "Run founder and key-person shadow sessions",
            "Complete production access review",
            "Triage critical vulnerabilities",
        ],
        "days_31_60": [
            "Implement cost-control operating cadence",
            "Assign production ownership and incident roles",
            "Document top recovery and release workflows",
        ],
        "days_61_90": [
            "Launch stability dashboard with MTTR and incident trends",
            "Execute technical debt burn-down plan for top operational risks",
            "Set FinOps savings targets where waste is identified",
        ],
        "days_91_100": [
            "Present stabilization scorecard, unresolved risks, and required budget decisions to the board",
        ],
    },
}

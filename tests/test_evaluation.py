from uuid import uuid4

from fastapi.testclient import TestClient

from app.advisor.schemas import AdvisorAskResponse, AdvisorCitation
from app.db.dependencies import get_db
from app.evaluation.schemas import EvaluationQuestion
from app.evaluation.scoring import score_advisor_response, score_citations
from app.evaluation.service import run_document_evaluation
from app.main import app
from app.models.document import Document


class FakeEvaluationSession:
    def __init__(self, document):
        self.document = document
        self.added = None
        self.committed = False

    def get(self, model, object_id):
        if self.document is not None and self.document.id == object_id:
            return self.document
        return None

    def add(self, instance):
        self.added = instance

    def commit(self):
        self.committed = True

    def refresh(self, instance):
        return None


def make_document():
    return Document(
        id=uuid4(),
        title="Technology Assessment",
        filename="assessment.pdf",
        file_path="data/uploads/assessment.pdf",
        source="assessment.pdf",
        document_type="pdf",
        status="embedded",
        source_type="technology_assessment",
        classification="confidential",
        document_metadata={},
    )


def make_advisor_response(answer=None, citations=None):
    document_id = uuid4()
    citation = AdvisorCitation(
        document_id=document_id,
        document_title="Technology Assessment",
        chunk_id=uuid4(),
        page_start=1,
        page_end=2,
        excerpt="Cybersecurity risks require board monitoring and control validation.",
    )
    return AdvisorAskResponse(
        question="What cybersecurity risks are disclosed?",
        answer=answer
        or "Cybersecurity risk requires board monitoring, management action, and control validation. [S1]",
        citations=citations if citations is not None else [citation],
        confidence="medium",
        limitations=["Limited to retrieved evidence."],
    )


def override_db(session):
    def _override_db():
        yield session

    return _override_db


def test_evaluation_run_creates_results(monkeypatch):
    document = make_document()
    session = FakeEvaluationSession(document)
    monkeypatch.setattr("app.evaluation.service.answer_executive_question", lambda **kwargs: make_advisor_response())

    response = run_document_evaluation(
        document_id=document.id,
        questions=[
            EvaluationQuestion(
                question="What cybersecurity risks are disclosed?",
                expected_themes=["cybersecurity", "risk", "controls"],
            )
        ],
        db=session,
    )

    assert session.added is not None
    assert session.committed is True
    assert response.document_id == document.id
    assert response.results[0].question == "What cybersecurity risks are disclosed?"
    assert response.average_score > 0


def test_citation_score_works():
    citations = [{"source_label": "S1", "excerpt": "Risk evidence."}]

    assert score_citations("Risk is disclosed. [S1]", citations) == 1.0
    assert score_citations("Risk is disclosed without a clear source.", citations) == 0.5


def test_missing_citations_score_low():
    result = score_advisor_response(
        question=EvaluationQuestion(question="What risks exist?", expected_themes=["risk"]),
        answer="There are operational risks.",
        citations=[],
        limitations=[],
    )

    assert result.citation_score == 0.0
    assert result.groundedness_score == 0.3


def test_average_score_calculates_correctly(monkeypatch):
    document = make_document()
    session = FakeEvaluationSession(document)
    responses = [
        make_advisor_response(),
        make_advisor_response(answer="", citations=[]),
    ]

    def fake_answer(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr("app.evaluation.service.answer_executive_question", fake_answer)

    response = run_document_evaluation(
        document_id=document.id,
        questions=[
            EvaluationQuestion(question="What cybersecurity risks are disclosed?"),
            EvaluationQuestion(question="What operational risks are disclosed?"),
        ],
        db=session,
    )

    expected_average = round(sum(result.overall_score for result in response.results) / 2, 3)
    assert response.average_score == expected_average


def test_evaluation_endpoint_returns_expected_schema(monkeypatch):
    document = make_document()
    session = FakeEvaluationSession(document)
    monkeypatch.setattr("app.evaluation.service.answer_executive_question", lambda **kwargs: make_advisor_response())
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/evaluation/run",
            json={
                "document_id": str(document.id),
                "evaluation_type": "advisor_qa",
                "questions": [
                    {
                        "question": "What cybersecurity risks are disclosed?",
                        "expected_themes": ["security", "risk", "controls"],
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["evaluation_run_id"]
    assert body["document_id"] == str(document.id)
    assert body["evaluation_type"] == "advisor_qa"
    assert body["average_score"] > 0
    assert body["results"][0]["citation_score"] == 1.0

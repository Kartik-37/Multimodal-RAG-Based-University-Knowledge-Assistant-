"""Frontend API client contract tests.

Validates that HTTP responses, error handling, and parameter serialization
strictly uphold interface and security contracts.
"""

from unittest.mock import MagicMock

import pytest

from frontend.client.api_client import FrontendAPIClient


def _error_response(status_code: int, detail: str) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {"detail": detail}
    response.text = detail
    return response


@pytest.mark.parametrize(
    ("method_name", "url", "kwargs"),
    [
        ("get_knowledge_bases", "/knowledge-bases", {}),
        ("get_course_summaries", "/knowledge-bases/summaries", {}),
        (
            "get_documents",
            "/knowledge-bases/00000000-0000-0000-0000-000000000001/documents",
            {"kb_id": "00000000-0000-0000-0000-000000000001"},
        ),
        ("get_chat_scope_courses", "/knowledge-bases/chat-scopes", {}),
        ("get_document_scope_courses", "/knowledge-bases/document-scopes", {}),
    ],
)
def test_api_client_does_not_turn_http_errors_into_empty_lists(
    method_name: str, url: str, kwargs: dict
) -> None:
    """HTTP errors must raise exceptions rather than returning silently empty lists."""
    client = FrontendAPIClient()
    client._http = MagicMock()
    client._http.get.return_value = _error_response(403, "Forbidden")

    with pytest.raises(ValueError):
        getattr(client, method_name)(**kwargs)


def test_api_client_chat_request_preserves_explicit_scope() -> None:
    """Chat requests must preserve explicit scope parameters and UUID identifiers."""
    client = FrontendAPIClient()
    client._http = MagicMock()

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "query": "What is the territorial jurisdiction?",
        "processed_query": "What is the territorial jurisdiction?",
        "knowledge_base_id": None,
        "answer": "The jurisdiction is stated in the document. [source_1]",
        "is_empty_context": False,
        "citations": [],
        "grounding": {
            "is_grounded": True,
            "status": "FULLY_SUPPORTED",
            "citation_validity_rate": 1.0,
            "citation_coverage": 1.0,
            "claim_support_rate": 1.0,
            "unsupported_claim_rate": 0.0,
            "has_conflicts": False,
            "claims": [],
        },
        "latency": {
            "query_processing_ms": 1,
            "retrieval_ms": 1,
            "reranking_ms": 1,
            "context_assembly_ms": 1,
            "llm_generation_ms": 1,
            "grounding_validation_ms": 1,
            "total_pipeline_ms": 7,
        },
        "model": "test-model",
    }
    client._http.post.return_value = response

    client.send_chat_message(
        kb_id="00000000-0000-0000-0000-000000000001",
        document_id="00000000-0000-0000-0000-000000000002",
        scope="DOCUMENT",
        question="What is the territorial jurisdiction?",
    )

    payload = client._http.post.call_args.kwargs["json"]
    assert payload["scope"] == "DOCUMENT"
    assert payload["knowledge_base_id"] == "00000000-0000-0000-0000-000000000001"
    assert payload["document_id"] == "00000000-0000-0000-0000-000000000002"
    assert payload["question"] == "What is the territorial jurisdiction?"

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai import ki1_extraction
from app.ai.prompts import SYSTEM_PROMPT
from app.main import app


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=self.output_text,
            usage=SimpleNamespace(input_tokens=12, output_tokens=8),
        )


class FakeOpenAIClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_ai_extract_returns_structured_result_with_one_mocked_openai_call(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected_result = {"original_text": "Peter Wagner Fußpflege groß durchgeführt.", "strukturierte_daten": {}}
    fake_client = FakeOpenAIClient(json.dumps(expected_result, ensure_ascii=False))
    monkeypatch.setattr(ki1_extraction, "_get_openai_client", lambda: fake_client)

    response = client.post("/ai/extract", json={"text": "Peter Wagner Fußpflege groß durchgeführt."})

    assert response.status_code == 200
    assert response.json() == expected_result
    assert len(fake_client.responses.calls) == 1
    assert fake_client.responses.calls[0] == {
        "model": "gpt-4.1-mini",
        "instructions": SYSTEM_PROMPT,
        "input": "Strukturiere ausschließlich den folgenden Behandlungs-Text nach den Regeln.\n\nPeter Wagner Fußpflege groß durchgeführt.",
        "temperature": 0,
    }


def test_ai_extract_rejects_empty_text_and_unknown_fields(client: TestClient) -> None:
    assert client.post("/ai/extract", json={"text": "   "}).status_code == 422
    assert client.post("/ai/extract", json={"text": "Behandlung", "unexpected": True}).status_code == 422


def test_ai_extract_handles_missing_api_key_and_invalid_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ki1_extraction,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key=None),
    )
    missing_key_response = client.post("/ai/extract", json={"text": "Behandlung"})
    monkeypatch.setattr(ki1_extraction, "_get_openai_client", lambda: FakeOpenAIClient("not json"))
    invalid_json_response = client.post("/ai/extract", json={"text": "Behandlung"})

    assert missing_key_response.status_code == 503
    assert invalid_json_response.status_code == 502

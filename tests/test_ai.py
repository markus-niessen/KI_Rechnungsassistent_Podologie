import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai import ki1_extraction, ki2_validation
from app.ai.orchestration import extract_and_validate
from app.ai.prompts import KI2_SYSTEM_PROMPT, SYSTEM_PROMPT
from app.main import app


class FakeResponses:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=self.outputs.pop(0),
            usage=SimpleNamespace(input_tokens=12, output_tokens=8),
        )


class FakeOpenAIClient:
    def __init__(self, outputs: list[str]) -> None:
        self.responses = FakeResponses(outputs)


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _mock_openai(monkeypatch: pytest.MonkeyPatch, outputs: list[dict[str, object]]) -> FakeOpenAIClient:
    fake_client = FakeOpenAIClient([json.dumps(output, ensure_ascii=False) for output in outputs])
    monkeypatch.setattr(ki1_extraction, "_get_openai_client", lambda: fake_client)
    monkeypatch.setattr(ki2_validation, "_get_openai_client", lambda: fake_client)
    return fake_client


def _extraction(payment: str | None = None) -> dict[str, object]:
    data: dict[str, object] = {
        "original_text": "Peter Beispiel Fußpflege groß durchgeführt.",
        "strukturierte_daten": {"positionen": ["Fußpflege groß"]},
    }
    if payment is not None:
        data["strukturierte_daten"] = {"positionen": ["Fußpflege groß"], "zahlung": payment}
    return data


def _position(name: str, position_type: str, **additional: object) -> dict[str, object]:
    return {"bezeichnung": name, "typ": position_type, "menge": 1, **additional}


def _validation_data(source_text: str, positions: list[dict[str, object]]) -> dict[str, object]:
    return {
        "original_text": source_text,
        "strukturierte_daten": {
            "patient": {"vorname": "Peter", "nachname": "Wagner"},
            "positionen": positions,
        },
    }


def test_ai_extract_returns_structured_result_with_one_mocked_openai_call(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import ai as ai_routes

    expected_result = _extraction()
    fake_client = _mock_openai(monkeypatch, [expected_result])
    monkeypatch.setattr(ai_routes, "get_active_service_names", lambda db: [])

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


@pytest.mark.parametrize(
    ("text", "service_names", "response_name"),
    [
        (
            "Peter Wagner, Spirularin Gel 40 ml mitgegeben.",
            ["Spirularin HF Gel 40 ml"],
            "Spirularin HF Gel 40 ml",
        ),
        (
            "Peter Wagner, Fußpflege grosse durchgeführt.",
            ["Fußpflege groß"],
            "Fußpflege groß",
        ),
        (
            "Peter Wagner, Unbekanntes Pflegeprodukt mitgegeben.",
            ["Spirularin HF Gel 40 ml"],
            "Unbekanntes Pflegeprodukt",
        ),
        (
            "Peter Wagner, Fußpflege durchgeführt.",
            ["Fußpflege klein", "Fußpflege groß"],
            "Fußpflege",
        ),
    ],
)
def test_ki1_uses_dynamic_service_context_without_forcing_unknown_names(
    monkeypatch: pytest.MonkeyPatch, text: str, service_names: list[str], response_name: str
) -> None:
    expected_result = {
        "original_text": text,
        "strukturierte_daten": {
            "positionen": [
                {"bezeichnung": response_name, "typ": "produkt", "menge": 1, "verwendungszweck": "abgabe"}
            ]
        },
    }
    fake_client = _mock_openai(monkeypatch, [expected_result])

    result = ki1_extraction.extract_treatment_text(
        text,
        service_names=service_names,
    )

    assert result == expected_result
    prompt_input = str(fake_client.responses.calls[0]["input"])
    assert "Aktive Leistungen/Produkte aus der Datenbank" in prompt_input
    for service_name in service_names:
        assert f"- {service_name}" in prompt_input
    assert "Nicht mehr angebotene Leistung" not in prompt_input
    assert "MUSST du exakt diese Datenbank-Bezeichnung ausgeben" in prompt_input
    assert "mehrere plausible Treffer oder keinen eindeutigen Treffer" in prompt_input


@pytest.mark.parametrize(
    ("source_text", "position_name", "service_names", "review_status"),
    [
        (
            "Peter Wagner, Spirularin Gel 40 ml mitgegeben.",
            "Spirularin HF Gel 40 ml",
            ["Spirularin HF Gel 40 ml"],
            "ok",
        ),
        (
            "Peter Wagner, Unbekanntes Produkt mitgegeben.",
            "Erfundenes Produkt",
            ["Spirularin HF Gel 40 ml"],
            "correction_required",
        ),
        (
            "Peter Wagner, Spirularin HF Gel 100 ml mitgegeben.",
            "Spirularin HF Gel 40 ml",
            ["Spirularin HF Gel 40 ml"],
            "correction_required",
        ),
        (
            "Peter Wagner, Spirularin Gel 40 ml mitgegeben.",
            "Spirularin HF Gel 40 ml",
            ["Spirularin Gel 40 ml", "Spirularin HF Gel 40 ml"],
            "correction_required",
        ),
        (
            "Peter Wagner, Spirularin Gel 40 ml mitgegeben.",
            "Spirularin HF Gel 40 ml",
            [],
            "correction_required",
        ),
    ],
)
def test_ki2_receives_active_service_context_for_normalization_checks(
    source_text: str,
    position_name: str,
    service_names: list[str],
    review_status: str,
) -> None:
    extracted_data = {
        "original_text": source_text,
        "strukturierte_daten": {"positionen": [_position(position_name, "produkt")]},
    }
    review = {"status": review_status, "issues": [], "summary": None}
    fake_client = FakeOpenAIClient([json.dumps(review, ensure_ascii=False)])

    result = ki2_validation.validate_ki1_result(
        source_text,
        extracted_data,
        client=fake_client,
        service_names=service_names,
    )

    assert result.status == review_status
    validation_input = str(fake_client.responses.calls[0]["input"])
    for service_name in service_names:
        assert f"- {service_name}" in validation_input
    assert "Nicht mehr angebotene Leistung" not in validation_input


@pytest.mark.parametrize("correction_phrase", ["ich meine", "Korrektur:"])
def test_ki1_self_correction_replaces_only_the_corrected_position(
    monkeypatch: pytest.MonkeyPatch, correction_phrase: str
) -> None:
    source_text = (
        f"Peter Wagner, Fußpflege klein durchgeführt, {correction_phrase} Fußpflege groß. Mehrarbeit gemacht."
    )
    extraction = {
        "original_text": source_text,
        "strukturierte_daten": {
            "positionen": [
                _position("Fußpflege groß", "leistung"),
                _position("Mehrarbeit", "zusatzleistung"),
            ]
        },
    }
    fake_client = _mock_openai(monkeypatch, [extraction, {"status": "ok", "issues": [], "summary": None}])

    result = extract_and_validate(source_text)

    positions = result.data["strukturierte_daten"]["positionen"]
    assert _position("Fußpflege groß", "leistung") in positions
    assert _position("Mehrarbeit", "zusatzleistung") in positions
    assert _position("Fußpflege klein", "leistung") not in positions
    assert result.manual_review_required is False
    assert "Korrektur:" in SYSTEM_PROMPT
    assert "SELBSTKORREKTUREN HABEN VORRANG" in str(fake_client.responses.calls[0]["input"])
    assert len(fake_client.responses.calls) == 2


def test_ki1_prompt_does_not_guess_ambiguous_self_corrections() -> None:
    assert "Ist nicht eindeutig, welche Angabe korrigiert wurde, nicht raten" in SYSTEM_PROMPT


@pytest.mark.parametrize(
    ("source_text", "revoked", "replacement"),
    [
        ("Fußpflege klein, ich meine Fußpflege groß.", "Fußpflege klein", "Fußpflege groß"),
        ("Fußpflege klein. Korrektur: Fußpflege groß.", "Fußpflege klein", "Fußpflege groß"),
    ],
)
def test_ki1_correction_input_marks_common_self_correction_variants(
    source_text: str, revoked: str, replacement: str
) -> None:
    correction_input = ki1_extraction._self_correction_input(source_text)

    assert "SELBSTKORREKTUREN HABEN VORRANG" in correction_input
    assert "widerrufen" in correction_input
    assert revoked in correction_input
    assert replacement in correction_input


@pytest.mark.parametrize("correction_phrase", ["ich meine", "Korrektur:"])
def test_ki2_accepts_a_fully_resolved_self_correction(
    correction_phrase: str,
) -> None:
    source_text = f"Peter Wagner, Fußpflege klein durchgeführt, {correction_phrase} Fußpflege groß."
    extracted_data = _validation_data(source_text, [_position("Fußpflege groß", "leistung")])
    fake_client = FakeOpenAIClient([json.dumps({"status": "ok", "issues": [], "summary": None})])

    result = ki2_validation.validate_ki1_result(source_text, extracted_data, client=fake_client)

    assert result.status == "ok"
    assert result.issues == []
    assert 'Direkte Selbstkorrekturen mit "X, ich meine Y"' in str(fake_client.responses.calls[0]["instructions"])
    assert source_text in str(fake_client.responses.calls[0]["input"])


@pytest.mark.parametrize(
    ("text", "patient"),
    [
        (
            "Keller aus dem Seniorenzentrum Sonnenhof, Fußpflege groß durchgeführt.",
            {"nachname": "Keller", "heim": "Seniorenzentrum Sonnenhof"},
        ),
        (
            "Sabine Keller aus dem Seniorenzentrum Sonnenhof, Fußpflege groß durchgeführt.",
            {"vorname": "Sabine", "nachname": "Keller", "heim": "Seniorenzentrum Sonnenhof"},
        ),
        (
            "Sabine Keller, Fußpflege groß durchgeführt.",
            {"vorname": "Sabine", "nachname": "Keller"},
        ),
    ],
)
def test_ki1_returns_structured_patient_home_context(
    monkeypatch: pytest.MonkeyPatch, text: str, patient: dict[str, str]
) -> None:
    expected_result = {
        "original_text": text,
        "strukturierte_daten": {"patient": patient, "positionen": []},
    }
    fake_client = _mock_openai(monkeypatch, [expected_result])

    result = ki1_extraction.extract_treatment_text(text)

    assert result["strukturierte_daten"]["patient"] == patient
    assert fake_client.responses.calls[0]["instructions"] == SYSTEM_PROMPT


def test_ki1_prompt_instructs_home_extraction_without_inventing_a_home() -> None:
    assert '"Keller aus dem Seniorenzentrum Sonnenhof"' in SYSTEM_PROMPT
    assert '"heim": "Seniorenzentrum Sonnenhof"' in SYSTEM_PROMPT
    assert 'Wenn kein Heim genannt wird, das Feld "heim" vollständig weglassen.' in SYSTEM_PROMPT


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
    monkeypatch.setattr(ki1_extraction, "_get_openai_client", lambda: FakeOpenAIClient(["not json"]))
    invalid_json_response = client.post("/ai/extract", json={"text": "Behandlung"})

    assert missing_key_response.status_code == 503
    assert invalid_json_response.status_code == 502


def test_ki2_approves_correct_ki1_result_without_correction(monkeypatch: pytest.MonkeyPatch) -> None:
    source_text = "Peter Wagner Fußpflege groß durchgeführt."
    fake_client = _mock_openai(
        monkeypatch,
        [_extraction(), {"status": "ok", "issues": [], "summary": None}],
    )

    result = extract_and_validate(source_text)

    assert result.source_text == source_text
    assert result.correction_attempted is False
    assert result.manual_review_required is False
    assert result.ai_review_comment is None
    assert [call["model"] for call in fake_client.responses.calls] == ["gpt-4.1-mini", "gpt-4o-mini"]


def test_validated_endpoint_returns_source_data_and_review(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_text = "Peter Wagner Fußpflege groß durchgeführt."
    _mock_openai(monkeypatch, [_extraction(), {"status": "ok", "issues": [], "summary": None}])

    response = client.post("/ai/extract-and-validate", json={"text": source_text})

    assert response.status_code == 200
    assert response.json()["source_text"] == source_text
    assert response.json()["data"] == _extraction()
    assert response.json()["validation"]["status"] == "ok"
    assert response.json()["correction_attempted"] is False
    assert response.json()["manual_review_required"] is False


@pytest.mark.parametrize(
    ("source_text", "data", "review", "expected_status", "expected_issue_type"),
    [
        (
            "Peter Wagner, Fußpflege groß durchgeführt.",
            _validation_data(
                "Peter Wagner, Fußpflege groß durchgeführt.",
                [_position("Fußpflege klein", "leistung")],
            ),
            {
                "status": "correction_required",
                "issues": [
                    {
                        "field": "strukturierte_daten.positionen[0].bezeichnung",
                        "type": "contradiction",
                        "message": "Der Text nennt Fußpflege groß, nicht klein.",
                    }
                ],
                "summary": "Die Leistung wurde falsch übernommen.",
            },
            "correction_required",
            "contradiction",
        ),
        (
            "Peter Wagner, Fußpflege groß durchgeführt.",
            _validation_data(
                "Peter Wagner, Fußpflege groß durchgeführt.",
                [_position("Fußpflege groß", "leistung"), _position("Spirularin Gel", "produkt")],
            ),
            {
                "status": "correction_required",
                "issues": [
                    {
                        "field": "strukturierte_daten.positionen[1]",
                        "type": "invention",
                        "message": "Spirularin Gel kommt im Text nicht vor.",
                    }
                ],
                "summary": "Eine Position wurde erfunden.",
            },
            "correction_required",
            "invention",
        ),
        (
            "Peter Wagner, Fußpflege groß durchgeführt und Mehrarbeit.",
            _validation_data(
                "Peter Wagner, Fußpflege groß durchgeführt und Mehrarbeit.",
                [_position("Fußpflege groß", "leistung")],
            ),
            {
                "status": "correction_required",
                "issues": [
                    {
                        "field": "strukturierte_daten.positionen",
                        "type": "omission",
                        "message": "Mehrarbeit fehlt.",
                    }
                ],
                "summary": "Eine Position fehlt.",
            },
            "correction_required",
            "omission",
        ),
        (
            "Peter Wagner, Fußpflege groß durchgeführt und Mehrarbeit.",
            _validation_data(
                "Peter Wagner, Fußpflege groß durchgeführt und Mehrarbeit.",
                [_position("Fußpflege groß", "leistung"), _position("Mehrarbeit", "zusatzleistung")],
            ),
            {"status": "ok", "issues": [], "summary": "null"},
            "ok",
            None,
        ),
        (
            "Peter Wagner, Fußpflege groß durchgeführt, Mehrarbeit wegen starker Hornhaut und Spirularin Gel mitgegeben.",
            _validation_data(
                "Peter Wagner, Fußpflege groß durchgeführt, Mehrarbeit wegen starker Hornhaut und Spirularin Gel mitgegeben.",
                [
                    _position("Fußpflege groß", "leistung"),
                    _position("Mehrarbeit", "zusatzleistung"),
                    _position("Spirularin Gel", "produkt", verwendungszweck="abgabe"),
                ],
            ),
            {"status": "ok", "issues": [], "summary": None},
            "ok",
            None,
        ),
    ],
)
def test_ai_validate_endpoint_checks_supplied_ki1_output_without_running_ki1(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    source_text: str,
    data: dict[str, object],
    review: dict[str, object],
    expected_status: str,
    expected_issue_type: str | None,
) -> None:
    fake_client = FakeOpenAIClient([json.dumps(review, ensure_ascii=False)])
    monkeypatch.setattr(ki2_validation, "_get_openai_client", lambda: fake_client)
    monkeypatch.setattr(
        ki1_extraction,
        "_get_openai_client",
        lambda: pytest.fail("/ai/validate must not call KI_1"),
    )

    response = client.post("/ai/validate", json={"text": source_text, "data": data})

    assert response.status_code == 200
    assert response.json()["status"] == expected_status
    assert len(fake_client.responses.calls) == 1
    assert fake_client.responses.calls[0]["model"] == "gpt-4o-mini"
    if expected_issue_type is None:
        assert response.json()["issues"] == []
        assert response.json()["summary"] is None
    else:
        assert response.json()["issues"][0]["type"] == expected_issue_type


def test_ai_validate_endpoint_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post(
        "/ai/validate",
        json={"text": "Behandlung", "data": {}, "invoice_id": 1},
    )

    assert response.status_code == 422


def test_ki1_correction_is_rechecked_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    source_text = "Peter Wagner Fußpflege groß durchgeführt und bar bezahlt."
    fake_client = _mock_openai(
        monkeypatch,
        [
            _extraction("BANK_TRANSFER"),
            {
                "status": "correction_required",
                "issues": [{"field": "payment.method", "type": "contradiction", "message": "Barzahlung fehlt."}],
                "summary": "Zahlungsart korrigieren.",
            },
            _extraction("CASH"),
            {"status": "ok", "issues": [], "summary": None},
        ],
    )

    result = extract_and_validate(source_text)

    assert result.source_text == source_text
    assert result.data == _extraction("CASH")
    assert result.correction_attempted is True
    assert result.manual_review_required is False
    assert [call["model"] for call in fake_client.responses.calls] == [
        "gpt-4.1-mini",
        "gpt-4o-mini",
        "gpt-4.1-mini",
        "gpt-4o-mini",
    ]
    assert "Barzahlung fehlt." in str(fake_client.responses.calls[2]["input"])


def test_second_failed_review_requires_manual_review_without_third_ki1_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _mock_openai(
        monkeypatch,
        [
            _extraction("BANK_TRANSFER"),
            {
                "status": "correction_required",
                "issues": [{"field": "payment.method", "type": "contradiction", "message": "Text sagt bar."}],
                "summary": "Zahlungsart stimmt nicht.",
            },
            _extraction("CASH"),
            {
                "status": "correction_required",
                "issues": [{"field": "payment.method", "type": "ambiguity", "message": "Weiterhin unklar."}],
                "summary": "Bitte prüfen.",
            },
        ],
    )

    result = extract_and_validate("Peter Wagner Fußpflege groß durchgeführt.")

    assert result.correction_attempted is True
    assert result.manual_review_required is True
    assert result.validation.status == "manual_review_required"
    assert result.ai_review_comment is not None
    assert len(fake_client.responses.calls) == 4


def test_correction_retains_unflagged_positions_and_rechecks_the_full_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = "Peter Wagner, Fußpflege groß durchgeführt. Zwei Spirularin Gel 40 ml mitgegeben."
    foot_care = _position("Fußpflege groß", "leistung")
    gel = _position("Spirularin Gel 40 ml", "produkt", menge=2, verwendungszweck="abgabe")
    first_result = {
        "original_text": source_text,
        "strukturierte_daten": {"positionen": [foot_care, gel]},
    }
    corrected_result = {
        "original_text": source_text,
        "strukturierte_daten": {"positionen": [gel]},
    }
    fake_client = _mock_openai(
        monkeypatch,
        [
            first_result,
            {
                "status": "correction_required",
                "issues": [
                    {
                        "field": "strukturierte_daten.behandlung",
                        "type": "omission",
                        "message": "Behandlung ergänzen.",
                    },
                    {
                        "field": "strukturierte_daten.positionen[1].verwendungszweck",
                        "type": "incorrect_value",
                        "message": "Verwendungszweck prüfen.",
                    },
                ],
                "summary": "Korrektur erforderlich.",
            },
            corrected_result,
            {"status": "ok", "issues": [], "summary": None},
        ],
    )

    result = extract_and_validate(source_text, service_names=["Spirularin HF Gel 40 ml"])

    positions = result.data["strukturierte_daten"]["positionen"]
    assert result.correction_attempted is True
    assert result.manual_review_required is False
    assert foot_care in positions
    assert gel in positions
    assert "Fußpflege groß" in str(fake_client.responses.calls[3]["input"])
    assert "Spirularin Gel 40 ml" in str(fake_client.responses.calls[3]["input"])
    assert "Spirularin HF Gel 40 ml" in str(fake_client.responses.calls[1]["input"])
    assert "Spirularin HF Gel 40 ml" in str(fake_client.responses.calls[3]["input"])
    assert "Positionen, Mengen" in str(fake_client.responses.calls[2]["input"])


@pytest.mark.parametrize(
    ("source_text", "replacement_name", "revoked_name"),
    [
        (
            "Sabine Keller, Fußpflege klein durchgeführt, ich meine Fußpflege groß. Mehrarbeit gemacht.",
            "Fußpflege groß",
            "Fußpflege klein",
        ),
        (
            "Sabine Keller, Fußpflege klein durchgeführt. Korrektur: Fußpflege groß. Mehrarbeit gemacht.",
            "Fußpflege groß",
            "Fußpflege klein",
        ),
    ],
)
def test_correction_does_not_regress_an_initially_correct_self_correction(
    monkeypatch: pytest.MonkeyPatch,
    source_text: str,
    replacement_name: str,
    revoked_name: str,
) -> None:
    additional_work = _position("Mehrarbeit", "zusatzleistung")
    initially_correct = {
        "original_text": source_text,
        "strukturierte_daten": {
            "behandlung": {"art": replacement_name},
            "positionen": [_position(replacement_name, "leistung"), additional_work],
        },
    }
    regressed_correction = {
        "original_text": source_text,
        "strukturierte_daten": {
            "behandlung": {"art": revoked_name},
            "positionen": [_position(revoked_name, "leistung"), additional_work],
        },
    }
    fake_client = _mock_openai(
        monkeypatch,
        [
            initially_correct,
            {
                "status": "correction_required",
                "issues": [
                    {
                        "field": "strukturierte_daten.positionen",
                        "type": "contradiction",
                        "message": "Die Positionen erneut prüfen.",
                    }
                ],
                "summary": "Prüfung erforderlich.",
            },
            regressed_correction,
            {"status": "ok", "issues": [], "summary": None},
        ],
    )

    result = extract_and_validate(source_text)

    structured_data = result.data["strukturierte_daten"]
    assert structured_data["behandlung"]["art"] == replacement_name
    assert _position(replacement_name, "leistung") in structured_data["positionen"]
    assert additional_work in structured_data["positionen"]
    assert _position(revoked_name, "leistung") not in structured_data["positionen"]
    assert result.validation.status == "ok"
    assert result.correction_attempted is True
    assert result.manual_review_required is False
    assert result.ai_review_comment is None
    correction_input = str(fake_client.responses.calls[2]["input"])
    previous_result_input = correction_input.split("Bisheriges KI-1-Ergebnis:\n", 1)[1].split(
        "\n\nKonkrete Prüfhinweise von KI-2:", 1
    )[0]
    previous_structured_data = json.loads(previous_result_input)["strukturierte_daten"]
    assert previous_structured_data["behandlung"]["art"] == replacement_name
    assert _position(replacement_name, "leistung") in previous_structured_data["positionen"]
    assert _position(revoked_name, "leistung") not in previous_structured_data["positionen"]
    recheck_input = str(fake_client.responses.calls[3]["input"])
    recheck_structured_data = json.loads(recheck_input.split("Strukturierte Ausgabe von KI_1:\n", 1)[1])["strukturierte_daten"]
    assert recheck_structured_data["behandlung"]["art"] == replacement_name
    assert _position(replacement_name, "leistung") in recheck_structured_data["positionen"]
    assert _position(revoked_name, "leistung") not in recheck_structured_data["positionen"]


def test_second_review_of_remaining_error_requires_manual_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = "Peter Wagner, Fußpflege groß durchgeführt. Zwei Spirularin Gel 40 ml mitgegeben."
    complete_result = {
        "original_text": source_text,
        "strukturierte_daten": {
            "positionen": [
                _position("Fußpflege groß", "leistung"),
                _position("Spirularin Gel 40 ml", "produkt", menge=2, verwendungszweck="abgabe"),
            ]
        },
    }
    fake_client = _mock_openai(
        monkeypatch,
        [
            complete_result,
            {
                "status": "correction_required",
                "issues": [{"field": "zahlung", "type": "ambiguity", "message": "Zahlung prüfen."}],
                "summary": "Korrektur erforderlich.",
            },
            complete_result,
            {
                "status": "correction_required",
                "issues": [{"field": "zahlung", "type": "ambiguity", "message": "Weiterhin unklar."}],
                "summary": "Manuelle Prüfung erforderlich.",
            },
        ],
    )

    result = extract_and_validate(source_text)

    assert result.manual_review_required is True
    assert result.validation.status == "manual_review_required"
    assert len(fake_client.responses.calls) == 4


@pytest.mark.parametrize(
    ("source_text", "positions"),
    [
        (
            "Peter Wagner, Fußpflege groß durchgeführt. Mehrarbeit wegen starker Hornhaut.",
            [_position("Fußpflege groß", "leistung"), _position("Mehrarbeit", "zusatzleistung")],
        ),
        (
            "Peter Wagner, Fußpflege groß durchgeführt, Mehrarbeit wegen starker Hornhaut und Spirularin Gel mitgegeben.",
            [
                _position("Fußpflege groß", "leistung"),
                _position("Mehrarbeit", "zusatzleistung"),
                _position("Spirularin Gel", "produkt", verwendungszweck="abgabe"),
            ],
        ),
    ],
)
def test_ki2_accepts_multiple_textually_covered_positions(
    monkeypatch: pytest.MonkeyPatch, source_text: str, positions: list[dict[str, object]]
) -> None:
    extraction = {"original_text": source_text, "strukturierte_daten": {"positionen": positions}}
    fake_client = _mock_openai(
        monkeypatch,
        [extraction, {"status": "ok", "issues": [], "summary": None}],
    )

    result = extract_and_validate(source_text)

    assert result.data == extraction
    assert result.validation.status == "ok"
    assert result.correction_attempted is False
    assert len(fake_client.responses.calls) == 2


def test_ki2_review_flags_an_actual_missing_position(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _mock_openai(
        monkeypatch,
        [
            {
                "original_text": "Peter",
                "strukturierte_daten": {"positionen": [_position("Fußpflege groß", "leistung")]},
            },
            {
                "status": "correction_required",
                "issues": [{"field": "positionen", "type": "omission", "message": "Mehrarbeit fehlt."}],
                "summary": "Eine Leistung fehlt.",
            },
            {
                "original_text": "Peter",
                "strukturierte_daten": {
                    "positionen": [
                        _position("Fußpflege groß", "leistung"),
                        _position("Mehrarbeit", "zusatzleistung"),
                    ]
                },
            },
            {"status": "ok", "issues": [], "summary": None},
        ],
    )

    result = extract_and_validate("Peter Wagner, Fußpflege groß und Mehrarbeit durchgeführt.")

    assert result.correction_attempted is True
    assert "Mehrarbeit" in str(fake_client.responses.calls[2]["input"])


def test_ki2_review_flags_an_invented_additional_position(monkeypatch: pytest.MonkeyPatch) -> None:
    source_text = "Peter Wagner, Fußpflege groß durchgeführt und Mehrarbeit wegen starker Hornhaut."
    fake_client = _mock_openai(
        monkeypatch,
        [
            {
                "original_text": source_text,
                "strukturierte_daten": {
                    "positionen": [
                        _position("Fußpflege groß", "leistung"),
                        _position("Mehrarbeit", "zusatzleistung"),
                        _position("Nicht genanntes Produkt", "produkt"),
                    ]
                },
            },
            {
                "status": "correction_required",
                "issues": [
                    {
                        "field": "strukturierte_daten.positionen[2]",
                        "type": "invention",
                        "message": "Das Produkt ist im Originaltext nicht genannt.",
                    }
                ],
                "summary": "Eine Position wurde erfunden.",
            },
            {
                "original_text": source_text,
                "strukturierte_daten": {
                    "positionen": [
                        _position("Fußpflege groß", "leistung"),
                        _position("Mehrarbeit", "zusatzleistung"),
                    ]
                },
            },
            {"status": "ok", "issues": [], "summary": None},
        ],
    )

    result = extract_and_validate(source_text)

    assert result.correction_attempted is True
    assert result.validation.status == "ok"
    assert "Nicht genanntes Produkt" in str(fake_client.responses.calls[2]["input"])


def test_ki2_review_represents_an_invented_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _mock_openai(
        monkeypatch,
        [
            _extraction("CASH"),
            {
                "status": "correction_required",
                "issues": [{"field": "payment.method", "type": "invention", "message": "Barzahlung ist nicht belegt."}],
                "summary": "Zahlungsinformation entfernen.",
            },
            _extraction(),
            {"status": "ok", "issues": [], "summary": None},
        ],
    )

    result = extract_and_validate("Peter Wagner, Fußpflege groß durchgeführt.")

    assert result.data == _extraction()
    assert "Barzahlung ist nicht belegt." in str(fake_client.responses.calls[2]["input"])


def test_ki2_zero_shot_prompt_and_technical_errors_are_not_manual_reviews(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "BEISPIEL 1" in SYSTEM_PROMPT
    assert "Max Mustermann" not in KI2_SYSTEM_PROMPT
    assert "BEISPIEL" not in KI2_SYSTEM_PROMPT
    assert "X, nein Y" not in KI2_SYSTEM_PROMPT
    assert "Bewerte keine Abrechnungslogik." in KI2_SYSTEM_PROMPT
    assert "zusammengefasst oder getrennt" in KI2_SYSTEM_PROMPT
    assert '"mitgegeben" bedeutet "abgabe"' in KI2_SYSTEM_PROMPT
    assert "aktiven Kontext" in KI2_SYSTEM_PROMPT

    fake_client = FakeOpenAIClient([json.dumps(_extraction()), "not valid json"])
    monkeypatch.setattr(ki1_extraction, "_get_openai_client", lambda: fake_client)
    monkeypatch.setattr(ki2_validation, "_get_openai_client", lambda: fake_client)

    with pytest.raises(ki2_validation.AIValidationError):
        extract_and_validate("Peter Wagner Fußpflege groß durchgeführt.")

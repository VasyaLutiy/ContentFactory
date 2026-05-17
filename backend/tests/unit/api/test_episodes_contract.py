def _beat_payload(**overrides):
    payload = {
        "start": 0.1,
        "end": 1.2,
        "text": "Hook text",
        "safe_area": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.2},
    }
    payload.update(overrides)
    return payload


def test_validate_text_beats_returns_expected_contract_for_valid_payload(client) -> None:
    response = client.post(
        "/api/v1/episodes/validate-text-beats",
        json={"beats": [_beat_payload()]},
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "issues": []}


def test_validate_text_beats_returns_business_issue_for_empty_beats(client) -> None:
    response = client.post(
        "/api/v1/episodes/validate-text-beats",
        json={"beats": []},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["issues"][0]["code"] == "VALIDATION_NO_TEXT_BEATS"


def test_validate_text_beats_flags_outside_frame_safe_area(client) -> None:
    response = client.post(
        "/api/v1/episodes/validate-text-beats",
        json={
            "beats": [
                _beat_payload(
                    safe_area={"x": 0.8, "y": 0.1, "width": 0.3, "height": 0.2},
                )
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any(issue["code"] == "VALIDATION_TEXT_OUTSIDE_SAFE_AREA" for issue in body["issues"])


def test_validate_text_beats_rejects_invalid_schema_with_422(client) -> None:
    response = client.post(
        "/api/v1/episodes/validate-text-beats",
        json={"beats": [{"start": 0.0, "end": 1.0, "text": ""}]},
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error["loc"][-1] == "text" for error in errors)


def test_validate_text_beats_allows_no_text_experiment_flag(client) -> None:
    response = client.post(
        "/api/v1/episodes/validate-text-beats",
        json={"beats": [], "no_text_experiment": True},
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "issues": []}

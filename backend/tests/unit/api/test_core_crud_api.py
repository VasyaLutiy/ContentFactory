def test_campaign_crud_success_path(client) -> None:
    created = client.post(
        "/api/v1/campaigns",
        json={"name": "Launch", "description": "First campaign"},
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["name"] == "Launch"

    campaign_id = payload["id"]
    fetched = client.get(f"/api/v1/campaigns/{campaign_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == campaign_id


def test_campaign_not_found_failure_path(client) -> None:
    response = client.get("/api/v1/campaigns/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Campaign not found"


def test_text_beat_validation_endpoint_still_available(client) -> None:
    response = client.post(
        "/api/v1/episodes/validate-text-beats",
        json={
            "beats": [
                {
                    "start": 0.3,
                    "end": 1.7,
                    "text": "Hook text",
                    "style_preset": "hook_default",
                    "safe_area": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.2},
                    "priority": 0,
                }
            ],
            "no_text_experiment": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True

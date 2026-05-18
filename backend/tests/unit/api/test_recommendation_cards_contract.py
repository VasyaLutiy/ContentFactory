def test_recommendation_cards_contract_supports_multiple_export_ids(client) -> None:
    campaign = client.post("/api/v1/campaigns", json={"name": "Launch"}).json()
    export_a = client.post(
        "/api/v1/exports",
        json={
            "campaign_id": campaign["id"],
            "platform": "tiktok",
            "metadata": {
                "variant_label": "Hook-A",
                "text_beats": [{"start": 0.1, "end": 0.8, "text": "Start here", "style_preset": "hook_default"}]
            },
        },
    ).json()
    export_b = client.post(
        "/api/v1/exports",
        json={"campaign_id": campaign["id"], "platform": "tiktok"},
    ).json()

    client.post(
        "/api/v1/analytics/snapshots",
        json={
            "export_id": export_a["id"],
            "campaign_id": campaign["id"],
            "video_id": "v-a",
            "snapshot_at": "2026-05-18T12:34:56Z",
            "avg_watch_seconds": 7.2,
            "full_watch_percent": 61.0,
            "retention_note": "Strong hold through second one",
        },
    )
    client.post(
        "/api/v1/analytics/snapshots",
        json={
            "export_id": export_b["id"],
            "campaign_id": campaign["id"],
            "video_id": "v-b",
            "snapshot_at": "2026-05-18T12:34:56Z",
            "avg_watch_seconds": 3.1,
            "full_watch_percent": 28.0,
            "retention_note": "drop at 0:01",
        },
    )

    response = client.get(
        "/api/v1/analytics/recommendation-cards",
        params=[
            ("campaign_id", campaign["id"]),
            ("export_id", export_a["id"]),
            ("export_id", export_b["id"]),
        ],
    )

    assert response.status_code == 200
    cards = response.json()
    assert [card["export_id"] for card in cards] == [export_a["id"], export_b["id"]]
    assert cards[0]["export_ids"] == [export_a["id"]]
    assert cards[0]["variant_label"] == "Hook-A"
    assert cards[0]["confidence"] == "high"
    assert cards[0]["reason"] == "Top-performing variant by latest watch-time and completion metrics."
    assert cards[0]["evidence"]
    assert cards[0]["suggested_next_hook"]
    assert cards[0]["suggested_next_edit"]
    assert cards[0]["on_screen_text_beats"][0]["text"] == "Start here"
    assert cards[0]["warnings"] == []
    assert cards[1]["reason"] == "Underperforming variant by latest watch-time and completion metrics."
    assert cards[1]["warnings"] == ["Missing on-screen text beats in export metadata and episode scenes."]


def test_recommendation_cards_contract_can_use_campaign_exports_without_explicit_filter(client) -> None:
    campaign = client.post("/api/v1/campaigns", json={"name": "Launch"}).json()
    export = client.post(
        "/api/v1/exports",
        json={"campaign_id": campaign["id"], "platform": "tiktok"},
    ).json()

    response = client.get(
        "/api/v1/analytics/recommendation-cards",
        params={"campaign_id": campaign["id"]},
    )

    assert response.status_code == 200
    assert [card["export_id"] for card in response.json()] == [export["id"]]


def test_recommendation_cards_contract_rejects_unknown_export_filter(client) -> None:
    campaign = client.post("/api/v1/campaigns", json={"name": "Launch"}).json()

    response = client.get(
        "/api/v1/analytics/recommendation-cards",
        params=[("campaign_id", campaign["id"]), ("export_id", 999999)],
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Exports not found in campaign: 999999"

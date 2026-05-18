from __future__ import annotations


def test_tiktok_analytics_ingest_legacy_json_writes_snapshot_and_attaches_export(client) -> None:
    campaign = client.post("/api/v1/campaigns", json={"name": "Launch"}).json()
    export = client.post(
        "/api/v1/exports",
        json={"campaign_id": campaign["id"], "platform": "tiktok"},
    ).json()

    response = client.post(
        "/api/v1/analytics/tiktok/ingest",
        json={
            "export_id": export["id"],
            "source_json_asset_id": None,
            "screenshot_asset_id": None,
            "legacy_json": {
                "video_id": "7639445229749259540",
                "scraped_at": "2026-05-18T12:34:56Z",
                "kpis": {
                    "Video views": "1,234",
                    "Total play time": "0h:04m:38s",
                    "Average watch time": "3.4s",
                    "Watched full video": "42%",
                },
                "retention_note": "Most viewers stopped watching at 0:01",
            },
        },
    )

    assert response.status_code == 201
    snapshot = response.json()
    assert snapshot["export_id"] == export["id"]
    assert snapshot["campaign_id"] == campaign["id"]
    assert snapshot["video_id"] == "7639445229749259540"
    assert snapshot["views"] == 1234
    assert snapshot["views_est"] == 1234
    assert snapshot["total_play_seconds"] == 278
    assert snapshot["avg_watch_seconds"] == 3.4
    assert snapshot["full_watch_percent"] == 42.0
    assert snapshot["retention_note"] == "Most viewers stopped watching at 0:01"

    fetched_export = client.get(f"/api/v1/exports/{export['id']}").json()
    assert fetched_export["tiktok_video_id"] == "7639445229749259540"


def test_tiktok_analytics_ingest_summary_row_and_list_filter(client) -> None:
    campaign = client.post("/api/v1/campaigns", json={"name": "Launch"}).json()
    export = client.post(
        "/api/v1/exports",
        json={
            "campaign_id": campaign["id"],
            "platform": "tiktok",
            "tiktok_video_id": "7639445229749259541",
        },
    ).json()

    response = client.post(
        "/api/v1/analytics/tiktok/ingest",
        json={
            "export_id": export["id"],
            "summary_row": {
                "video_id": "7639445229749259541",
                "scraped_at": "2026-05-18T12:35:56Z",
                "Video views": "1.2M",
                "Total play time": "1h:02m:03s",
                "Average watch time": "0:07",
                "Watched full video": "51.5%",
                "retention_note": "",
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["views"] is None
    assert response.json()["views_est"] == 1_200_000

    listed = client.get("/api/v1/analytics/snapshots", params={"export_id": export["id"]})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [response.json()["id"]]


def test_tiktok_analytics_ingest_requires_single_legacy_source(client) -> None:
    response = client.post(
        "/api/v1/analytics/tiktok/ingest",
        json={"export_id": 1},
    )

    assert response.status_code == 422


def test_tiktok_analytics_ingest_rejects_video_id_mismatch(client) -> None:
    campaign = client.post("/api/v1/campaigns", json={"name": "Launch"}).json()
    export = client.post(
        "/api/v1/exports",
        json={
            "campaign_id": campaign["id"],
            "platform": "tiktok",
            "tiktok_video_id": "111",
        },
    ).json()

    response = client.post(
        "/api/v1/analytics/tiktok/ingest",
        json={
            "export_id": export["id"],
            "legacy_json": {
                "video_id": "222",
                "scraped_at": "2026-05-18T12:34:56Z",
                "kpis": {"Video views": "10"},
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "TikTok analytics snapshot video ID does not match export."


def test_create_snapshot_rejects_campaign_mismatch(client) -> None:
    first_campaign = client.post("/api/v1/campaigns", json={"name": "First"}).json()
    second_campaign = client.post("/api/v1/campaigns", json={"name": "Second"}).json()
    export = client.post(
        "/api/v1/exports",
        json={"campaign_id": first_campaign["id"], "platform": "tiktok"},
    ).json()

    response = client.post(
        "/api/v1/analytics/snapshots",
        json={
            "export_id": export["id"],
            "campaign_id": second_campaign["id"],
            "video_id": "7639445229749259540",
            "snapshot_at": "2026-05-18T12:34:56Z",
            "views": 10,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Analytics snapshot campaign does not match export"

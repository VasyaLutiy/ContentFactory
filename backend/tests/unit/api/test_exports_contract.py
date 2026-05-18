from __future__ import annotations


def test_exports_contract_create_attach_and_filter(client) -> None:
    campaign = client.post("/api/v1/campaigns", json={"name": "Launch"}).json()

    created = client.post(
        "/api/v1/exports",
        json={
            "campaign_id": campaign["id"],
            "platform": "tiktok",
            "render_job_id": "render-001",
            "metadata": {"slot": "hook-a"},
        },
    )
    assert created.status_code == 201
    export = created.json()
    assert export["campaign_id"] == campaign["id"]
    assert export["platform"] == "tiktok"
    assert export["tiktok_video_id"] is None
    assert export["metadata"] == {"slot": "hook-a"}

    updated = client.put(
        f"/api/v1/exports/{export['id']}/tiktok-video",
        json={"tiktok_video_id": "7639445229749259540"},
    )
    assert updated.status_code == 200
    assert updated.json()["tiktok_video_id"] == "7639445229749259540"

    listed = client.get(
        "/api/v1/exports",
        params={"campaign_id": campaign["id"], "render_job_id": "render-001"},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [export["id"]]


def test_export_not_found_contract(client) -> None:
    response = client.get("/api/v1/exports/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Export not found"

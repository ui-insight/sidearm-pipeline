"""API coverage for deployment-wide shared workspace views."""

from datetime import UTC, datetime, timedelta

from app.models.workspace_view import WorkspaceView

SEASON_PARAMS = {
    "season": "2025-26",
    "stat": "points",
    "scope": "conference",
    "opponent": "all",
    "limit": "10",
}


async def test_shared_workspace_view_create_list_and_delete(client):
    created = await client.post(
        "/api/v1/workspace-views",
        json={"name": "Conference scoring", "view": "season", "params": SEASON_PARAMS},
    )

    assert created.status_code == 201
    assert created.json() == {
        "id": created.json()["id"],
        "name": "Conference scoring",
        "view": "season",
        "params": SEASON_PARAMS,
        "created_by": "prototype",
        "created_at": created.json()["created_at"],
    }

    listed = await client.get("/api/v1/workspace-views")
    assert listed.status_code == 200
    assert listed.json() == [created.json()]

    deleted = await client.delete(f"/api/v1/workspace-views/{created.json()['id']}")
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/workspace-views")).json() == []

    missing = await client.delete(f"/api/v1/workspace-views/{created.json()['id']}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Workspace view not found"}

    invalid_id = await client.delete("/api/v1/workspace-views/not-a-uuid")
    assert invalid_id.status_code == 422


async def test_comparison_workspace_view_accepts_the_exact_filter_shape(client):
    params = {
        "season": "2025-26",
        "stat": "points",
        "conference": "all",
        "venue": "home",
        "opponent": "Montana",
        "left": "4",
        "right": "8",
    }

    response = await client.post(
        "/api/v1/workspace-views",
        json={"name": "Player handoff", "view": "comparison", "params": params},
    )

    assert response.status_code == 201
    assert response.json()["view"] == "comparison"
    assert response.json()["params"] == params


async def test_shared_workspace_views_are_newest_first_and_bounded(
    client,
    db_session,
):
    base_time = datetime(2026, 7, 17, 12, tzinfo=UTC)
    db_session.add_all(
        [
            WorkspaceView(
                id=f"{index:036d}",
                name=f"View {index}",
                view_kind="season",
                params=SEASON_PARAMS,
                created_by="prototype",
                created_at=base_time + timedelta(minutes=index),
            )
            for index in range(101)
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/workspace-views")

    assert response.status_code == 200
    assert len(response.json()) == 100
    assert response.json()[0]["name"] == "View 100"
    assert response.json()[-1]["name"] == "View 1"


async def test_shared_workspace_view_validates_names_and_filter_shapes(client):
    invalid_payloads = [
        {"name": "   ", "view": "season", "params": SEASON_PARAMS},
        {
            "name": "Incomplete",
            "view": "season",
            "params": {
                key: value for key, value in SEASON_PARAMS.items() if key != "limit"
            },
        },
        {
            "name": "Unknown filter",
            "view": "season",
            "params": {**SEASON_PARAMS, "admin": "true"},
        },
        {
            "name": "Oversized value",
            "view": "season",
            "params": {**SEASON_PARAMS, "stat": "x" * 161},
        },
    ]

    for payload in invalid_payloads:
        response = await client.post("/api/v1/workspace-views", json=payload)
        assert response.status_code == 422

    assert (await client.get("/api/v1/workspace-views")).json() == []

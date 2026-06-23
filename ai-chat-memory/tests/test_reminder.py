import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_create_reminder(client):
    resp = await client.post(
        "/api/v1/reminders",
        json={
            "user_id": "ru1",
            "message": "test reminder",
            "remind_at": "2026-06-23T15:00:00",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["message"] == "test reminder"


@pytest.mark.asyncio
async def test_get_reminders_today(client):
    resp = await client.get("/api/v1/reminders/ru1")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_mark_reminder_shown(client):
    resp = await client.post(
        "/api/v1/reminders",
        json={
            "user_id": "ru2",
            "message": "shown test",
            "remind_at": "2026-06-23T16:00:00",
        },
    )
    rid = resp.json()["id"]
    shown = await client.put(f"/api/v1/reminders/{rid}/shown")
    assert shown.status_code == 200
    assert "ok" in shown.text


@pytest.mark.asyncio
async def test_delete_reminder(client):
    resp = await client.post(
        "/api/v1/reminders",
        json={
            "user_id": "ru3",
            "message": "delete test",
            "remind_at": "2026-06-23T17:00:00",
        },
    )
    rid = resp.json()["id"]
    del_resp = await client.delete(f"/api/v1/reminders/{rid}")
    assert del_resp.status_code == 200
    assert "deleted" in del_resp.text


@pytest.mark.asyncio
async def test_reminder_empty_user(client):
    resp = await client.get("/api/v1/reminders/nouser")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []

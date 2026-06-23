import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_chat_streaming(client):
    resp = await client.post(
        "/api/v1/chat",
        json={"user_id": "test1", "conversation_id": "c1", "message": "halo"},
    )
    assert resp.status_code == 200
    text = resp.text
    assert len(text) > 0
    assert "halo" in text.lower() or "Halo" in text or "Hai" in text or "hai" in text.lower()


@pytest.mark.asyncio
async def test_create_user(client):
    resp = await client.post("/api/v1/users", params={"username": "testuser"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["username"] == "testuser"


@pytest.mark.asyncio
async def test_get_user(client):
    await client.post("/api/v1/users", params={"username": "getuser"})
    resp = await client.get("/api/v1/users/getuser")
    assert resp.status_code in (200,)
    data = resp.json()
    assert data["username"] == "getuser"


@pytest.mark.asyncio
async def test_conversations_list(client):
    resp = await client.get("/api/v1/conversations/test1")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_messages(client):
    resp = await client.get("/api/v1/conversations/c1/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_delete_conversation(client):
    resp = await client.delete("/api/v1/conversations/nonexistent")
    assert resp.status_code == 200
    assert "deleted" in resp.text


@pytest.mark.asyncio
async def test_delete_message(client):
    resp = await client.delete("/api/v1/messages/nonexistent")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_vote_message(client):
    resp = await client.post("/api/v1/messages/nonexistent/vote", json={"vote": "up"})
    assert resp.status_code == 200
    assert "voted" in resp.text


@pytest.mark.asyncio
async def test_export_conversation(client):
    resp = await client.get("/api/v1/conversations/c1/export")
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_root_redirect(client):
    resp = await client.get("/", follow_redirects=False)
    assert resp.status_code in (307,)


@pytest.mark.asyncio
async def test_favicon(client):
    resp = await client.get("/favicon.ico")
    assert resp.status_code == 200

import pytest


@pytest.mark.asyncio
async def test_memory_ingat_command(client):
    resp = await client.post(
        "/api/v1/chat",
        json={"user_id": "mu1", "conversation_id": "mc1", "message": "ingat bahwa aku suka kopi"},
    )
    assert resp.status_code == 200
    assert "simpan" in resp.text.lower() or "Disimpan" in resp.text


@pytest.mark.asyncio
async def test_memory_ganti_namaku(client):
    resp = await client.post(
        "/api/v1/chat",
        json={"user_id": "mu1", "conversation_id": "mc1", "message": "ganti namaku Budi"},
    )
    assert resp.status_code == 200
    assert "kenal" in resp.text.lower() or "Budi" in resp.text


@pytest.mark.asyncio
async def test_memory_ganti_namamu(client):
    resp = await client.post(
        "/api/v1/chat",
        json={"user_id": "mu1", "conversation_id": "mc1", "message": "ganti namamu Siska"},
    )
    assert resp.status_code == 200
    assert "Siska" in resp.text or "siska" in resp.text


@pytest.mark.asyncio
async def test_memory_list(client):
    resp = await client.get("/api/v1/memory/mu1")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_memory_teach(client):
    resp = await client.post(
        "/api/v1/memory/mu1/teach",
        json={"type": "personal", "key": "hobi", "value": "membaca"},
    )
    assert resp.status_code == 200
    assert "learned" in resp.text


@pytest.mark.asyncio
async def test_memory_forget(client):
    resp = await client.get("/api/v1/memory/mu1")
    facts = resp.json()
    if facts:
        fid = facts[0]["id"]
        del_resp = await client.delete(f"/api/v1/memory/mu1/{fid}")
        assert del_resp.status_code == 200
        assert "forgotten" in del_resp.text


@pytest.mark.asyncio
async def test_memory_lupa_command(client):
    resp = await client.post(
        "/api/v1/chat",
        json={"user_id": "mu1", "conversation_id": "mc1", "message": "lupa kopi"},
    )
    assert resp.status_code == 200
    assert "Dihapus" in resp.text or "dihapus" in resp.text or "Nem" in resp.text or "nemu" in resp.text


@pytest.mark.asyncio
async def test_memory_update_command(client):
    resp = await client.post(
        "/api/v1/chat",
        json={"user_id": "mu1", "conversation_id": "mc1", "message": "ingat hutang 50000"},
    )
    assert resp.status_code == 200
    resp2 = await client.post(
        "/api/v1/chat",
        json={"user_id": "mu1", "conversation_id": "mc1", "message": "ingat hutang 75000"},
    )
    assert resp2.status_code == 200
    assert "Diperbaharui" in resp2.text or "diperbaharui" in resp2.text or "Disimpan" in resp2.text

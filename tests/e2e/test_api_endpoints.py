import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_version(client: AsyncClient):
    resp = await client.get("/v1/version")
    assert resp.status_code == 200
    assert "version" in resp.json()

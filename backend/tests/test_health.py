import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "email_configured" in body
    assert isinstance(body["email_configured"], bool)


@pytest.mark.asyncio
async def test_openapi(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert "CommercialBrainz" in response.json()["info"]["title"]

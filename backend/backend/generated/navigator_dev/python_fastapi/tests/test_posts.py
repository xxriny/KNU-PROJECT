import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_get_posts():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/posts?page=1&limit=10")
        assert response.status_code == 200
        assert "data" in response.json()
from fastapi.testclient import TestClient


def test_health_returns_200():
    from src.api.main import app

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

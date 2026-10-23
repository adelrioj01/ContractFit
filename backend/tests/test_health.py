from fastapi.testclient import TestClient

from contractfit.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_vertical_slice() -> None:
    assert client.post("/api/demo/reset").status_code == 201
    opportunities = client.get("/api/opportunities").json()
    matches = client.get("/api/matches").json()
    evaluation = client.get("/api/evaluation").json()

    assert len(opportunities) == 1
    assert matches[0]["eligibility"] == "eligible"
    assert matches[0]["gates"][0]["evidence"]["supporting_text"]
    assert evaluation["eligibility_accuracy"] == 1

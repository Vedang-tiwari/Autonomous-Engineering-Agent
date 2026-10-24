import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db

# Initialize database schema for tests
init_db()

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"

def test_root():
    res = client.get("/")
    assert res.status_code == 200
    assert "Autonomous Engineering Agent" in res.json()["service"]

def test_create_and_get_task():
    payload = {
        "repository": "https://github.com/example/demo-repo",
        "task": "Fix the failing authentication tests and add regression assertions.",
        "require_human_approval": False
    }
    create_res = client.post("/api/tasks", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    assert "task_id" in data
    task_id = data["task_id"]

    get_res = client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == 200
    task_data = get_res.json()
    assert task_data["task_id"] == task_id
    assert task_data["repository"] == payload["repository"]

def test_list_tasks():
    res = client.get("/api/tasks")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

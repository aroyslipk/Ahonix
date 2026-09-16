"""Unit tests for workspace management (creation, listing, selection, and deletion)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
import pytest
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from auth import get_current_user
from server import app, db


@pytest.fixture
def mock_user():
    return {
        "user_id": "usr_test_alpha",
        "email": "owner@brand.com",
        "name": "Brand Owner",
        "active_workspace_id": "ws_1",
    }


@pytest.fixture(autouse=True)
def cleanup():
    yield
    app.dependency_overrides.clear()


def test_google_auth_status():
    client = TestClient(app)
    res = client.get("/api/auth/google/status")
    assert res.status_code == 200
    assert "configured" in res.json()


def test_create_real_workspace(mock_user, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_workspaces = MagicMock()
    mock_workspaces.insert_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    mock_workspace_data = MagicMock()
    mock_workspace_data.insert_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    mock_users = MagicMock()
    mock_users.update_one = AsyncMock(return_value=MagicMock(acknowledged=True))

    monkeypatch.setattr(db, "workspaces", mock_workspaces)
    monkeypatch.setattr(db, "workspace_data", mock_workspace_data)
    monkeypatch.setattr(db, "users", mock_users)

    client = TestClient(app)
    payload = {
        "name": "Apex Athletics",
        "business_type": "DTC Brand",
        "currency": "USD",
        "mode": "real",
        "channels": ["Shopify"],
    }
    res = client.post("/api/workspaces", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Apex Athletics"
    assert data["is_demo"] is False
    assert mock_workspaces.insert_one.called
    assert mock_workspace_data.insert_one.called


def test_delete_workspace_success(mock_user, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_workspaces = MagicMock()
    # User owns 2 workspaces, so deletion of 1 is allowed
    mock_workspaces.find_one = AsyncMock(side_effect=[
        {"workspace_id": "ws_1", "user_id": "usr_test_alpha", "name": "Duplicate Workspace"},
        {"workspace_id": "ws_2", "user_id": "usr_test_alpha", "name": "Primary Store"},
    ])
    mock_workspaces.count_documents = AsyncMock(return_value=2)
    mock_workspaces.delete_one = AsyncMock(return_value=MagicMock(acknowledged=True))

    mock_workspace_data = MagicMock()
    mock_workspace_data.delete_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    mock_shopify = MagicMock()
    mock_shopify.delete_many = AsyncMock(return_value=MagicMock(acknowledged=True))
    mock_meta = MagicMock()
    mock_meta.delete_many = AsyncMock(return_value=MagicMock(acknowledged=True))
    mock_google = MagicMock()
    mock_google.delete_many = AsyncMock(return_value=MagicMock(acknowledged=True))
    mock_stripe = MagicMock()
    mock_stripe.delete_many = AsyncMock(return_value=MagicMock(acknowledged=True))
    mock_subs = MagicMock()
    mock_subs.delete_many = AsyncMock(return_value=MagicMock(acknowledged=True))
    mock_states = MagicMock()
    mock_states.delete_many = AsyncMock(return_value=MagicMock(acknowledged=True))

    mock_users = MagicMock()
    mock_users.update_one = AsyncMock(return_value=MagicMock(acknowledged=True))

    monkeypatch.setattr(db, "workspaces", mock_workspaces)
    monkeypatch.setattr(db, "workspace_data", mock_workspace_data)
    monkeypatch.setattr(db, "shopify_connections", mock_shopify)
    monkeypatch.setattr(db, "meta_connections", mock_meta)
    monkeypatch.setattr(db, "google_connections", mock_google)
    monkeypatch.setattr(db, "stripe_merchant_connections", mock_stripe)
    monkeypatch.setattr(db, "subscriptions", mock_subs)
    monkeypatch.setattr(db, "shopify_oauth_states", mock_states)
    monkeypatch.setattr(db, "users", mock_users)

    client = TestClient(app)
    res = client.delete("/api/workspaces/ws_1")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["deleted_workspace_id"] == "ws_1"
    assert data["active_workspace_id"] == "ws_2"
    assert mock_workspaces.delete_one.called


def test_delete_only_workspace_rejected(mock_user, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_workspaces = MagicMock()
    mock_workspaces.find_one = AsyncMock(return_value={"workspace_id": "ws_1", "user_id": "usr_test_alpha"})
    mock_workspaces.count_documents = AsyncMock(return_value=1)

    monkeypatch.setattr(db, "workspaces", mock_workspaces)

    client = TestClient(app)
    res = client.delete("/api/workspaces/ws_1")
    assert res.status_code == 400
    assert "Cannot delete your only workspace" in res.json()["detail"]

"""Unit and integration tests for Stripe Merchant Store Connector."""
import sys
from pathlib import Path
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import stripe_integration
from auth import get_current_user
from server import app


@pytest.fixture
def mock_user_and_workspace():
    user = {
        "user_id": "usr_test_123",
        "email": "merchant@northstargoods.com",
        "name": "Northstar Merchant",
        "active_workspace_id": "ws_test_456",
    }
    workspace = {
        "workspace_id": "ws_test_456",
        "user_id": "usr_test_123",
        "name": "Northstar Goods",
        "currency": "USD",
        "is_demo": True,
        "created_at": "2026-09-01T00:00:00Z",
    }
    return user, workspace


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.stripe_merchant_connections = MagicMock()
    db.stripe_merchant_connections.find_one = AsyncMock(return_value=None)
    db.stripe_merchant_connections.update_one = AsyncMock(return_value=MagicMock(acknowledged=True))

    db.workspace_data = MagicMock()
    initial_workspace_data = {
        "workspace_id": "ws_test_456",
        "profit": {
            "gross_revenue": 50000.0,
            "steps": [
                {"label": "Gross Revenue", "value": 50000.0, "type": "total"},
                {"label": "COGS", "value": -15000.0, "type": "cost"},
                {"label": "Shipping", "value": -3000.0, "type": "cost"},
                {"label": "Advertising", "value": -8000.0, "type": "cost"},
                {"label": "Payment Fees", "value": -1450.0, "type": "cost"},
                {"label": "True Profit", "value": 22550.0, "type": "result"},
            ],
            "true_profit": 22550.0,
            "margin": 45.1,
        },
        "sales": {
            "orders": 500,
        },
        "channels": {
            "payments": {
                "total_fees": 1450.0,
                "avg_fee_pct": 2.9,
            }
        },
    }
    db.workspace_data.find_one = AsyncMock(return_value=initial_workspace_data)
    db.workspace_data.update_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    return db


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def test_merchant_status_disconnected(mock_user_and_workspace, mock_db):
    user, ws = mock_user_and_workspace
    stripe_integration.init_stripe(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    res = client.get("/api/integrations/stripe/status")
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is False
    assert data["workspace_id"] == "ws_test_456"


def test_merchant_connect_sandbox(mock_user_and_workspace, mock_db):
    user, ws = mock_user_and_workspace
    stripe_integration.init_stripe(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    payload = {"mode": "sandbox"}
    res = client.post("/api/integrations/stripe/connect", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["connected"] is True
    assert data["mode"] == "sandbox"
    assert mock_db.stripe_merchant_connections.update_one.called


def test_merchant_sync_fees(mock_user_and_workspace, mock_db):
    user, ws = mock_user_and_workspace
    mock_db.stripe_merchant_connections.find_one = AsyncMock(return_value={
        "workspace_id": "ws_test_456",
        "connected": True,
        "mode": "sandbox",
        "account_id": "acct_test_123",
    })

    stripe_integration.init_stripe(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    res = client.post("/api/integrations/stripe/sync", json={"days": 30})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["synced"] is True
    assert data["total_fees"] > 0
    assert mock_db.workspace_data.update_one.called


def test_merchant_disconnect(mock_user_and_workspace, mock_db):
    user, ws = mock_user_and_workspace
    stripe_integration.init_stripe(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    res = client.post("/api/integrations/stripe/disconnect")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["disconnected"] is True
    assert mock_db.stripe_merchant_connections.update_one.called

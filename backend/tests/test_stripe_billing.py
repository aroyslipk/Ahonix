"""Unit and integration tests for Stripe SaaS Subscription Billing Module."""
import sys
from pathlib import Path
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import billing
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
        "is_demo": False,
        "created_at": "2026-09-01T00:00:00Z",
    }
    return user, workspace


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.subscriptions = MagicMock()
    db.subscriptions.find_one = AsyncMock(return_value=None)
    db.subscriptions.update_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    db.subscriptions.update_many = AsyncMock(return_value=MagicMock(acknowledged=True))
    return db


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def test_list_plans():
    client = TestClient(app)
    res = client.get("/api/billing/plans")
    assert res.status_code == 200
    data = res.json()
    assert "plans" in data
    assert len(data["plans"]) == 3
    plan_ids = [p["id"] for p in data["plans"]]
    assert "starter" in plan_ids
    assert "growth" in plan_ids
    assert "enterprise" in plan_ids

    starter = next(p for p in data["plans"] if p["id"] == "starter")
    assert starter["monthly_price"] == 49
    assert starter["annual_price"] == 39
    assert len(starter["features"]) > 0


def test_get_subscription_status_default_trial(mock_user_and_workspace, mock_db):
    user, ws = mock_user_and_workspace
    billing.init_billing(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    res = client.get("/api/billing/status")
    assert res.status_code == 200
    data = res.json()
    assert data["workspace_id"] == "ws_test_456"
    assert data["plan_id"] == "growth"
    assert data["status"] in ("trialing", "active")
    assert "features" in data


def test_create_checkout_session_sandbox(mock_user_and_workspace, mock_db, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    user, ws = mock_user_and_workspace
    billing.init_billing(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    payload = {"plan_id": "growth", "interval": "month"}
    res = client.post("/api/billing/create-checkout-session", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "sandbox"
    assert "checkout_url" in data
    assert "sandbox_activated" in data["checkout_url"]
    assert mock_db.subscriptions.update_one.called


def test_create_checkout_session_invalid_plan(mock_user_and_workspace, mock_db):
    user, ws = mock_user_and_workspace
    billing.init_billing(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    payload = {"plan_id": "unlimited_super_plan", "interval": "month"}
    res = client.post("/api/billing/create-checkout-session", json=payload)
    assert res.status_code == 400


def test_create_checkout_session_live_mode(mock_user_and_workspace, mock_db, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake_secret_key_123")
    user, ws = mock_user_and_workspace
    billing.init_billing(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_live_123"
    mock_session.id = "cs_test_live_123"

    mock_customer = MagicMock()
    mock_customer.id = "cus_test_merchant_123"

    with patch("stripe.Customer.create", return_value=mock_customer), \
         patch("stripe.checkout.Session.create", return_value=mock_session):
        client = TestClient(app)
        payload = {"plan_id": "starter", "interval": "year"}
        res = client.post("/api/billing/create-checkout-session", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "live"
        assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_live_123"
        assert data["session_id"] == "cs_test_live_123"


def test_customer_portal_sandbox(mock_user_and_workspace, mock_db, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    user, ws = mock_user_and_workspace
    billing.init_billing(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    res = client.post("/api/billing/customer-portal", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "sandbox"
    assert "portal_url" in data


def test_sandbox_upgrade_direct(mock_user_and_workspace, mock_db):
    user, ws = mock_user_and_workspace
    billing.init_billing(mock_db, AsyncMock(return_value=ws))
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    payload = {"plan_id": "enterprise", "interval": "year"}
    res = client.post("/api/billing/sandbox-upgrade", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["plan_id"] == "enterprise"
    assert data["interval"] == "year"
    assert mock_db.subscriptions.update_one.called


def test_webhook_checkout_session_completed(mock_db):
    billing.init_billing(mock_db, AsyncMock())

    webhook_payload = {
        "id": "evt_test_checkout_completed",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_789",
                "customer": "cus_test_123",
                "subscription": "sub_test_456",
                "client_reference_id": "ws_test_456",
                "metadata": {
                    "workspace_id": "ws_test_456",
                    "plan_id": "growth",
                    "interval": "annual",
                },
            }
        },
    }

    client = TestClient(app)
    res = client.post(
        "/api/billing/webhook",
        json=webhook_payload,
    )
    assert res.status_code == 200
    assert res.json()["received"] is True
    assert mock_db.subscriptions.update_one.called

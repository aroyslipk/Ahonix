"""Unit tests for Production Hardening Phase 1 changes.
These tests run in-process without requiring an active cloud sandbox.
"""
import sys
import os
import pytest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from rate_limit import check_rate_limit, make_rate_limiter
from auth import RegisterBody, LoginBody, ResetBody, _is_production
from server import AskBody, SimBody, ActionOp, CreateWorkspace, app
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.testclient import TestClient


class TestRateLimiter:
    def test_rate_limit_allows_under_threshold(self):
        key = "unit_test_allowed"
        # Should allow 3 calls within 10 seconds
        for _ in range(3):
            check_rate_limit(key, max_calls=3, window_seconds=10)

    def test_rate_limit_blocks_exceeded(self):
        key = "unit_test_blocked"
        for _ in range(2):
            check_rate_limit(key, max_calls=2, window_seconds=10)
        
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(key, max_calls=2, window_seconds=10)
        
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers
        assert "Too many requests" in exc_info.value.detail


class TestAuthValidation:
    def test_register_body_valid(self):
        body = RegisterBody(name="Valid User", email="user@example.com", password="Password123!")
        assert body.name == "Valid User"
        assert body.email == "user@example.com"

    def test_register_body_password_too_short(self):
        with pytest.raises(ValidationError):
            RegisterBody(name="User", email="user@example.com", password="123")

    def test_register_body_password_too_long(self):
        with pytest.raises(ValidationError):
            RegisterBody(name="User", email="user@example.com", password="a" * 129)

    def test_register_body_name_too_long(self):
        with pytest.raises(ValidationError):
            RegisterBody(name="a" * 101, email="user@example.com", password="Password123!")

    def test_login_body_password_length_guard(self):
        with pytest.raises(ValidationError):
            LoginBody(email="user@example.com", password="a" * 129)

    def test_reset_body_token_guards(self):
        with pytest.raises(ValidationError):
            ResetBody(token="short", password="Password123!")


class TestServerModelsValidation:
    def test_ask_body_valid(self):
        b = AskBody(question="How is my profit calculated?")
        assert b.question == "How is my profit calculated?"

    def test_ask_body_empty_rejected(self):
        with pytest.raises(ValidationError):
            AskBody(question="")

    def test_ask_body_oversized_rejected(self):
        with pytest.raises(ValidationError):
            AskBody(question="x" * 5001)

    def test_sim_body_negative_values_rejected(self):
        with pytest.raises(ValidationError):
            SimBody(country="Germany", price=-5.0, demand_units=100, inventory_units=100, marketing_budget=500.0)

        with pytest.raises(ValidationError):
            SimBody(country="Germany", price=50.0, demand_units=-1, inventory_units=100, marketing_budget=500.0)

    def test_action_op_literal_validation(self):
        valid = ActionOp(op="simulate")
        assert valid.op == "simulate"

        with pytest.raises(ValidationError):
            ActionOp(op="invalid_action_name")

    def test_create_workspace_mode_literal(self):
        w = CreateWorkspace(name="My Store", mode="demo")
        assert w.mode == "demo"

        with pytest.raises(ValidationError):
            CreateWorkspace(name="My Store", mode="unsupported")


class TestSecurityHeadersAndHealth:
    @pytest.fixture(scope="class")
    def client(self):
        return TestClient(app, raise_server_exceptions=False)

    def test_security_headers_present(self, client):
        r = client.get("/api/")
        assert r.status_code == 200
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert "strict-origin" in r.headers.get("Referrer-Policy", "").lower()

    def test_health_endpoint_structure(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "db" in data
        assert "version" in data


class TestDeploymentConfiguration:
    def test_is_production_detection(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "https://app.ahonix.com")
        assert _is_production() is True

        monkeypatch.setenv("APP_URL", "http://localhost:3000")
        assert _is_production() is False

        monkeypatch.setenv("APP_URL", "http://127.0.0.1:8000")
        assert _is_production() is False

    def test_cors_origins_filter_wildcard(self):
        raw = "http://localhost:3000, *, https://example.com/ "
        cleaned = [o.strip().rstrip("/") for o in raw.split(",") if o.strip() and o.strip() != "*"]
        assert "*" not in cleaned
        assert "http://localhost:3000" in cleaned
        assert "https://example.com" in cleaned


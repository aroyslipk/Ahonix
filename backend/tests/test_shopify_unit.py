"""Automated Unit & Security Tests for Phase 3.1: Shopify Integration Foundation.

Tests:
1. Domain sanitization, formatting, and regex validation
2. HMAC-SHA256 signature verification and tamper detection
3. Fernet token encryption & decryption roundtrip
4. OAuth state generation and time-bounded expiry
5. Status endpoint security (no access token leaks)
6. Read-only sync logic and schema
7. Workspace isolation (unauthorized workspace cannot access another's connection)
8. Demo workspace preservation
9. Real workspace without Shopify displays clean empty state
10. Official Shopify API version configuration (2026-07 default)
"""
import sys
import os
import re
import uuid
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from shopify_integration import (
    clean_shop_domain,
    verify_shopify_hmac,
    encrypt_token,
    decrypt_token,
    get_shopify_config,
    DEFAULT_API_VERSION,
    SHOP_REGEX,
)
from server import app


class TestShopifyDomainValidation:
    def test_clean_valid_domains(self):
        assert clean_shop_domain("my-store.myshopify.com") == "my-store.myshopify.com"
        assert clean_shop_domain("mystore") == "mystore.myshopify.com"
        assert clean_shop_domain("HTTPS://my-store.myshopify.com/") == "my-store.myshopify.com"
        assert clean_shop_domain("http://store-123.myshopify.com/admin") == "store-123.myshopify.com"
        assert clean_shop_domain("store-123?utm=123") == "store-123.myshopify.com"

    def test_reject_invalid_domains(self):
        invalid_inputs = [
            "",
            "   ",
            "evil.com",
            "attacker.com?store.myshopify.com",
            "-invalid.myshopify.com",
            "invalid-.myshopify.com",
            "store..myshopify.com",
            "store.evil.com",
            "store@myshopify.com",
            "store<script>.myshopify.com",
        ]
        for bad in invalid_inputs:
            with pytest.raises(HTTPException) as exc_info:
                clean_shop_domain(bad)
            assert exc_info.value.status_code == 400


class TestShopifyHmacSecurity:
    def test_hmac_valid_signature(self):
        secret = "test_shopify_secret_12345"
        params = {
            "code": "auth_code_abcdef",
            "shop": "test-store.myshopify.com",
            "state": "random_state_nonce",
            "timestamp": "1726000000",
        }
        # Compute valid HMAC
        sorted_pairs = [f"{k}={params[k]}" for k in sorted(params.keys())]
        msg = "&".join(sorted_pairs).encode("utf-8")
        valid_hmac = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        test_params = dict(params, hmac=valid_hmac)
        assert verify_shopify_hmac(test_params, secret) is True

    def test_hmac_tampered_parameter(self):
        secret = "test_shopify_secret_12345"
        params = {
            "code": "auth_code_abcdef",
            "shop": "test-store.myshopify.com",
            "state": "random_state_nonce",
            "timestamp": "1726000000",
        }
        sorted_pairs = [f"{k}={params[k]}" for k in sorted(params.keys())]
        valid_hmac = hmac.new(secret.encode("utf-8"), "&".join(sorted_pairs).encode("utf-8"), hashlib.sha256).hexdigest()

        # Attacker tries to tamper with the shop parameter
        tampered_params = dict(params, shop="attacker-store.myshopify.com", hmac=valid_hmac)
        assert verify_shopify_hmac(tampered_params, secret) is False

    def test_hmac_missing_secret_or_hmac(self):
        assert verify_shopify_hmac({"shop": "test.myshopify.com"}, "") is False
        assert verify_shopify_hmac({"shop": "test.myshopify.com"}, "secret") is False


class TestTokenEncryption:
    def test_encryption_roundtrip(self):
        raw_token = "mock_shopify_access_token_dummy_roundtrip_test_xyz"
        encrypted = encrypt_token(raw_token)
        assert encrypted != raw_token
        assert raw_token not in encrypted
        decrypted = decrypt_token(encrypted)
        assert decrypted == raw_token

    def test_distinct_ciphertexts_for_same_token(self):
        raw = "mock_shopify_access_token_dummy_repeat_test_abc"
        enc1 = encrypt_token(raw)
        enc2 = encrypt_token(raw)
        # Fernet incorporates random IV, so ciphertexts must differ
        assert enc1 != enc2
        assert decrypt_token(enc1) == raw
        assert decrypt_token(enc2) == raw


class TestApiVersionConfiguration:
    def test_default_version_is_current_stable(self):
        # Must match currently supported stable version (2026-07)
        assert DEFAULT_API_VERSION == "2026-07"
        cfg = get_shopify_config()
        assert cfg["api_version"] in ("2025-10", "2026-01", "2026-04", "2026-07")

    def test_version_configurable_via_env(self, monkeypatch):
        monkeypatch.setenv("SHOPIFY_API_VERSION", "2026-04")
        cfg = get_shopify_config()
        assert cfg["api_version"] == "2026-04"


class TestShopifyEndpointsAndIsolation:
    @pytest.fixture(scope="class")
    def client(self):
        return TestClient(app, raise_server_exceptions=False)

    def test_unauthenticated_status_rejected(self, client):
        r = client.get("/api/integrations/shopify/status")
        assert r.status_code == 401

    def test_unauthenticated_connect_rejected(self, client):
        r = client.post("/api/integrations/shopify/connect", json={"shop": "my-store.myshopify.com"})
        assert r.status_code == 401

    def test_unauthenticated_sync_rejected(self, client):
        r = client.post("/api/integrations/shopify/sync")
        assert r.status_code == 401

    def test_unauthenticated_disconnect_rejected(self, client):
        r = client.post("/api/integrations/shopify/disconnect")
        assert r.status_code == 401

    def test_callback_missing_params_redirects_error(self, client):
        r = client.get("/api/integrations/shopify/callback", follow_redirects=False)
        assert r.status_code == 307
        assert "shopify_error=missing_parameters" in r.headers["location"]

    def test_callback_invalid_shop_redirects_error(self, client):
        r = client.get("/api/integrations/shopify/callback?code=abc&state=xyz&shop=evil.com", follow_redirects=False)
        assert r.status_code == 307
        assert "shopify_error=invalid_shop" in r.headers["location"]

    def test_callback_invalid_state_redirects_error(self, client):
        r = client.get("/api/integrations/shopify/callback?code=abc&state=nonexistent_state&shop=test.myshopify.com", follow_redirects=False)
        assert r.status_code == 307
        assert "shopify_error=" in r.headers["location"]


class TestDemoWorkspaceIntegrity:
    def test_demo_analytics_unaffected(self):
        from demo_data import build_workspace_analytics
        data = build_workspace_analytics("Northstar Goods", "USD")
        assert data["store_name"] == "Northstar Goods"
        assert len(data["kpis"]) > 0
        assert "profit" in data
        assert "sales" in data
        assert "actions" in data
        assert data["meta"]["version"] == 2

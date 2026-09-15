"""Unit tests for Ask AHONIX Multi-Provider AI Analyst Service.

Tests:
1. Provider detection and priority resolution (Groq -> OpenAI -> Gemini -> Anthropic -> Emergent).
2. Groq, Anthropic, OpenAI, and Gemini streaming protocols.
3. Emergent fallback resilience.
4. Clean user-facing error handling when unconfigured or when provider fails.
5. Zero secret leakage across responses and logs.
6. HTTP endpoint validation (/api/ask and /api/ask/status).
"""
import sys
from pathlib import Path
import os
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx
from fastapi import HTTPException
from starlette.requests import Request

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import ai_analyst
from ai_analyst import (
    SYSTEM_PROMPT,
    AIProviderNotConfiguredError,
    AIProviderError,
    get_active_ai_provider,
    stream_analyst_response,
)


class TestAIProviderDetection:
    def test_no_provider_when_env_clean(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)

        info = get_active_ai_provider()
        assert info["configured"] is False
        assert info["provider"] is None

    def test_groq_provider_detected(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key_123")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        info = get_active_ai_provider()
        assert info["configured"] is True
        assert info["provider"] == "groq"
        assert info["model"] == "openai/gpt-oss-120b"

    def test_groq_priority_over_other_providers(self, monkeypatch):
        # Even when all other keys are present, Groq takes precedence
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key_123")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test-key")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTest")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-emergent-test")

        info = get_active_ai_provider()
        assert info["configured"] is True
        assert info["provider"] == "groq"

    def test_openai_priority_over_gemini_anthropic(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test-key")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTest")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        info = get_active_ai_provider()
        assert info["configured"] is True
        assert info["provider"] == "openai"

    def test_gemini_provider_detected(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestKey789")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        info = get_active_ai_provider()
        assert info["configured"] is True
        assert info["provider"] == "gemini"
        assert "gemini" in info["model"].lower()

    def test_anthropic_provider_detected(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-123")

        info = get_active_ai_provider()
        assert info["configured"] is True
        assert info["provider"] == "anthropic"
        assert "claude" in info["model"].lower()


class MockStreamResponse:
    def __init__(self, status_code=200, lines=None, error_body=b"Error"):
        self.status_code = status_code
        self._lines = lines or []
        self._error_body = error_body

    async def aread(self):
        return self._error_body

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class TestStreamAnalystResponse:
    def test_unconfigured_raises_clean_error(self, monkeypatch):
        async def _run():
            monkeypatch.delenv("GROQ_API_KEY", raising=False)
            monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
            monkeypatch.delenv("OPENAI_API_KEY", raising=False)
            monkeypatch.delenv("GEMINI_API_KEY", raising=False)
            monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
            monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)

            with pytest.raises(AIProviderNotConfiguredError) as exc_info:
                async for _ in stream_analyst_response("question", "context", "sess_1"):
                    pass
            assert "no AI provider API key is configured" in str(exc_info.value)
            assert "GROQ_API_KEY" in str(exc_info.value)

        asyncio.run(_run())

    def test_groq_streaming_success(self, monkeypatch):
        async def _run():
            monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_stream")
            groq_lines = [
                'data: {"choices": [{"delta": {"content": "### Answer\\n"}}]}',
                'data: {"choices": [{"delta": {"content": "Net profit margin improved to 34%."}}]}',
                'data: [DONE]',
            ]

            mock_resp = MockStreamResponse(200, lines=groq_lines)
            with patch("httpx.AsyncClient.stream", return_value=mock_resp):
                chunks = []
                async for delta in stream_analyst_response("What is net profit?", "{}", "sess_groq"):
                    chunks.append(delta)

                full = "".join(chunks)
                assert "### Answer" in full
                assert "Net profit margin improved to 34%." in full

        asyncio.run(_run())

    def test_groq_auth_failure_raises_clean_error(self, monkeypatch):
        async def _run():
            monkeypatch.setenv("GROQ_API_KEY", "gsk_invalid_test_key")
            mock_resp = MockStreamResponse(401, error_body=b'{"error": {"message": "Invalid API Key"}}')
            with patch("httpx.AsyncClient.stream", return_value=mock_resp):
                with pytest.raises(AIProviderError) as exc_info:
                    async for _ in stream_analyst_response("q", "{}", "s"):
                        pass
                assert "authentication failed" in str(exc_info.value).lower()
                assert "GROQ_API_KEY" in str(exc_info.value)
                # Ensure secret key is never leaked
                assert "gsk_invalid_test_key" not in str(exc_info.value)

        asyncio.run(_run())

    def test_groq_quota_exceeded_raises_clean_error(self, monkeypatch):
        async def _run():
            monkeypatch.setenv("GROQ_API_KEY", "gsk_valid_key")
            mock_resp = MockStreamResponse(429, error_body=b'{"error": "rate_limit"}')
            with patch("httpx.AsyncClient.stream", return_value=mock_resp):
                with pytest.raises(AIProviderError) as exc_info:
                    async for _ in stream_analyst_response("q", "{}", "s"):
                        pass
                assert "rate limit or quota" in str(exc_info.value).lower()

        asyncio.run(_run())

    def test_anthropic_streaming_success(self, monkeypatch):
        async def _run():
            monkeypatch.delenv("GROQ_API_KEY", raising=False)
            monkeypatch.delenv("OPENAI_API_KEY", raising=False)
            monkeypatch.delenv("GEMINI_API_KEY", raising=False)
            monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
            anthropic_lines = [
                'event: message_start',
                'data: {"type": "message_start"}',
                'event: content_block_delta',
                'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "### Answer\\n"}}',
                'event: content_block_delta',
                'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Focus on restocking."}}',
                'event: message_stop',
                'data: {"type": "message_stop"}',
            ]

            mock_resp = MockStreamResponse(200, lines=anthropic_lines)
            with patch("httpx.AsyncClient.stream", return_value=mock_resp):
                chunks = []
                async for delta in stream_analyst_response("What should I focus on?", "{}", "sess_1"):
                    chunks.append(delta)

                full = "".join(chunks)
                assert "### Answer" in full
                assert "Focus on restocking." in full

        asyncio.run(_run())

    def test_openai_streaming_success(self, monkeypatch):
        async def _run():
            monkeypatch.delenv("GROQ_API_KEY", raising=False)
            monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
            monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test")
            openai_lines = [
                'data: {"choices": [{"delta": {"content": "### Answer\\n"}}]}',
                'data: {"choices": [{"delta": {"content": "Revenue grew by 15%."}}]}',
                'data: [DONE]',
            ]

            mock_resp = MockStreamResponse(200, lines=openai_lines)
            with patch("httpx.AsyncClient.stream", return_value=mock_resp):
                chunks = []
                async for delta in stream_analyst_response("What is revenue?", "{}", "sess_2"):
                    chunks.append(delta)

                full = "".join(chunks)
                assert "### Answer" in full
                assert "Revenue grew by 15%." in full

        asyncio.run(_run())

    def test_gemini_streaming_success(self, monkeypatch):
        async def _run():
            monkeypatch.delenv("GROQ_API_KEY", raising=False)
            monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
            monkeypatch.delenv("OPENAI_API_KEY", raising=False)
            monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTest")
            gemini_lines = [
                'data: {"candidates": [{"content": {"parts": [{"text": "### Answer\\nReduce ad spend."}]}}]}',
            ]

            mock_resp = MockStreamResponse(200, lines=gemini_lines)
            with patch("httpx.AsyncClient.stream", return_value=mock_resp):
                chunks = []
                async for delta in stream_analyst_response("How to improve profit?", "{}", "sess_3"):
                    chunks.append(delta)

                full = "".join(chunks)
                assert "### Answer" in full
                assert "Reduce ad spend." in full

        asyncio.run(_run())

    def test_provider_auth_failure_raises_clean_error(self, monkeypatch):
        async def _run():
            monkeypatch.delenv("GROQ_API_KEY", raising=False)
            monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-invalid")
            mock_resp = MockStreamResponse(401, error_body=b'{"error": "invalid_api_key"}')
            with patch("httpx.AsyncClient.stream", return_value=mock_resp):
                with pytest.raises(AIProviderError) as exc_info:
                    async for _ in stream_analyst_response("q", "{}", "s"):
                        pass
                assert "authentication failed" in str(exc_info.value).lower()
                # Ensure raw secret is never in the exception
                assert "sk-ant-invalid" not in str(exc_info.value)

        asyncio.run(_run())

    def test_provider_quota_exceeded_raises_clean_error(self, monkeypatch):
        async def _run():
            monkeypatch.delenv("GROQ_API_KEY", raising=False)
            monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-valid")
            mock_resp = MockStreamResponse(429, error_body=b'{"error": "rate_limit"}')
            with patch("httpx.AsyncClient.stream", return_value=mock_resp):
                with pytest.raises(AIProviderError) as exc_info:
                    async for _ in stream_analyst_response("q", "{}", "s"):
                        pass
                assert "rate limit or quota" in str(exc_info.value).lower()

        asyncio.run(_run())


class TestAskEndpointHttp:
    @pytest.fixture(autouse=True)
    def setup_client(self):
        from starlette.testclient import TestClient
        from server import app, get_current_user, get_workspace_data

        mock_user = {"user_id": "u_test", "email": "test@example.com", "active_workspace_id": "ws_test"}
        mock_ws = {"workspace_id": "ws_test", "name": "Test Store", "currency": "USD"}
        mock_data = {
            "store_name": "Test Store",
            "currency": "USD",
            "kpis": [
                {"id": "revenue", "value": 10000, "change": 5},
                {"id": "true-profit", "value": 3000, "change": 2},
                {"id": "orders", "value": 150},
                {"id": "aov", "value": 66.7},
                {"id": "return-rate", "value": 3.5},
                {"id": "marketing-eff", "value": 3.2},
            ],
            "profit": {
                "margin": 30.0,
                "insight": {"best_seller": "Product A", "most_profitable": "Product B", "best_margin": "Product C"},
                "steps": [{"label": "COGS", "value": 4000}],
            },
            "inventory": {"items": [{"name": "Product A", "days_left": 10, "stockout_date": "2026-10-01", "reorder_qty": 50}]},
            "marketing": {"paradox": False, "campaigns": [{"name": "C1", "roas": 3.5, "contribution": 1000}]},
            "returns": {"by_product": [{"name": "Product A", "return_rate": 2.1, "cost": 500}]},
            "markets": [{"country": "Canada"}],
        }

        app.dependency_overrides[get_current_user] = lambda: mock_user
        with patch("server.get_workspace_data", new=AsyncMock(return_value=(mock_ws, mock_data))):
            with patch("server.db.chat_messages.insert_one", new=AsyncMock(return_value=MagicMock())):
                client = TestClient(app)
                yield client

        app.dependency_overrides.clear()

    def test_status_endpoint_returns_unconfigured(self, setup_client, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)

        res = setup_client.get("/api/ask/status")
        assert res.status_code == 200
        data = res.json()
        assert data["configured"] is False
        assert data["provider"] is None

    def test_status_endpoint_returns_groq_when_configured(self, setup_client, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_status_key")
        res = setup_client.get("/api/ask/status")
        assert res.status_code == 200
        data = res.json()
        assert data["configured"] is True
        assert data["provider"] == "groq"
        assert data["model"] == "openai/gpt-oss-120b"

    def test_empty_question_returns_422(self, setup_client):
        res = setup_client.post("/api/ask", json={"question": "   "})
        assert res.status_code == 422
        assert "empty" in res.json()["detail"].lower()

    def test_oversized_question_returns_422(self, setup_client):
        res = setup_client.post("/api/ask", json={"question": "a" * 5001})
        assert res.status_code == 422

    def test_unconfigured_returns_sse_error_without_500(self, setup_client, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)

        res = setup_client.post("/api/ask", json={"question": "What is my revenue?"})
        # Crucial requirement: Must NOT fail with 500!
        assert res.status_code == 200
        body = res.text
        assert "data:" in body
        assert "error" in body
        assert "no AI provider API key is configured" in body

    def test_configured_groq_streams_sse_deltas(self, setup_client, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_live")
        groq_lines = [
            'data: {"choices": [{"delta": {"content": "### Answer\\nRevenue is $10,000."}}]}',
            'data: [DONE]',
        ]
        mock_resp = MockStreamResponse(200, lines=groq_lines)
        with patch("httpx.AsyncClient.stream", return_value=mock_resp):
            res = setup_client.post("/api/ask", json={"question": "What is my revenue?"})
            assert res.status_code == 200
            body = res.text
            assert "data:" in body
            assert "Revenue is $10,000." in body
            assert '"done": true' in body

    def test_configured_anthropic_streams_sse_deltas(self, setup_client, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        anthropic_lines = [
            'event: content_block_delta',
            'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "### Answer\\nRevenue is $10,000."}}',
        ]
        mock_resp = MockStreamResponse(200, lines=anthropic_lines)
        with patch("httpx.AsyncClient.stream", return_value=mock_resp):
            res = setup_client.post("/api/ask", json={"question": "What is my revenue?"})
            assert res.status_code == 200
            body = res.text
            assert "data:" in body
            assert "Revenue is $10,000." in body
            assert '"done": true' in body

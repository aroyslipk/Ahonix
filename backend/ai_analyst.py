"""AI Commerce Analyst service for AHONIX.

Supports multiple external AI providers via direct HTTP streaming (httpx):
1. Groq (GROQ_API_KEY) — e.g. openai/gpt-oss-120b or qwen/qwen3.8-27b via OpenAI-compatible endpoint
2. OpenAI / OpenAI-compatible (OPENAI_API_KEY) — e.g. gpt-4o-mini
3. Google Gemini (GEMINI_API_KEY / GOOGLE_AI_API_KEY) — e.g. gemini-1.5-flash
4. Anthropic Claude (ANTHROPIC_API_KEY) — e.g. claude-3-5-sonnet-20241022
5. Emergent Sandbox Fallback (EMERGENT_LLM_KEY) — via emergentintegrations if installed

Zero secret leakage: API keys are read strictly from environment variables and never logged.
"""
import os
import json
import logging
from typing import AsyncGenerator

import httpx

logger = logging.getLogger("ahonix.ai_analyst")

SYSTEM_PROMPT = """You are AHONIX, an AI commerce analyst inside the AHONIX Commerce OS. \
You are NOT a generic chatbot. You are a sharp, concise commerce analyst who reasons over the merchant's own data.

You will be given a JSON snapshot of the merchant's commerce data (which may be active demo data, or a live merchant store awaiting or synchronizing data). Answer the user's question ONLY using that data.
If has_recorded_activity is false or values are 0 / null, explicitly inform the merchant that their store currently has no recorded transactions or order activity yet, and recommend connecting their store (Shopify, Meta Ads, Google Ads) in Settings.
Under AHONIX Zero Fabrication Policy: Never invent external facts, fictional numbers, or claim certainty on unrecorded data.

Always respond in GitHub-flavoured markdown using EXACTLY these sections (omit a section only if truly not applicable):

### Answer
One or two sentences with the key conclusion.

### Evidence
- 2-4 bullet points citing specific numbers from the data.

### Reasoning
A concise 1-2 sentence explanation of *why*.

### Recommendation
The single most valuable next action.

### Expected Impact
An estimated or projected figure, clearly labelled as Estimated/Projected (or Next Step if awaiting telemetry).

Keep it tight and executive. Use the currency and figures from the snapshot. Do not use tables."""


class AIProviderNotConfiguredError(Exception):
    """Raised when no external AI provider API key is set in environment."""
    pass


class AIProviderError(Exception):
    """Raised when the AI provider API returns an error or fails to stream."""
    pass


def get_active_ai_provider() -> dict:
    """Inspect environment variables to determine the active AI provider.
    
    Priority order:
    1. GROQ_API_KEY -> Groq (OpenAI-compatible)
    2. OPENAI_API_KEY -> OpenAI / compatible
    3. GEMINI_API_KEY / GOOGLE_AI_API_KEY -> Google Gemini
    4. ANTHROPIC_API_KEY -> Anthropic Claude
    5. EMERGENT_LLM_KEY -> Emergent sandbox fallback
    """
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_AI_API_KEY", "")).strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()

    if groq_key:
        return {
            "provider": "groq",
            "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            "configured": True,
        }
    if openai_key:
        return {
            "provider": "openai",
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "configured": True,
        }
    if gemini_key:
        return {
            "provider": "gemini",
            "model": os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
            "configured": True,
        }
    if anthropic_key:
        return {
            "provider": "anthropic",
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            "configured": True,
        }
    if emergent_key:
        return {
            "provider": "emergent",
            "model": "claude-sonnet-4-6",
            "configured": True,
        }

    return {
        "provider": None,
        "model": None,
        "configured": False,
    }


async def _stream_groq(
    api_key: str, model: str, system: str, question: str
) -> AsyncGenerator[str, None]:
    base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "AHONIX/2.0",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    err_bytes = await resp.aread()
                    logger.error("Groq API error status %s", resp.status_code)
                    if resp.status_code in (401, 403):
                        raise AIProviderError("Groq API key authentication failed. Please verify GROQ_API_KEY.")
                    elif resp.status_code == 429:
                        raise AIProviderError("Groq rate limit or quota exceeded.")
                    raise AIProviderError(f"Groq returned status {resp.status_code}")

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        ev = json.loads(data_str)
                        choices = ev.get("choices", [])
                        if choices:
                            content = choices[0].get("delta", {}).get("content")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
    except httpx.RequestError as e:
        logger.error("Groq connection error: %s", type(e).__name__)
        raise AIProviderError(f"Could not connect to Groq API: {type(e).__name__}")


async def _stream_anthropic(
    api_key: str, model: str, system: str, question: str
) -> AsyncGenerator[str, None]:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": int(os.environ.get("ANTHROPIC_MAX_TOKENS", "1500")),
        "system": system,
        "messages": [{"role": "user", "content": question}],
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    err_bytes = await resp.aread()
                    logger.error("Anthropic API error status %s", resp.status_code)
                    if resp.status_code in (401, 403):
                        raise AIProviderError("Anthropic API key authentication failed. Please verify ANTHROPIC_API_KEY.")
                    elif resp.status_code == 429:
                        raise AIProviderError("Anthropic rate limit or quota exceeded.")
                    raise AIProviderError(f"Anthropic returned status {resp.status_code}")

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                    try:
                        ev = json.loads(data_str)
                        if ev.get("type") == "content_block_delta":
                            delta = ev.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue
    except httpx.RequestError as e:
        logger.error("Anthropic connection error: %s", type(e).__name__)
        raise AIProviderError(f"Could not connect to Anthropic API: {type(e).__name__}")


async def _stream_openai(
    api_key: str, model: str, system: str, question: str
) -> AsyncGenerator[str, None]:
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    err_bytes = await resp.aread()
                    logger.error("OpenAI API error status %s", resp.status_code)
                    if resp.status_code in (401, 403):
                        raise AIProviderError("OpenAI API key authentication failed. Please verify OPENAI_API_KEY.")
                    elif resp.status_code == 429:
                        raise AIProviderError("OpenAI rate limit or quota exceeded.")
                    raise AIProviderError(f"OpenAI returned status {resp.status_code}")

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        ev = json.loads(data_str)
                        choices = ev.get("choices", [])
                        if choices:
                            content = choices[0].get("delta", {}).get("content")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
    except httpx.RequestError as e:
        logger.error("OpenAI connection error: %s", type(e).__name__)
        raise AIProviderError(f"Could not connect to OpenAI API: {type(e).__name__}")


async def _stream_gemini(
    api_key: str, model: str, system: str, question: str
) -> AsyncGenerator[str, None]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "system_instruction": {
            "parts": [{"text": system}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": question}]}
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    err_bytes = await resp.aread()
                    logger.error("Gemini API error status %s", resp.status_code)
                    if resp.status_code in (400, 401, 403):
                        raise AIProviderError("Gemini API key authentication failed. Please verify GEMINI_API_KEY.")
                    elif resp.status_code == 429:
                        raise AIProviderError("Gemini rate limit or quota exceeded.")
                    raise AIProviderError(f"Gemini returned status {resp.status_code}")

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                    try:
                        ev = json.loads(data_str)
                        candidates = ev.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                text = part.get("text")
                                if text:
                                    yield text
                    except json.JSONDecodeError:
                        continue
    except httpx.RequestError as e:
        logger.error("Gemini connection error: %s", type(e).__name__)
        raise AIProviderError(f"Could not connect to Gemini API: {type(e).__name__}")


async def _stream_emergent(
    api_key: str, session_id: str, system: str, question: str
) -> AsyncGenerator[str, None]:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
    except ImportError:
        logger.warning("emergentintegrations is not installed in this environment.")
        raise AIProviderError(
            "Emergent LLM integration is unavailable on Render. "
            "Please configure GROQ_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY in Render environment variables."
        )

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system,
        ).with_model("anthropic", "claude-sonnet-4-6")

        async for ev in chat.stream_message(UserMessage(text=question)):
            if isinstance(ev, TextDelta):
                yield ev.content
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        logger.error("Emergent chat stream error: %s", type(e).__name__)
        raise AIProviderError("Emergent analyst stream encountered an error.")


async def stream_analyst_response(
    question: str,
    context: str,
    session_id: str,
    system_prompt: str = SYSTEM_PROMPT,
) -> AsyncGenerator[str, None]:
    """Stream response from the active AI provider.
    
    Raises:
        AIProviderNotConfiguredError: When no AI API key is set in environment.
        AIProviderError: When provider connection fails or returns error status.
    """
    info = get_active_ai_provider()
    provider = info["provider"]

    if not provider:
        raise AIProviderNotConfiguredError(
            "Ask AHONIX is ready, but no AI provider API key is configured. "
            "Please configure GROQ_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY in your environment variables."
        )

    full_system = system_prompt + "\n\nMERCHANT DATA SNAPSHOT:\n" + context

    if provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        async for delta in _stream_groq(api_key, info["model"], full_system, question):
            yield delta
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        async for delta in _stream_openai(api_key, info["model"], full_system, question):
            yield delta
    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_AI_API_KEY", "")).strip()
        async for delta in _stream_gemini(api_key, info["model"], full_system, question):
            yield delta
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        async for delta in _stream_anthropic(api_key, info["model"], full_system, question):
            yield delta
    elif provider == "emergent":
        api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
        async for delta in _stream_emergent(api_key, session_id, full_system, question):
            yield delta

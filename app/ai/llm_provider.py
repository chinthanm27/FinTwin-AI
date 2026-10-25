"""
Pluggable LLM providers.

All LLM access goes through `get_llm_provider()`. When no API key is
configured it returns None and the Copilot uses the offline twin engine.
The API key is read from settings (.env) and sent only in a request
header to the provider, never logged or shown in the UI.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("ai.llm")


class LLMError(Exception):
    """Raised when the LLM provider fails; callers fall back to offline answers."""


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, history: list[dict[str, str]] | None = None) -> str:
        """Return the model's text response."""


class GeminiProvider(LLMProvider):
    """Google Gemini via the public REST API (no extra SDK dependency)."""

    name = "Gemini"
    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str, history: list[dict[str, str]] | None = None) -> str:
        contents = []
        for msg in (history or [])[-6:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"][:4000]}]})
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
        }
        request = urllib.request.Request(
            self.ENDPOINT.format(model=self.model),
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            log.warning("Gemini HTTP error %s", exc.code)
            raise LLMError(f"Gemini returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            log.warning("Gemini request failed: %s", type(exc).__name__)
            raise LLMError("Gemini request failed") from None
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError):
            raise LLMError("Unexpected Gemini response") from None
        if not text:
            raise LLMError("Empty Gemini response")
        return text


def get_llm_provider() -> LLMProvider | None:
    if settings.llm_configured:
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    return None


def provider_status() -> tuple[bool, str]:
    provider = get_llm_provider()
    if provider is None:
        return False, "Offline twin engine (add GEMINI_API_KEY in .env to enable Gemini)"
    return True, f"{provider.name} · {settings.gemini_model}"

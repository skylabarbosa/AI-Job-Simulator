import json
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


_rate_lock = threading.Lock()
_request_times: list[float] = []


def _reserve_request() -> None:
    """Small in-process safety valve; deployment-wide quotas remain provider-side."""
    now = time.monotonic()
    with _rate_lock:
        _request_times[:] = [item for item in _request_times if now - item < 60]
        if len(_request_times) >= settings.llm_max_requests_per_minute:
            raise LLMProviderError("AI service is temporarily busy. Please try again shortly.")
        _request_times.append(now)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str


class LLMConfigurationError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    pass


class GeminiProvider:
    endpoint_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> LLMResponse:
        _reserve_request()
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        try:
            response = httpx.post(
                self.endpoint_template.format(model=self.model),
                headers={"x-goog-api-key": self.api_key},
                json=payload,
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            content = body["candidates"][0]["content"]["parts"][0]["text"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("The provider returned empty content")
            return LLMResponse(content=content, provider="gemini", model=self.model)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMProviderError("The AI provider did not return a usable blueprint") from error


def get_llm_provider() -> GeminiProvider:
    if settings.llm_provider != "gemini":
        raise LLMConfigurationError("The configured AI provider is not supported")
    if not settings.llm_api_key:
        raise LLMConfigurationError("AI project understanding is not configured")
    return GeminiProvider(settings.llm_api_key, settings.llm_model)


def parse_json(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise LLMProviderError("The AI provider returned invalid JSON") from error
    if not isinstance(parsed, dict):
        raise LLMProviderError("The AI provider returned an invalid blueprint object")
    return parsed

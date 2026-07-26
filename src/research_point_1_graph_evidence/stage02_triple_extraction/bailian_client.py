"""Minimal OpenAI-compatible Bailian client with retry and JSON-only output."""

from __future__ import annotations

import json
import http.client
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping


@dataclass(frozen=True)
class BailianResponse:
    request_id: str | None
    model: str
    finish_reason: str | None
    usage: dict[str, object]
    latency_ms: int
    attempt: int
    content: dict[str, object]


def _decode_json_content(value: str) -> dict[str, object]:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Model response content must be a JSON object")
    return parsed


def call_chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    enable_thinking: bool,
    response_format: Mapping[str, object],
    timeout_seconds: int,
    max_retries: int,
    retry_callback: Callable[[int, int, str, float], None] | None = None,
) -> BailianResponse:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": dict(response_format),
            "enable_thinking": enable_thinking,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    retry_statuses = {408, 409, 429, 500, 502, 503, 504}
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Fault-LLM-v2/Stage02",
                "Connection": "close",
            },
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latency_ms = round((time.perf_counter() - started) * 1000)
            message_content = payload["choices"][0]["message"]["content"]
            return BailianResponse(
                request_id=payload.get("id"),
                model=str(payload.get("model") or model),
                finish_reason=payload["choices"][0].get("finish_reason"),
                usage=dict(payload.get("usage") or {}),
                latency_ms=latency_ms,
                attempt=attempt,
                content=_decode_json_content(str(message_content)),
            )
        except urllib.error.HTTPError as error:
            body_text = error.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(
                f"Bailian HTTP {error.code}: {body_text[:800]}"
            )
            if error.code not in retry_statuses or attempt == max_retries:
                break
        except (
            urllib.error.URLError,
            http.client.RemoteDisconnected,
            ConnectionResetError,
            BrokenPipeError,
            TimeoutError,
            ssl.SSLError,
            json.JSONDecodeError,
            KeyError,
            ValueError,
        ) as error:
            last_error = error
            if attempt == max_retries:
                break
        wait_seconds = float(min(2 ** (attempt - 1), 8))
        if retry_callback:
            retry_callback(
                attempt,
                max_retries,
                f"{type(last_error).__name__}: {last_error}",
                wait_seconds,
            )
        time.sleep(wait_seconds)

    raise RuntimeError(
        f"Bailian request failed after {max_retries} attempts: {last_error}"
    ) from last_error

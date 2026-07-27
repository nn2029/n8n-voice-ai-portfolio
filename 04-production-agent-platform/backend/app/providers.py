from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    content: dict[str, Any]
    latency_ms: int
    token_cost_usd: float


class ProviderRouter:
    """Route model work through explicit adapters and preserve a deterministic fallback."""

    def run(self, preferred: str, task: str, payload: dict[str, Any]) -> ProviderResult:
        errors: list[str] = []
        for candidate in self._candidates(preferred):
            try:
                if candidate == "openai":
                    return self._openai(task, payload)
                if candidate == "anthropic":
                    return self._anthropic(task, payload)
                return self._mock(task, payload)
            except Exception as exc:
                errors.append(f"{candidate}:{type(exc).__name__}")
        result = self._mock(task, payload)
        result.content["fallback_errors"] = errors
        return result

    def _candidates(self, preferred: str) -> list[str]:
        if preferred == "mock":
            return ["mock"]
        if preferred == "openai":
            return ["openai", "anthropic", "mock"]
        if preferred == "anthropic":
            return ["anthropic", "openai", "mock"]
        ordered: list[str] = []
        if os.getenv("OPENAI_API_KEY"):
            ordered.append("openai")
        if os.getenv("ANTHROPIC_API_KEY"):
            ordered.append("anthropic")
        return ordered + ["mock"]

    def _mock(self, task: str, payload: dict[str, Any]) -> ProviderResult:
        started = time.perf_counter()
        subject = str(payload.get("subject") or payload.get("title") or payload.get("name") or "request")
        if task == "email_triage":
            content = {
                "category": "priority" if any(word in str(payload).lower() for word in ["urgent", "refund", "outage"]) else "standard",
                "summary": f"Triage summary for {subject}",
                "recommended_action": "assign_owner",
                "confidence": 0.86,
            }
        elif task == "crm_update":
            content = {"operation": "upsert_contact", "fields": payload, "confidence": 0.98}
        elif task == "document_generation":
            content = {"document": f"Draft document for {subject}", "requires_review": True, "confidence": 0.91}
        else:
            content = {"report": "Deterministic daily report generated from supplied records.", "record_count": len(payload)}
        return ProviderResult("mock", content, int((time.perf_counter() - started) * 1000), 0.0)

    def _openai(self, task: str, payload: dict[str, Any]) -> ProviderResult:
        key = os.environ["OPENAI_API_KEY"]
        started = time.perf_counter()
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "Return JSON only. Recommend actions; never claim an external action was executed."},
                    {"role": "user", "content": f"Task: {task}\nPayload: {payload}"},
                ],
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        import json
        content = json.loads(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        cost = round((usage.get("prompt_tokens", 0) * 0.00000015) + (usage.get("completion_tokens", 0) * 0.0000006), 6)
        return ProviderResult("openai", content, int((time.perf_counter() - started) * 1000), cost)

    def _anthropic(self, task: str, payload: dict[str, Any]) -> ProviderResult:
        key = os.environ["ANTHROPIC_API_KEY"]
        started = time.perf_counter()
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={
                "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
                "max_tokens": 800,
                "temperature": 0,
                "system": "Return JSON only. Recommend actions; never claim an external action was executed.",
                "messages": [{"role": "user", "content": f"Task: {task}\nPayload: {payload}"}],
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        import json
        content = json.loads(data["content"][0]["text"])
        usage = data.get("usage", {})
        cost = round((usage.get("input_tokens", 0) * 0.0000008) + (usage.get("output_tokens", 0) * 0.000004), 6)
        return ProviderResult("anthropic", content, int((time.perf_counter() - started) * 1000), cost)

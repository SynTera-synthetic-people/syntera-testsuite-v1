"""Shared LLM provider gateway: OpenAI/Anthropic calls with cache, budget, and throttling."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from backend.utils.llm_runtime import DailyTokenBudget, HeavyCallLimiter, LlmResponseCache, estimate_tokens


def provider_from_model(model: str) -> str:
    m = (model or "").lower()
    return "anthropic" if "claude" in m else "openai"


class LlmGateway:
    def __init__(self, settings: Any):
        self.settings = settings
        self.cache = LlmResponseCache(
            max_items=getattr(settings, "LLM_CACHE_MAX_ITEMS", 300),
            ttl_seconds=getattr(settings, "LLM_CACHE_TTL_SEC", 21600),
        )
        self.limiter = HeavyCallLimiter(max_concurrent=getattr(settings, "LLM_MAX_CONCURRENT_HEAVY_CALLS", 3))
        self.budget = DailyTokenBudget(max_tokens_per_day=getattr(settings, "LLM_DAILY_TOKEN_BUDGET", 50_000_000))

    def _cache_get(self, provider: str, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
        return self.cache.get(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allow_near_duplicate=bool(getattr(self.settings, "LLM_ALLOW_NEAR_DUPLICATE_CACHE", True)),
            near_duplicate_threshold=float(getattr(self.settings, "LLM_NEAR_DUPLICATE_THRESHOLD", 0.985)),
        )

    def _cache_set(self, provider: str, model: str, system_prompt: str, user_prompt: str, value: str) -> None:
        self.cache.set(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            value=value,
        )

    def _guard_daily_budget(self, input_text: str, max_tokens: int) -> None:
        estimated = estimate_tokens(input_text) + int(max_tokens)
        if not self.budget.can_consume(estimated):
            raise HTTPException(
                status_code=429,
                detail=(
                    "Daily LLM token budget exceeded for this environment. "
                    "Please retry later or run this as an offline batch with a larger budget."
                ),
            )
        self.budget.consume(estimated)

    def _consume_usage_tokens(self, response: Any) -> None:
        try:
            usage = getattr(response, "usage", None) or {}
            if isinstance(usage, dict):
                total = int(usage.get("total_tokens") or 0) or int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
            else:
                total = int(getattr(usage, "total_tokens", 0) or 0) or int(getattr(usage, "input_tokens", 0) or 0) + int(getattr(usage, "output_tokens", 0) or 0)
            if total > 0:
                self.budget.consume(total)
        except Exception:
            pass

    def complete(
        self,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        *,
        api_key: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        response_format_json: bool = False,
        use_cache: bool = True,
    ) -> str:
        provider = (provider or "").strip().lower()
        if provider not in {"openai", "anthropic"}:
            raise ValueError("provider must be openai or anthropic")
        if not api_key:
            raise ValueError(f"{provider.upper()} API key not set")

        if use_cache:
            cached = self._cache_get(provider, model, system_prompt, user_prompt)
            if cached:
                return cached

        self._guard_daily_budget(user_prompt, max_tokens)
        with self.limiter:
            if provider == "openai":
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
                kwargs = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format_json:
                    kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
                self._consume_usage_tokens(response)
                content = response.choices[0].message.content if response.choices else None
                if isinstance(content, list):
                    content = " ".join((p.get("text") if isinstance(p, dict) else str(p) for p in content if p))
                out = (content or "").strip()
            else:
                import anthropic

                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                self._consume_usage_tokens(response)
                parts = []
                for block in response.content or []:
                    text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
                    if text:
                        parts.append(str(text).strip())
                out = "\n\n".join(parts).strip()

        if use_cache and out:
            self._cache_set(provider, model, system_prompt, user_prompt, out)
        return out

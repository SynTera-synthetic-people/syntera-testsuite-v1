import hashlib
import re
import threading
import time
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from typing import Optional


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) used for budget guardrails."""
    t = (text or "").strip()
    if not t:
        return 0
    return max(1, int(len(t) / 4))


def normalize_prompt(text: str) -> str:
    """Normalize prompt for deterministic + near-duplicate cache matching."""
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def hash_prompt(parts: list[str]) -> str:
    joined = "||".join(normalize_prompt(p) for p in parts if p is not None)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass
class CacheEntry:
    created_at: float
    key_hash: str
    provider: str
    model: str
    normalized_user_prompt: str
    value: str


class LlmResponseCache:
    """In-memory cache for deterministic requests keyed by provider/model/prompt hash."""

    def __init__(self, max_items: int = 200, ttl_seconds: int = 7200):
        self.max_items = max(10, int(max_items))
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._items: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def _evict_expired_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._items.items() if now - v.created_at > self.ttl_seconds]
        for k in expired:
            self._items.pop(k, None)
        while len(self._items) > self.max_items:
            oldest_key = min(self._items, key=lambda k: self._items[k].created_at)
            self._items.pop(oldest_key, None)

    def get(
        self,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        allow_near_duplicate: bool = True,
        near_duplicate_threshold: float = 0.985,
    ) -> Optional[str]:
        k = hash_prompt([provider, model, system_prompt, user_prompt])
        normalized_user = normalize_prompt(user_prompt)
        with self._lock:
            self._evict_expired_locked()
            if k in self._items:
                return self._items[k].value
            if not allow_near_duplicate or not normalized_user:
                return None
            candidates = [
                v for v in self._items.values()
                if v.provider == provider and v.model == model
            ]
            for entry in candidates:
                ratio = SequenceMatcher(None, normalized_user, entry.normalized_user_prompt).ratio()
                if ratio >= near_duplicate_threshold:
                    return entry.value
        return None

    def set(self, provider: str, model: str, system_prompt: str, user_prompt: str, value: str) -> None:
        k = hash_prompt([provider, model, system_prompt, user_prompt])
        normalized_user = normalize_prompt(user_prompt)
        entry = CacheEntry(
            created_at=time.time(),
            key_hash=k,
            provider=provider,
            model=model,
            normalized_user_prompt=normalized_user,
            value=value or "",
        )
        with self._lock:
            self._items[k] = entry
            self._evict_expired_locked()


class HeavyCallLimiter:
    """Simple concurrency limiter for high-token operations."""

    def __init__(self, max_concurrent: int = 3):
        self._sem = threading.Semaphore(max(1, int(max_concurrent)))

    def __enter__(self):
        self._sem.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._sem.release()


class DailyTokenBudget:
    """In-memory daily token budget guardrail (best-effort)."""

    def __init__(self, max_tokens_per_day: int = 50_000_000):
        self.max_tokens_per_day = max(10_000, int(max_tokens_per_day))
        self._lock = threading.Lock()
        self._day = date.today().isoformat()
        self._used_tokens = 0

    def _rollover_locked(self) -> None:
        today = date.today().isoformat()
        if today != self._day:
            self._day = today
            self._used_tokens = 0

    def can_consume(self, tokens: int) -> bool:
        with self._lock:
            self._rollover_locked()
            return self._used_tokens + max(0, int(tokens)) <= self.max_tokens_per_day

    def consume(self, tokens: int) -> None:
        with self._lock:
            self._rollover_locked()
            self._used_tokens += max(0, int(tokens))

    @property
    def used_tokens(self) -> int:
        with self._lock:
            self._rollover_locked()
            return self._used_tokens

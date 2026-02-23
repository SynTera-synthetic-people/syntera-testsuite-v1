"""Simulation runtime for section-level Q&A generation.

Provides:
- Batch request/response schemas for section-level simulation
- Archetype-level caching (compute once, reuse many respondents)
- Deterministic local variation generator (no extra LLM calls)
"""
from __future__ import annotations

import hashlib
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class SimulationQuestion(BaseModel):
    question_id: str
    question_text: str
    question_type: str = "single_choice"  # single_choice | multi_choice | likert | text
    options: list[str] = Field(default_factory=list)


class SegmentConfig(BaseModel):
    segment_id: str
    segment_name: str
    traits: list[str] = Field(default_factory=list)
    archetype_count: int = Field(default=3, ge=1, le=10)
    variation_strength: float = Field(default=0.25, ge=0.0, le=1.0)


class SectionQABatchRequest(BaseModel):
    section_id: str
    section_name: str
    objective: str
    model: str = "gpt-4o-mini"
    respondent_count: int = Field(default=50, ge=1, le=5000)
    deterministic_seed: int = 42
    use_llm_archetypes: bool = True
    llm_max_tokens: int = Field(default=2500, ge=256, le=8192)
    segment: SegmentConfig
    questions: list[SimulationQuestion] = Field(default_factory=list)


class SimulatedAnswer(BaseModel):
    question_id: str
    answer: str
    reasons: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ArchetypeProfile(BaseModel):
    archetype_id: str
    label: str
    answers: list[SimulatedAnswer] = Field(default_factory=list)


class RespondentSimulation(BaseModel):
    respondent_id: str
    segment_id: str
    archetype_id: str
    answers: list[SimulatedAnswer] = Field(default_factory=list)


class SectionQABatchResponse(BaseModel):
    section_id: str
    section_name: str
    objective: str
    model: str
    cache_hit: bool
    archetypes: list[ArchetypeProfile] = Field(default_factory=list)
    respondents: list[RespondentSimulation] = Field(default_factory=list)
    generated_at: float


class FeatureMapRequest(BaseModel):
    section_id: str
    segment_id: str
    respondents: list[RespondentSimulation] = Field(default_factory=list)
    force_refresh: bool = False


class FeatureMapItem(BaseModel):
    answer: str
    sentiment: str
    themes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class FeatureMapResponse(BaseModel):
    section_id: str
    segment_id: str
    cache_hits: int
    cache_misses: int
    feature_map: dict[str, list[FeatureMapItem]] = Field(default_factory=dict)  # question_id -> features
    generated_at: float


@dataclass
class _ArchetypeCacheEntry:
    created_at: float
    archetypes: list[ArchetypeProfile]


@dataclass
class _FeatureCacheEntry:
    created_at: float
    value: FeatureMapItem


class SimulationRuntimeService:
    """Archetype-cache + local variation simulation runtime."""

    def __init__(self, cache_ttl_sec: int = 6 * 60 * 60, cache_max_items: int = 500):
        self.cache_ttl_sec = max(60, int(cache_ttl_sec))
        self.cache_max_items = max(10, int(cache_max_items))
        self._cache: dict[str, _ArchetypeCacheEntry] = {}
        self._feature_cache: dict[str, _FeatureCacheEntry] = {}
        self._lock = threading.Lock()

    def _cache_key(self, req: SectionQABatchRequest) -> str:
        q_sig = "||".join(
            f"{q.question_id}|{q.question_text}|{q.question_type}|{'/'.join(q.options)}"
            for q in req.questions
        )
        raw = (
            f"{req.model}|{req.section_id}|{req.section_name}|{req.objective}|"
            f"{req.segment.segment_id}|{req.segment.segment_name}|"
            f"{','.join(req.segment.traits)}|{req.segment.archetype_count}|{q_sig}"
        ).lower().strip()
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _evict_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v.created_at > self.cache_ttl_sec]
        for k in expired:
            self._cache.pop(k, None)
        while len(self._cache) > self.cache_max_items:
            oldest = min(self._cache, key=lambda x: self._cache[x].created_at)
            self._cache.pop(oldest, None)
        f_expired = [k for k, v in self._feature_cache.items() if now - v.created_at > self.cache_ttl_sec]
        for k in f_expired:
            self._feature_cache.pop(k, None)
        while len(self._feature_cache) > self.cache_max_items * 5:
            oldest = min(self._feature_cache, key=lambda x: self._feature_cache[x].created_at)
            self._feature_cache.pop(oldest, None)

    @staticmethod
    def _normalize_answer(text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    @staticmethod
    def _sentiment(answer: str) -> str:
        t = (answer or "").lower()
        positive = ("good", "great", "excellent", "love", "best", "satisfied", "happy", "positive", "yes")
        negative = ("bad", "poor", "worst", "hate", "unsatisfied", "negative", "no", "never")
        p = sum(1 for w in positive if w in t)
        n = sum(1 for w in negative if w in t)
        if p > n:
            return "positive"
        if n > p:
            return "negative"
        return "neutral"

    @staticmethod
    def _themes(answer: str) -> list[str]:
        t = (answer or "").lower()
        theme_map = {
            "price": ("price", "cost", "expensive", "cheap", "value"),
            "quality": ("quality", "durable", "reliable", "taste"),
            "health": ("health", "healthy", "sugar-free", "low-fat", "protein"),
            "convenience": ("convenient", "easy", "quick", "ready-to-eat"),
            "brand": ("brand", "trusted", "known", "familiar"),
        }
        found = []
        for theme, words in theme_map.items():
            if any(w in t for w in words):
                found.append(theme)
        return found or ["general"]

    def _feature_key(self, section_id: str, segment_id: str, question_id: str, answer: str) -> str:
        raw = f"{section_id}|{segment_id}|{question_id}|{self._normalize_answer(answer)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _classify_answer(self, answer: str) -> FeatureMapItem:
        sentiment = self._sentiment(answer)
        themes = self._themes(answer)
        tags = [sentiment] + themes
        return FeatureMapItem(answer=answer, sentiment=sentiment, themes=themes, tags=tags)

    def build_feature_map(self, req: FeatureMapRequest) -> FeatureMapResponse:
        feature_map: dict[str, list[FeatureMapItem]] = {}
        hits = 0
        misses = 0

        # Deduplicate answers per question for compact precomputed maps
        q_to_answers: dict[str, set[str]] = {}
        for r in req.respondents:
            for a in r.answers:
                q_to_answers.setdefault(a.question_id, set()).add(a.answer or "")

        with self._lock:
            self._evict_locked()
            for question_id, answers in q_to_answers.items():
                rows: list[FeatureMapItem] = []
                for ans in sorted(answers):
                    k = self._feature_key(req.section_id, req.segment_id, question_id, ans)
                    cached = None if req.force_refresh else self._feature_cache.get(k)
                    if cached:
                        rows.append(cached.value)
                        hits += 1
                        continue
                    item = self._classify_answer(ans)
                    self._feature_cache[k] = _FeatureCacheEntry(created_at=time.time(), value=item)
                    rows.append(item)
                    misses += 1
                feature_map[question_id] = rows
            self._evict_locked()

        return FeatureMapResponse(
            section_id=req.section_id,
            segment_id=req.segment_id,
            cache_hits=hits,
            cache_misses=misses,
            feature_map=feature_map,
            generated_at=time.time(),
        )

    def _default_archetypes(self, req: SectionQABatchRequest) -> list[ArchetypeProfile]:
        archetypes: list[ArchetypeProfile] = []
        seg_traits = req.segment.traits or [req.segment.segment_name]
        seed_rng = random.Random(req.deterministic_seed + len(req.questions))
        for i in range(req.segment.archetype_count):
            trait = seg_traits[i % len(seg_traits)]
            label = f"{req.segment.segment_name} archetype {i + 1} ({trait})"
            answers: list[SimulatedAnswer] = []
            for q in req.questions:
                ans = self._default_answer_for_question(q, i, seed_rng)
                answers.append(
                    SimulatedAnswer(
                        question_id=q.question_id,
                        answer=ans,
                        reasons=[
                            f"Aligned with {trait}",
                            f"Matches section objective: {req.objective[:80]}",
                        ],
                        tags=[trait, req.segment.segment_id],
                    )
                )
            archetypes.append(
                ArchetypeProfile(
                    archetype_id=f"{req.segment.segment_id}-a{i+1}",
                    label=label,
                    answers=answers,
                )
            )
        return archetypes

    @staticmethod
    def _default_answer_for_question(q: SimulationQuestion, idx: int, rng: random.Random) -> str:
        if q.question_type in ("single_choice", "multi_choice") and q.options:
            return q.options[idx % len(q.options)]
        if q.question_type == "likert":
            return str(3 + ((idx + rng.randint(0, 1)) % 3))  # 3..5
        return "Needs-based response aligned to objective"

    def get_or_create_archetypes(
        self,
        req: SectionQABatchRequest,
        llm_batch_generator: Optional[Callable[[SectionQABatchRequest], list[ArchetypeProfile]]] = None,
    ) -> tuple[list[ArchetypeProfile], bool]:
        key = self._cache_key(req)
        with self._lock:
            self._evict_locked()
            found = self._cache.get(key)
            if found:
                return found.archetypes, True

        if llm_batch_generator:
            try:
                archetypes = llm_batch_generator(req)
            except Exception:
                archetypes = self._default_archetypes(req)
        else:
            archetypes = self._default_archetypes(req)

        with self._lock:
            self._cache[key] = _ArchetypeCacheEntry(created_at=time.time(), archetypes=archetypes)
            self._evict_locked()
        return archetypes, False

    @staticmethod
    def _rephrase_reason(reason: str, rng: random.Random) -> str:
        swaps = {
            "aligned with": ["fits", "is consistent with", "maps to"],
            "matches": ["tracks", "reflects", "follows"],
            "objective": ["goal", "intent"],
        }
        out = reason
        for src, alternatives in swaps.items():
            if src in out.lower() and rng.random() < 0.5:
                choice = alternatives[rng.randint(0, len(alternatives) - 1)]
                out = out.replace(src, choice).replace(src.title(), choice.title())
        return out

    def apply_local_variations(
        self,
        base_answers: list[SimulatedAnswer],
        respondent_seed: int,
        strength: float,
    ) -> list[SimulatedAnswer]:
        rng = random.Random(respondent_seed)
        varied: list[SimulatedAnswer] = []
        for a in base_answers:
            answer = a.answer
            reasons = list(a.reasons)
            if reasons and rng.random() < (0.2 + 0.6 * strength):
                reasons = [self._rephrase_reason(r, rng) for r in reasons]
                if rng.random() < (0.15 + 0.35 * strength):
                    rng.shuffle(reasons)
            # Small deterministic numeric perturbation where answer is numeric (e.g. likert)
            if answer.isdigit() and rng.random() < (0.15 + 0.35 * strength):
                n = int(answer)
                answer = str(max(1, min(5, n + rng.choice([-1, 0, 1]))))
            varied.append(
                SimulatedAnswer(
                    question_id=a.question_id,
                    answer=answer,
                    reasons=reasons,
                    tags=a.tags,
                )
            )
        return varied

    def simulate_section_batch(
        self,
        req: SectionQABatchRequest,
        llm_batch_generator: Optional[Callable[[SectionQABatchRequest], list[ArchetypeProfile]]] = None,
    ) -> SectionQABatchResponse:
        archetypes, cache_hit = self.get_or_create_archetypes(req, llm_batch_generator=llm_batch_generator)
        respondents: list[RespondentSimulation] = []
        if not archetypes:
            return SectionQABatchResponse(
                section_id=req.section_id,
                section_name=req.section_name,
                objective=req.objective,
                model=req.model,
                cache_hit=cache_hit,
                archetypes=[],
                respondents=[],
                generated_at=time.time(),
            )

        for i in range(req.respondent_count):
            archetype = archetypes[i % len(archetypes)]
            seed = req.deterministic_seed + i * 101 + len(archetype.archetype_id)
            answers = self.apply_local_variations(
                archetype.answers,
                respondent_seed=seed,
                strength=req.segment.variation_strength,
            )
            respondents.append(
                RespondentSimulation(
                    respondent_id=f"{req.segment.segment_id}-r{i+1}",
                    segment_id=req.segment.segment_id,
                    archetype_id=archetype.archetype_id,
                    answers=answers,
                )
            )

        return SectionQABatchResponse(
            section_id=req.section_id,
            section_name=req.section_name,
            objective=req.objective,
            model=req.model,
            cache_hit=cache_hit,
            archetypes=archetypes,
            respondents=respondents,
            generated_at=time.time(),
        )


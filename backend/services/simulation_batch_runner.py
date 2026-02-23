"""Nightly offline simulation batch runner with strict daily token cap."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field

from backend.services.simulation_runtime import SectionQABatchRequest, SectionQABatchResponse, SimulationRuntimeService


class NightlyBatchJob(BaseModel):
    job_id: str
    request: SectionQABatchRequest


class NightlyBatchRunRequest(BaseModel):
    jobs: list[NightlyBatchJob] = Field(default_factory=list)
    daily_token_cap: int = Field(default=50_000_000, ge=10_000)


class NightlyBatchJobResult(BaseModel):
    job_id: str
    status: str  # completed | skipped_budget | failed
    estimated_tokens: int = 0
    error: str | None = None
    response: SectionQABatchResponse | None = None


class NightlyBatchRunResponse(BaseModel):
    run_date: str
    daily_token_cap: int
    used_tokens_before: int
    used_tokens_after: int
    jobs: list[NightlyBatchJobResult] = Field(default_factory=list)


class SimulationNightlyBatchRunner:
    def __init__(
        self,
        runtime: SimulationRuntimeService,
        state_file: str = ".runtime/simulation_budget_state.json",
    ):
        self.runtime = runtime
        self.state_file = state_file

    def _load_state(self) -> dict:
        p = Path(self.state_file)
        if not p.exists():
            return {"date": date.today().isoformat(), "used_tokens": 0}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"date": date.today().isoformat(), "used_tokens": 0}
            return {"date": str(data.get("date") or date.today().isoformat()), "used_tokens": int(data.get("used_tokens") or 0)}
        except Exception:
            return {"date": date.today().isoformat(), "used_tokens": 0}

    def _save_state(self, state: dict) -> None:
        p = Path(self.state_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2), encoding="utf-8")

    @staticmethod
    def estimate_job_tokens(req: SectionQABatchRequest) -> int:
        # Only one LLM call for archetypes; respondent-level variation is local.
        if not req.use_llm_archetypes:
            return 0
        prompt_size_chars = len(req.section_name) + len(req.objective) + len(req.segment.segment_name) + sum(
            len(q.question_text) + sum(len(o) for o in q.options) for q in req.questions
        )
        prompt_est = max(100, int(prompt_size_chars / 4))
        return prompt_est + int(req.llm_max_tokens)

    def run(
        self,
        payload: NightlyBatchRunRequest,
        llm_batch_generator: Optional[Callable[[SectionQABatchRequest], list]] = None,
    ) -> NightlyBatchRunResponse:
        today = date.today().isoformat()
        state = self._load_state()
        if state.get("date") != today:
            state = {"date": today, "used_tokens": 0}

        used_before = int(state.get("used_tokens") or 0)
        used = used_before
        results: list[NightlyBatchJobResult] = []

        for job in payload.jobs:
            est = self.estimate_job_tokens(job.request)
            if used + est > payload.daily_token_cap:
                results.append(
                    NightlyBatchJobResult(
                        job_id=job.job_id,
                        status="skipped_budget",
                        estimated_tokens=est,
                        error="Daily token cap reached; job skipped.",
                    )
                )
                continue
            try:
                resp = self.runtime.simulate_section_batch(job.request, llm_batch_generator=llm_batch_generator)
                used += est
                results.append(
                    NightlyBatchJobResult(
                        job_id=job.job_id,
                        status="completed",
                        estimated_tokens=est,
                        response=resp,
                    )
                )
            except Exception as e:
                results.append(
                    NightlyBatchJobResult(
                        job_id=job.job_id,
                        status="failed",
                        estimated_tokens=est,
                        error=str(e),
                    )
                )

        state["date"] = today
        state["used_tokens"] = used
        self._save_state(state)

        return NightlyBatchRunResponse(
            run_date=today,
            daily_token_cap=payload.daily_token_cap,
            used_tokens_before=used_before,
            used_tokens_after=used,
            jobs=results,
        )


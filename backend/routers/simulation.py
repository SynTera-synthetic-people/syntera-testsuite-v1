"""Simulation API routes."""
import json
import os
from typing import Any

from fastapi import APIRouter

from config.settings import Settings
from backend.utils.llm_gateway import LlmGateway, provider_from_model

from backend.services.simulation_runtime import (
    ArchetypeProfile,
    FeatureMapRequest,
    FeatureMapResponse,
    SectionQABatchRequest,
    SectionQABatchResponse,
    SimulatedAnswer,
    SimulationRuntimeService,
)
from backend.services.simulation_batch_runner import (
    NightlyBatchRunRequest,
    NightlyBatchRunResponse,
    SimulationNightlyBatchRunner,
)

router = APIRouter()
_runtime = SimulationRuntimeService()
_settings = Settings()
_llm_gateway = LlmGateway(_settings)
_nightly_runner = SimulationNightlyBatchRunner(_runtime)


def _extract_json_string(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _to_archetypes(data: Any):
    items = []
    if isinstance(data, dict):
        items = data.get("archetypes") or []
    elif isinstance(data, list):
        items = data
    out: list[ArchetypeProfile] = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        answers = []
        for a in item.get("answers") or []:
            if not isinstance(a, dict):
                continue
            answers.append(
                SimulatedAnswer(
                    question_id=str(a.get("question_id") or ""),
                    answer=str(a.get("answer") or ""),
                    reasons=[str(r) for r in (a.get("reasons") or [])],
                    tags=[str(t) for t in (a.get("tags") or [])],
                )
            )
        out.append(
            ArchetypeProfile(
                archetype_id=str(item.get("archetype_id") or f"a{i}"),
                label=str(item.get("label") or f"Archetype {i}"),
                answers=answers,
            )
        )
    return out


def _llm_batch_generate_archetypes(payload: SectionQABatchRequest):
    model = (payload.model or "").strip()
    if not model:
        model = _settings.OPENAI_MODEL

    schema_instruction = """
Return valid JSON only:
{
  "archetypes": [
    {
      "archetype_id": "string",
      "label": "string",
      "answers": [
        {
          "question_id": "string",
          "answer": "string",
          "reasons": ["string"],
          "tags": ["string"]
        }
      ]
    }
  ]
}
Rules:
- Return exactly {archetype_count} archetypes.
- Include one answer per input question in each archetype.
- Prefer options from the given options list where available.
- Keep reasons concise (1-2 short bullets).
""".strip().replace("{archetype_count}", str(payload.segment.archetype_count))

    q_lines = [
        f"- {q.question_id}: {q.question_text} | type={q.question_type} | options={q.options}"
        for q in payload.questions
    ]

    user_prompt = (
        f"Section: {payload.section_name}\n"
        f"Objective: {payload.objective}\n"
        f"Segment: {payload.segment.segment_name} ({payload.segment.segment_id})\n"
        f"Traits: {', '.join(payload.segment.traits) if payload.segment.traits else 'N/A'}\n"
        f"Questions:\n" + "\n".join(q_lines)
    )

    provider = provider_from_model(model)
    if provider == "anthropic":
        api_key = (_settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        raw = _llm_gateway.complete(
            provider="anthropic",
            model=model,
            system_prompt=schema_instruction + "\nOutput JSON only.",
            user_prompt=user_prompt,
            api_key=api_key,
            max_tokens=payload.llm_max_tokens,
            temperature=0.2,
            response_format_json=False,
        )
    else:
        api_key = (_settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        raw = _llm_gateway.complete(
            provider="openai",
            model=model,
            system_prompt=schema_instruction + "\nOutput JSON only.",
            user_prompt=user_prompt,
            api_key=api_key,
            max_tokens=payload.llm_max_tokens,
            temperature=0.2,
            response_format_json=True,
        )

    parsed = json.loads(_extract_json_string(raw))
    archetypes = _to_archetypes(parsed)
    return archetypes


@router.post("/section-qa-batch", response_model=SectionQABatchResponse)
async def section_qa_batch(payload: SectionQABatchRequest):
    """
    Generate section-level Q&A simulations with:
    - Archetype caching (compute once, reuse respondents)
    - Local deterministic variations (no extra LLM call per respondent)
    """
    llm_cb = _llm_batch_generate_archetypes if payload.use_llm_archetypes else None
    return _runtime.simulate_section_batch(payload, llm_batch_generator=llm_cb)


@router.post("/feature-map/cache", response_model=FeatureMapResponse)
async def precompute_feature_map(payload: FeatureMapRequest):
    """
    Precompute and cache segment/question feature maps (sentiment/themes/tags) from respondent answers.
    Useful for repeated tagging/classification workloads.
    """
    return _runtime.build_feature_map(payload)


@router.post("/nightly-batch/run", response_model=NightlyBatchRunResponse)
async def run_nightly_batch(payload: NightlyBatchRunRequest):
    """
    Offline/nightly simulation runner with strict daily token cap.
    Jobs that exceed remaining budget are skipped.
    """
    cap = int(os.getenv("SIMULATION_DAILY_TOKEN_CAP", str(payload.daily_token_cap)))
    req = NightlyBatchRunRequest(jobs=payload.jobs, daily_token_cap=cap)
    return _nightly_runner.run(req, llm_batch_generator=_llm_batch_generate_archetypes)


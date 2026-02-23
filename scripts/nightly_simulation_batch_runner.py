"""
Nightly offline simulation batch runner.

Usage:
  python scripts/nightly_simulation_batch_runner.py --plan nightly_plan.json --out nightly_result.json

Plan JSON shape:
{
  "daily_token_cap": 50000000,
  "jobs": [
    {
      "job_id": "job-1",
      "request": {
        "section_id": "sec-1",
        "section_name": "Snacking Habits",
        "objective": "Understand behavior",
        "model": "gpt-4o-mini",
        "respondent_count": 200,
        "deterministic_seed": 42,
        "use_llm_archetypes": true,
        "llm_max_tokens": 2500,
        "segment": {
          "segment_id": "urban-genz",
          "segment_name": "Urban Gen Z",
          "traits": ["weekly treat buyer", "health-conscious buyer"],
          "archetype_count": 3,
          "variation_strength": 0.3
        },
        "questions": [
          {"question_id": "q1", "question_text": "How often?", "question_type": "single_choice", "options": ["Daily", "Weekly"]}
        ]
      }
    }
  ]
}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.routers.simulation import _llm_batch_generate_archetypes
from backend.services.simulation_batch_runner import NightlyBatchRunRequest, SimulationNightlyBatchRunner
from backend.services.simulation_runtime import SimulationRuntimeService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="Path to nightly batch plan JSON")
    parser.add_argument("--out", default="nightly_simulation_result.json", help="Output result JSON path")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        raise SystemExit(f"Plan file not found: {plan_path}")

    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    payload = NightlyBatchRunRequest(**raw)

    runtime = SimulationRuntimeService()
    runner = SimulationNightlyBatchRunner(runtime)
    result = runner.run(payload, llm_batch_generator=_llm_batch_generate_archetypes)

    out_path = Path(args.out)
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"Nightly batch completed. Output: {out_path}")
    print(f"Used tokens: {result.used_tokens_before} -> {result.used_tokens_after} / cap={result.daily_token_cap}")


if __name__ == "__main__":
    main()


from backend.services.simulation_batch_runner import (
    NightlyBatchJob,
    NightlyBatchRunRequest,
    SimulationNightlyBatchRunner,
)
from backend.services.simulation_runtime import (
    SectionQABatchRequest,
    SegmentConfig,
    SimulationQuestion,
    SimulationRuntimeService,
)


def _job(job_id: str, use_llm: bool = True, llm_max_tokens: int = 800):
    req = SectionQABatchRequest(
        section_id=f"sec-{job_id}",
        section_name="Section",
        objective="Objective",
        model="gpt-4o-mini",
        respondent_count=10,
        deterministic_seed=1,
        use_llm_archetypes=use_llm,
        llm_max_tokens=llm_max_tokens,
        segment=SegmentConfig(
            segment_id="seg",
            segment_name="Segment",
            traits=["trait"],
            archetype_count=2,
            variation_strength=0.2,
        ),
        questions=[
            SimulationQuestion(
                question_id="q1",
                question_text="Question",
                question_type="single_choice",
                options=["A", "B"],
            )
        ],
    )
    return NightlyBatchJob(job_id=job_id, request=req)


def test_nightly_runner_respects_daily_token_cap(tmp_path):
    runtime = SimulationRuntimeService()
    state = tmp_path / "budget_state.json"
    runner = SimulationNightlyBatchRunner(runtime, state_file=str(state))

    payload = NightlyBatchRunRequest(
        daily_token_cap=10000,
        jobs=[
            _job("j1", use_llm=True, llm_max_tokens=7000),
            _job("j2", use_llm=True, llm_max_tokens=7000),
            _job("j3", use_llm=True, llm_max_tokens=7000),
        ],
    )
    result = runner.run(payload, llm_batch_generator=None)
    statuses = [j.status for j in result.jobs]
    assert "completed" in statuses
    assert "skipped_budget" in statuses
    assert result.used_tokens_after <= payload.daily_token_cap

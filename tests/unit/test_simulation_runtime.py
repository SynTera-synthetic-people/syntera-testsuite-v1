from backend.services.simulation_runtime import (
    FeatureMapRequest,
    RespondentSimulation,
    SectionQABatchRequest,
    SegmentConfig,
    SimulatedAnswer,
    SimulationQuestion,
    SimulationRuntimeService,
)


def _sample_batch_request(use_llm: bool = False):
    return SectionQABatchRequest(
        section_id="sec-1",
        section_name="Snacking Habits",
        objective="Understand preferences",
        model="gpt-4o-mini",
        respondent_count=6,
        deterministic_seed=42,
        use_llm_archetypes=use_llm,
        llm_max_tokens=1200,
        segment=SegmentConfig(
            segment_id="urban-genz",
            segment_name="Urban Gen Z",
            traits=["health-conscious buyer", "weekly treat buyer"],
            archetype_count=2,
            variation_strength=0.3,
        ),
        questions=[
            SimulationQuestion(
                question_id="q1",
                question_text="How often do you buy snacks?",
                question_type="single_choice",
                options=["Daily", "Weekly", "Monthly"],
            ),
            SimulationQuestion(
                question_id="q2",
                question_text="How healthy are your snacks?",
                question_type="likert",
                options=["1", "2", "3", "4", "5"],
            ),
        ],
    )


def test_simulate_section_batch_returns_expected_shapes():
    runtime = SimulationRuntimeService()
    req = _sample_batch_request()
    result = runtime.simulate_section_batch(req)
    assert result.section_id == "sec-1"
    assert len(result.archetypes) == req.segment.archetype_count
    assert len(result.respondents) == req.respondent_count
    assert all(r.answers for r in result.respondents)


def test_feature_map_cache_hits_on_repeat():
    runtime = SimulationRuntimeService()
    respondents = [
        RespondentSimulation(
            respondent_id="r1",
            segment_id="urban-genz",
            archetype_id="a1",
            answers=[
                SimulatedAnswer(question_id="q1", answer="Sugar-free", reasons=["Health"], tags=[]),
                SimulatedAnswer(question_id="q2", answer="Good value", reasons=["Price"], tags=[]),
            ],
        ),
        RespondentSimulation(
            respondent_id="r2",
            segment_id="urban-genz",
            archetype_id="a2",
            answers=[
                SimulatedAnswer(question_id="q1", answer="Sugar-free", reasons=["Health"], tags=[]),
                SimulatedAnswer(question_id="q2", answer="Good value", reasons=["Price"], tags=[]),
            ],
        ),
    ]
    req = FeatureMapRequest(section_id="sec-1", segment_id="urban-genz", respondents=respondents)
    first = runtime.build_feature_map(req)
    second = runtime.build_feature_map(req)
    assert first.cache_misses >= 1
    assert second.cache_hits >= first.cache_misses

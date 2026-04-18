"""
Test Lab — LLM verdict layer (contract for Pranjal / implementers).

The LLM compares structured insights from the human survey narrative and the
Synthetic People (SP) run, then fills `test_lab_profiles.verdict`:
  - what_matches: list[str]
  - where_it_differs: list[str]
  - why_the_difference: list[str]
  - summary_statement: str (optional)

Inputs to assemble for the user message typically include:
  - Profile: human_study, synthetic_study, industry, scenario, geography
  - Survey: test_suite_report summary, study_metrics, accuracy_score

Replace SYSTEM_PROMPT_PLACEHOLDER with the final system prompt.
"""

# Pranjal: replace this with the production system prompt.
VERDICT_SYSTEM_PROMPT_PLACEHOLDER = """You are an expert research methodologist.

Given structured summaries of a human survey and a Synthetic People simulation
for the same study design, produce:
1) what_matches — bullet points where conclusions or patterns align
2) where_it_differs — bullet points where they diverge (magnitude, segments, wording)
3) why_the_difference — plausible methodological reasons (not blame)
4) summary_statement — one short paragraph for executives

Use neutral, precise language. Output valid JSON only with keys:
what_matches, where_it_differs, why_the_difference, summary_statement.
"""


def build_verdict_user_payload_stub(human_block: str, synthetic_block: str) -> str:
    """Example shape for the user message body (implement with real serialization)."""
    return f"""Human study summary:\n{human_block}\n\nSynthetic People summary:\n{synthetic_block}\n"""

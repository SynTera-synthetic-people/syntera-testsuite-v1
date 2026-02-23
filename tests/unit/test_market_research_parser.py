from backend.routers.market_research import _parse_structured_output, _split_list_items


def test_split_list_items_preserves_hyphenated_words():
    text = """
    - Sugar-free
    - Ready-to-eat
    - Low fat
    """
    items = _split_list_items(text)
    assert items == ["Sugar-free", "Ready-to-eat", "Low fat"]


def test_parse_structured_output_keeps_hyphenated_options_and_values_aligned():
    raw = """
A. Overall Research Objectives
- Overall sample size (n): 100
- Understand purchase patterns

B. Section-wise Objectives
- Snacking Habits: Understand product preference

C. Reconstructed Questionnaire
- Report Reference: Figure 4
- Research Intent: Measure preference by product type
- Survey Question: Which snack type do you prefer?
- Question Type: Single choice
- Answer Options:
  - Sugar-free
  - Ready-to-eat
  - Low-fat
- Report Output:
  - 40
  - 35
  - 25
- Sample size (n): 100
- Target Segment: All respondents
- Expected Output Pattern: Bar chart
"""
    overall, overall_n, sections, questions = _parse_structured_output(raw)

    assert overall_n == 100
    assert len(sections) == 1
    assert len(questions) == 1

    q = questions[0]
    assert q["answer_options"] == ["Sugar-free", "Ready-to-eat", "Low-fat"]
    assert q["option_values"] == ["40", "35", "25"]

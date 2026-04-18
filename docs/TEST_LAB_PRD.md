# Test Lab PRD

## Objective
Build a confidence-inspiring `Test Lab` that proves Human vs Synthetic similarity for:
- Website viewers (high-level trust signal)
- Enterprise prospects and investors (deal-closing validation workflow)

## Stakeholders and Modes
- Public viewers: read-only dashboard, high impact, minimal complexity.
- Expert viewers: detailed methodology and question-level evidence.
- Sales/investor demos: run a known historical survey live and compare against SP output.

## UX Layers
### Layer 1: Executive Dashboard
- Tests Conducted
- Avg Similarity
- Avg Directional Alignment
- Scenarios Covered (count + mix)
- Industries Covered (count + mix)

### Layer 2: Detailed Comparison
- Question-level similarity and tier
- Option-level side-by-side counts
- Method transparency and confidence language
- Verdict block: `What Matches`, `Where It Differs`, `Why the Difference`

## Key Metric Definitions
- Tests Conducted: number of validated runs.
- Avg Similarity: mean of run-level similarity scores.
- Avg Directional Alignment: fraction of questions where top synthetic option equals top human option.
- Scenarios Covered: unique scenario labels and distribution.
- Industries Covered: unique industry labels and distribution.

## Human Study Summary Box
- Survey name
- Target audience
- Geography
- Sample size
- Number of questions
- Industry
- Scenario
- Estimated cost: sample_size * $5 to sample_size * $8
- Estimated time:
  - 1000-2000 -> 1-2 weeks
  - 2001-4000 -> 2-3 weeks
  - 4001-6000 -> 3-4 weeks
  - 6000+ -> 4-5 weeks
- Estimated effort: 80-120 hours

## Synthetic People Summary Box
- Sample size
- Actions data points
- Neuroscience data points
- Contextual layer data points
- Statistical outputs from validation engine
- Economics (static values from design)

## Lead Capture
On `View Detailed Comparison` CTA:
- Required: name, company name, email
- Persist to PostgreSQL
- Trigger downstream email to humans@synthetic-people.ai
- Also push to CRM integration service

## Non-Goals (Phase 1)
- No external BI tool requirement
- No advanced cohort slicing in first release
- No custom PDF layout builder in backend phase

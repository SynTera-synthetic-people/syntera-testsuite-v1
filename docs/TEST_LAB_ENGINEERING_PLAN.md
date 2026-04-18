# Test Lab Engineering Plan and Data Contract

## Scope Delivered
- PostgreSQL persistence for Test Lab profile metadata
- PostgreSQL persistence for detailed-comparison lead capture
- Metrics endpoint for Layer 1 dashboard
- API contract for profile, lead capture, and metrics

## Database Tables
### `test_lab_profiles`
- `id` (pk)
- `survey_id` (unique, indexed)
- `industry` (indexed)
- `scenario` (indexed)
- `human_study` (json)
- `synthetic_study` (json)
- `verdict` (json)
- `metadata` (json)
- `created_at`, `updated_at`

### `test_lab_leads`
- `id` (pk)
- `survey_id` (indexed)
- `name`
- `company_name`
- `email` (indexed)
- `consent` (boolean)
- `source`
- `metadata` (json)
- `created_at`, `updated_at`

## API Endpoints
### 1) Upsert profile
`POST /api/validation/test-lab/profile/{survey_id}`

Body:
```json
{
  "industry": "Healthcare",
  "scenario": "Product Launch",
  "human_study": {
    "survey_name": "Q4 Pulse Survey",
    "target_audience": "Urban adults 25-45",
    "geography": "India",
    "sample_size": 2600,
    "total_questions": 24,
    "economics": {}
  },
  "synthetic_study": {
    "sample_size": 2600,
    "actions_data_points": 120000,
    "neuroscience_data_points": 45000,
    "contextual_layer_data_points": 22000,
    "economics": {},
    "statistics": {}
  },
  "verdict": {
    "what_matches": ["Price sensitivity pattern is similar"],
    "where_it_differs": ["Slightly higher brand loyalty in SP"],
    "why_the_difference": ["SP weighs prior category exposure differently"],
    "llm_confidence": 0.83
  },
  "metadata": {}
}
```

Rules:
- Human economics auto-filled if missing:
  - cost min = sample_size * 5
  - cost max = sample_size * 8
  - time bucket by sample size
  - effort default = `80-120 hours`

### 2) Get profile
`GET /api/validation/test-lab/profile/{survey_id}`

Returns persisted profile payload for rendering summary boxes and verdict.

### 3) Lead capture
`POST /api/validation/test-lab/lead-capture/{survey_id}`

Body:
```json
{
  "name": "Jane Doe",
  "company_name": "Unilever",
  "email": "jane@unilever.com",
  "consent": true,
  "source": "view_detailed_comparison",
  "metadata": {
    "campaign": "website_test_lab"
  }
}
```

Returns:
- `lead_id`
- `survey_id`
- `email_delivery_target` = `humans@synthetic-people.ai`

### 4) Dashboard metrics
`GET /api/validation/test-lab/metrics`

Returns:
```json
{
  "tests_conducted": 120,
  "avg_similarity": 0.89,
  "avg_directional_alignment": 0.82,
  "scenarios_covered": {
    "count": 5,
    "mix": {"Pricing": 22, "Adoption": 33}
  },
  "industries_covered": {
    "count": 6,
    "mix": {"Healthcare": 18, "Ecommerce": 27}
  }
}
```

## Calculation Notes
- `avg_similarity`: average of survey `accuracy_score` on validated surveys.
- `avg_directional_alignment`: for each question, compare option with max synthetic count vs max real count; alignment is ratio of matches.

## Integration Notes
- Tables are created by SQLAlchemy `create_all` for new deployments.
- For existing environments, ensure app startup imports models so new tables are created.
- If using migration tooling later, add equivalent migration scripts for these two tables.

## Next Backend Steps
- Add async notifier/email service hook on lead capture.
- Add CRM adapter worker for lead sync (HubSpot/Salesforce).
- Add scenario/industry extraction from reverse-engineering output into profile defaults.

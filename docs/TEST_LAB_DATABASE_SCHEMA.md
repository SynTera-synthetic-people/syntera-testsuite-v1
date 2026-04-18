# Test Lab database schema (canonical)

This document is the **canonical Test Lab relational model**. Any change to Test Lab persistence must keep **SQLAlchemy** (`backend/models/survey.py`), **bootstrap DDL** (`database/connection.py` → `init_db`), and this file **in sync**.

## Entity relationships

```mermaid
erDiagram
    TEST_LAB_SURVEYS ||--|| TEST_LAB_PROFILES : defined_by
    TEST_LAB_SURVEYS ||--o{ TEST_LAB_VALIDATION_RUNS : historical_log
    TEST_LAB_SURVEYS ||--o{ TEST_LAB_LEADS : source_attribution

    TEST_LAB_SURVEYS {
        string id PK
        string title
        text description
        int total_personas
        int total_questions
        float accuracy_score
        float avg_similarity
        int actions_data_points
        int neuroscience_data_points
        int contextual_layer_data_points
        float directional_alignment
        float avg_prediction_accuracy
        float avg_relationship_strength
        int checks_passed
        string confidence_tier
        string validation_status
        timestamptz validated_at
        jsonb synthetic_personas
        jsonb survey_questions
        jsonb synthetic_responses
        jsonb real_responses
        jsonb test_suite_report
        timestamptz created_at
        timestamptz updated_at
    }

    TEST_LAB_PROFILES {
        string id PK
        string survey_id FK UK
        string geography
        string industry
        string scenario
        jsonb human_study
        jsonb synthetic_study
        jsonb verdict
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
    }

    TEST_LAB_VALIDATION_RUNS {
        string id PK
        string survey_id FK
        float overall_accuracy
        string overall_tier
        jsonb question_results
        jsonb comparison_metadata
        timestamptz created_at
        timestamptz updated_at
    }

    TEST_LAB_LEADS {
        string id PK
        string survey_id FK
        string name
        string company_name
        string email
        string source
        boolean consent
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
    }
```

## Relationship semantics

| Relationship (ERD) | Implementation |
|--------------------|----------------|
| **defined_by** | One `test_lab_profiles` row per survey (`survey_id` **UNIQUE**). Profile holds human/synthetic study JSON and verdict payload. |
| **historical_log** | Many `test_lab_validation_runs` rows per survey (`survey_id` indexed). Each run stores `question_results` JSON. |
| **source_attribution** | Many `test_lab_leads` rows per survey (`survey_id` indexed). Lead capture from Test Lab UI. |

## Physical table names

| Logical (ERD) | PostgreSQL table | SQLAlchemy class |
|-----------------|------------------|------------------|
| TEST_LAB_SURVEYS | `test_lab_surveys` | `Survey` |
| TEST_LAB_PROFILES | `test_lab_profiles` | `TestLabProfile` |
| TEST_LAB_VALIDATION_RUNS | `test_lab_validation_runs` | `ValidationRun` |
| TEST_LAB_LEADS | `test_lab_leads` | `TestLabLead` |

## Verdict column

The ERD may show verdict as free text. In Postgres we store **`verdict` as JSONB** so the UI can persist structured fields (`what_matches`, `where_it_differs`, `summary_statement`, `source`, etc.) without losing the conceptual “verdict” entity on `test_lab_profiles`.

## Extensions beyond the baseline ERD

These exist in code and production DB for product needs; document them here when they change.

| Table | Purpose |
|-------|---------|
| `test_lab_surveys` | Extra scalar metrics (`avg_similarity`, `directional_alignment`, …) and `test_suite_report` JSONB for engine output, question-level comparisons, and embedded `study_metrics`. |
| `test_lab_reports` | Optional `TestLabReport` model: stable render snapshot per survey (see `survey.py`). Created in `init_db` if missing. |
| `market_research_extractions` | Separate feature; not part of the Test Lab ERD above. |

## Change checklist

1. Update **`backend/models/survey.py`** (`__tablename__`, columns, types).
2. For existing deployments, add **`ALTER TABLE … ADD COLUMN IF NOT EXISTS`** (or equivalent) in **`database/connection.py`** inside `init_db` (create_all does not migrate new columns).
3. Update **this document** (Mermaid + tables) and any API serializers that expose the new fields.
4. Run smoke tests: validation run, reports list, profile upsert, lead capture.

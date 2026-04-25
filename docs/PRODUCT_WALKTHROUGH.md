# SynTera Test Suite — Product walkthrough and understanding

This document explains **what the product is**, **who it is for**, and **how to use the UI step by step**. Technical deployment is covered in [INSTALLATION.md](INSTALLATION.md); system design in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. What is SynTera Test Suite?

SynTera Test Suite is a **web application plus API** used to:

- **Compare synthetic survey outputs with human (real) survey outputs** using statistical tests and file-based questionnaire comparison.
- **Track studies** in a **Test Lab**: each validated survey can show a structured “Human vs Synthetic” summary, economics-style hints, and a **Verdict** block (rule-based insights from question-level similarity).
- **Explore industry reference materials** (optional S3-backed file browser).
- **Reverse-engineer questionnaire structure** from long-form market research text or PDFs (optional LLM features).
- **Run simulation-style LLM flows** for advanced experimentation (optional keys).

The same server serves the **single-page dashboard** (`app/index.html` + static JS/CSS) and the **REST API** under `/api/...`.

---

## 2. Who uses it?

| Persona | Typical goals |
|--------|----------------|
| **Analyst / researcher** | Upload synthetic vs real files, read accuracy and per-question comparison, download HTML/JSON reports. |
| **Product / QA** | Use Dashboard & Reports to see validation health across studies; open detailed comparison from a study card. |
| **Authenticated “super” user** | Same as above, plus delete survey reports and access extra nav sections depending on configuration. |
| **Visitor (not logged in)** | Still open **Dashboard & Reports** and **Results** (e.g. after following a link); login is required for other areas. |

---

## 3. How you open the product

1. After the server is running (see [INSTALLATION.md](INSTALLATION.md)), open a browser to **`http://localhost:8000`** (or your deployed host).
2. The **home page** loads the main shell: sidebar navigation, content area, and (if assets are present) the **Omi** narrator widget for lightweight guidance.

---

## 4. Step-by-step: Dashboard & Reports

**Purpose:** High-level metrics and a **paginated list of validated studies** (Test Lab style cards: Human study, Synthetic simulation, Verdict).

1. Click **Dashboard & Reports** (or **Reports**) in the sidebar.
2. The **dashboard strip** shows aggregate numbers (total surveys, validated count, averages where the backend exposes Test Lab metrics).
3. Below, **each “page”** shows one study card (pagination controls if there are many studies).
4. Each card pulls **survey facts** from the API (accuracy, directional alignment, checks, etc.) and **profile** data (geography, industry, scenario, human/synthetic JSON, verdict JSON).
5. **View detailed comparison** opens a lead-capture modal (name, company, email); after submit, the app navigates to **Results** for that survey.
6. **HTML / JSON** buttons download report artifacts via the reports API.

**Note:** First-time visitors may see **Dashboard & Reports** without logging in; protected sections redirect to login when needed.

---

## 5. Step-by-step: Logging in

1. Use the **login** entry in the UI (sidebar or login panel, depending on skin).
2. Enter **username** (the backend resolves this to **email** or **full name** in the shared users table) and **password**.
3. On success you receive a **JWT** stored in the browser; the session also tracks **last activity** for idle logout (see architecture doc).
4. **Super** vs **user** roles control visibility of destructive actions (e.g. delete report) and some navigation items.

---

## 6. Step-by-step: Surveys

1. Open **Surveys** (requires login).
2. See a simple list of surveys created in the system.
3. **Create** prompts for a title and creates a survey via `POST /api/surveys/`.

Surveys are the **anchor entity** for validation runs, file comparisons, and Test Lab profiles.

---

## 7. Step-by-step: Validation runs

**Purpose:** Attach numeric synthetic vs real arrays to a survey **or** compare **Excel/CSV** files.

### 7a. Manual JSON comparison (advanced)

1. Open **Validation runs**.
2. Enter **Survey ID**, paste **synthetic** and **real** responses as JSON arrays, then run validation.
3. Results are stored; you are taken to **Results** to inspect tests and summaries.

### 7b. File comparison (typical)

1. Open **Validation runs**.
2. Choose **synthetic** and **real** files (`.xlsx`, `.xls`, `.csv` within size limits shown in the UI).
3. Optionally enter an existing **survey ID** to attach the run to that survey; otherwise a new survey may be created as part of the flow.
4. Choose extraction method if offered (**totals** vs **all**).
5. Submit; the backend parses files, builds **question-level comparisons** when question metadata exists, runs the **comparison engine**, updates the survey, syncs **study metrics** and **Test Lab profile** fields where applicable.
6. You land on **Results** with charts/tables; Dashboard & Reports refresh from cached survey list invalidation.

---

## 8. Step-by-step: Results

1. Open **Results** from the nav, or arrive here automatically after a validation run.
2. Content is driven from **session storage** (last run) and/or a fresh fetch from **`GET /api/validation/results/{survey_id}`** when an ID is known.
3. Inspect per-test outputs, tiers, and narrative summaries as implemented in the UI.

---

## 9. Step-by-step: Industry surveys

1. Open **Industry surveys**.
2. If **AWS** credentials and bucket settings are configured, the UI lists **S3** objects under the configured prefix for browsing/downloading reference material.
3. If S3 is not configured, the section may show errors or empty states depending on implementation.

---

## 10. Step-by-step: Market research reverse engineering

1. Open **Market research** (wording may vary slightly in the nav).
2. Paste report text or upload a **PDF** (limits apply).
3. The backend uses configured **OpenAI / Anthropic** models (when keys exist) to extract objectives, questionnaire drafts, etc.
4. Without API keys, this flow will not succeed until keys are set in `.env`.

---

## 11. Step-by-step: Simulation (API-backed UI sections)

If your build exposes **Simulation** features, they call **`/api/simulation/...`** endpoints backed by `SimulationRuntimeService` and optional nightly batch runners. Exact UI steps depend on the current `app/index.html` wiring; refer to the **Simulation** section in the sidebar if present.

---

## 12. Concepts glossary

| Term | Meaning |
|------|--------|
| **Survey** | Row in `test_lab_surveys`: title, validation status, JSON blobs for personas/questions/responses, `test_suite_report` for engine output. |
| **Test Lab profile** | Row in `test_lab_profiles` (1:1 with survey): `human_study`, `synthetic_study`, `verdict`, geography/industry/scenario. |
| **Validation run** | Historical log row in `test_lab_validation_runs` for a comparison event. |
| **Study metrics** | Denormalized numbers on the survey and/or embedded under `test_suite_report.study_metrics` for fast list views. |
| **Verdict** | Structured JSON on the profile: bullets + `summary_statement`; may be **rule-based** (from question similarities) unless **manual** overrides. |

---

## 13. Where to go next

| Need | Document |
|------|----------|
| Install and run locally | [INSTALLATION.md](INSTALLATION.md) |
| Components, APIs, data flow | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Canonical DB tables for Test Lab | [TEST_LAB_DATABASE_SCHEMA.md](TEST_LAB_DATABASE_SCHEMA.md) |

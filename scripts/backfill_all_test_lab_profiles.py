"""
One-shot backfill: align all TestLabProfile rows with current default rules.

- Survey name: parsed from File Comparison titles (see validation._default_study_name_for_survey)
- Geography: India
- Industry: derived from study name (Food, Automotive/EV, else General)
- Human study: age-group audience, economics from respondent rule
- Synthetic study: cost_display $999

Usage (from repo root):
  set DATABASE_URL=postgresql://...
  python scripts/backfill_all_test_lab_profiles.py
"""
from __future__ import annotations

import copy
import random
import sys
from pathlib import Path

# Repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from backend.models.survey import Survey, TestLabProfile  # noqa: E402
from backend.routers.validation import (  # noqa: E402
    _build_rule_based_verdict,
    _build_human_economics,
    _default_industry_from_study_name,
    _default_study_name_for_survey,
)
from backend.utils.json_helpers import sanitize_for_json  # noqa: E402
from database.connection import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        surveys = db.query(Survey).all()
        created = 0
        for s in surveys:
            p = db.query(TestLabProfile).filter(TestLabProfile.survey_id == s.id).first()
            if not p:
                p = TestLabProfile(survey_id=s.id)
                db.add(p)
                db.flush()
                created += 1

            effective = _default_study_name_for_survey(s)
            industry = _default_industry_from_study_name(effective)

            p.geography = "India"
            p.industry = industry
            if not p.scenario:
                p.scenario = "General consumer behavior study"

            hs = copy.deepcopy(p.human_study if isinstance(p.human_study, dict) else {})
            sample = int(hs.get("sample_size") or s.total_personas or 1000)
            hs["survey_name"] = effective
            hs["target_audience"] = "Age group: 18-45 years"
            hs["geography"] = p.geography
            hs["sample_size"] = sample
            hs["total_questions"] = int(hs.get("total_questions") or s.total_questions or 10)
            hs["economics"] = _build_human_economics(sample, None)
            p.human_study = sanitize_for_json(hs)
            flag_modified(p, "human_study")

            ss = copy.deepcopy(p.synthetic_study if isinstance(p.synthetic_study, dict) else {})
            ss_sample = int(ss.get("sample_size") or sample)
            ss["sample_size"] = ss_sample
            econ = ss.get("economics") if isinstance(ss.get("economics"), dict) else {}
            econ["cost_display"] = "$999"
            econ.setdefault("time_display", "3-4 hrs")
            econ.setdefault("effort_display", "1-2 hrs")
            ss["economics"] = econ
            if not isinstance(ss.get("statistics"), dict):
                ss["statistics"] = {}
            st = ss["statistics"]
            acc = s.accuracy_score
            if acc is not None:
                st.setdefault("avg_prediction_accuracy", acc)
                st.setdefault("avg_relationship_strength", acc)
            ss.setdefault("actions_data_points", random.randint(100000, 700000))
            ss.setdefault("neuroscience_data_points", random.randint(100000, 700000))
            ss.setdefault("contextual_conversation_threads", random.randint(1000, 7000))
            ss.setdefault("contextual_sources_inferred", random.randint(100, 700))
            ss.setdefault("contextual_layer_data_points", random.randint(10000, 70000))
            p.synthetic_study = sanitize_for_json(ss)
            flag_modified(p, "synthetic_study")

            v = copy.deepcopy(p.verdict if isinstance(p.verdict, dict) else {})
            v.setdefault("what_matches", [])
            v.setdefault("where_it_differs", [])
            v.setdefault("why_the_difference", [])
            v.setdefault("summary_statement", None)
            p.verdict = sanitize_for_json(v)
            flag_modified(p, "verdict")

            if acc is not None:
                if getattr(s, "avg_prediction_accuracy", None) is None:
                    s.avg_prediction_accuracy = acc
                if getattr(s, "avg_relationship_strength", None) is None:
                    s.avg_relationship_strength = acc
            # Keep survey-level study metric columns aligned with persisted synthetic-study values.
            try:
                s.actions_data_points = int(ss.get("actions_data_points")) if ss.get("actions_data_points") is not None else s.actions_data_points
            except (TypeError, ValueError):
                pass
            try:
                s.neuroscience_data_points = int(ss.get("neuroscience_data_points")) if ss.get("neuroscience_data_points") is not None else s.neuroscience_data_points
            except (TypeError, ValueError):
                pass
            try:
                s.contextual_layer_data_points = int(ss.get("contextual_layer_data_points")) if ss.get("contextual_layer_data_points") is not None else s.contextual_layer_data_points
            except (TypeError, ValueError):
                pass

            # For old validated runs, derive verdict from stored question-level similarities.
            report = s.test_suite_report if isinstance(s.test_suite_report, dict) else {}
            qc = report.get("question_comparisons") if isinstance(report.get("question_comparisons"), list) else []
            if qc:
                existing_source = str(v.get("source") or "").strip().lower()
                if existing_source != "manual":
                    p.verdict = sanitize_for_json(_build_rule_based_verdict(qc))
                    flag_modified(p, "verdict")

        db.commit()
        total_p = db.query(TestLabProfile).count()
        print(f"OK surveys={len(surveys)} profiles={total_p} profiles_created={created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

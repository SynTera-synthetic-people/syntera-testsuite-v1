"""JSON Serialization Helpers - Handle NaN and inf values"""
import math
from typing import Any, Dict

# Legacy / mistaken labels → canonical Test Lab signal name
_LEGACY_REASON_SIGNAL_LABELS = frozenset({"Reason / Explanation", "Reason"})


def normalize_signal_category_label(value: Any) -> str:
    """Canonical survey-signal category for reason-style questions."""
    s = str(value or "").strip()
    if s in _LEGACY_REASON_SIGNAL_LABELS:
        return "Reasoning"
    return s


def migrate_signal_category_labels(obj: Any) -> Any:
    """
    Recursively rename legacy reason categories to "Reasoning" on question_category
    and any string "category" field (e.g. avgSimilarityByCategory rows).
    """
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if k in ("question_category", "category") and isinstance(v, str):
                out[k] = normalize_signal_category_label(v)
            else:
                out[k] = migrate_signal_category_labels(v)
        return out
    if isinstance(obj, list):
        return [migrate_signal_category_labels(x) for x in obj]
    return obj


def test_suite_report_has_legacy_reason_label(obj: Any) -> bool:
    """True if any question_category or category string still uses a legacy reason label."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("question_category", "category") and isinstance(v, str) and v in _LEGACY_REASON_SIGNAL_LABELS:
                return True
            if test_suite_report_has_legacy_reason_label(v):
                return True
        return False
    if isinstance(obj, list):
        return any(test_suite_report_has_legacy_reason_label(x) for x in obj)
    return False


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize an object to be JSON-compliant.
    Replaces NaN, inf, and -inf with None or 0.
    """
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        elif math.isinf(obj):
            return None if obj > 0 else None
        return obj
    elif isinstance(obj, dict):
        return {key: sanitize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (int, str, bool, type(None))):
        return obj
    else:
        # For other types (like datetime), convert to string
        try:
            return str(obj)
        except:
            return None


def survey_to_dict(survey) -> Dict[str, Any]:
    """
    Convert a Survey SQLAlchemy model to a dictionary with sanitized values.
    """
    if survey is None:
        return {}
    
    avg_sim = survey.avg_similarity if getattr(survey, "avg_similarity", None) is not None else survey.accuracy_score
    result = {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "total_personas": survey.total_personas,
        "total_questions": survey.total_questions,
        "accuracy_score": sanitize_for_json(survey.accuracy_score),
        "avg_similarity": sanitize_for_json(avg_sim),
        "actions_data_points": survey.actions_data_points,
        "neuroscience_data_points": survey.neuroscience_data_points,
        "contextual_layer_data_points": survey.contextual_layer_data_points,
        "directional_alignment": sanitize_for_json(survey.directional_alignment),
        "avg_prediction_accuracy": sanitize_for_json(getattr(survey, "avg_prediction_accuracy", None)),
        "avg_relationship_strength": sanitize_for_json(getattr(survey, "avg_relationship_strength", None)),
        "checks_passed": survey.checks_passed,
        "study_metrics": sanitize_for_json(
            {
                "actions_data_points": survey.actions_data_points,
                "neuroscience_data_points": survey.neuroscience_data_points,
                "contextual_layer_data_points": survey.contextual_layer_data_points,
                "avg_similarity": avg_sim,
                "directional_alignment": survey.directional_alignment,
                "avg_prediction_accuracy": getattr(survey, "avg_prediction_accuracy", None),
                "avg_relationship_strength": getattr(survey, "avg_relationship_strength", None),
                "checks_passed": survey.checks_passed,
            }
        ),
        "llm_accuracy_score": sanitize_for_json(getattr(survey, "llm_accuracy_score", None)),
        "llm_avg_similarity": sanitize_for_json(getattr(survey, "llm_avg_similarity", None)),
        "llm_directional_alignment": sanitize_for_json(getattr(survey, "llm_directional_alignment", None)),
        "llm_avg_prediction_accuracy": sanitize_for_json(getattr(survey, "llm_avg_prediction_accuracy", None)),
        "llm_avg_relationship_strength": sanitize_for_json(getattr(survey, "llm_avg_relationship_strength", None)),
        "llm_checks_passed": getattr(survey, "llm_checks_passed", None),
        "validation_status": survey.validation_status,
        "synthetic_personas": sanitize_for_json(survey.synthetic_personas),
        "survey_questions": sanitize_for_json(survey.survey_questions),
        "synthetic_responses": sanitize_for_json(survey.synthetic_responses),
        "real_responses": sanitize_for_json(survey.real_responses),
        "llm_output": sanitize_for_json(getattr(survey, "llm_output", None)),
        "llm_responses": sanitize_for_json(getattr(survey, "llm_responses", None)),
        "test_suite_report": sanitize_for_json(
            migrate_signal_category_labels(survey.test_suite_report)
            if isinstance(survey.test_suite_report, dict)
            else survey.test_suite_report
        ),
    }
    
    # Add datetime fields as ISO strings
    if survey.created_at:
        result["created_at"] = survey.created_at.isoformat()
    if survey.validated_at:
        result["validated_at"] = survey.validated_at.isoformat()
    if survey.updated_at:
        result["updated_at"] = survey.updated_at.isoformat()
    
    return result


def _slim_questionnaire_blob(obj: Any, count_key: str) -> Any:
    """Keep file metadata without shipping large question_data arrays (list views)."""
    if not isinstance(obj, dict):
        return sanitize_for_json(obj)
    out: Dict[str, Any] = {}
    for k in ("source_file", "extraction_method", "filename", "source_path"):
        if k in obj and obj[k] is not None:
            out[k] = obj[k]
    qd = obj.get("question_data")
    if isinstance(qd, list):
        out[count_key] = len(qd)
    return sanitize_for_json(out)


def _slim_test_suite_report_for_list(report: Any) -> Any:
    """Report fields needed for dashboard/reports cards; omit heavy engine-only blobs."""
    if not isinstance(report, dict):
        return sanitize_for_json(report)
    report = migrate_signal_category_labels(dict(report))
    keys = (
        "question_comparisons",
        "llm_question_comparisons",
        "llm_overall_accuracy",
        "tests",
        "test_summary",
        "study_metrics",
        "overall_accuracy",
        "recommendations",
        "synthetic_size",
        "real_size",
    )
    slim = {k: report[k] for k in keys if k in report}
    return sanitize_for_json(slim)


def survey_to_summary_dict(survey) -> Dict[str, Any]:
    """
    Lightweight survey for GET /api/surveys?summary=1 (dashboard + reports lists).

    Omits raw response arrays and full questionnaire payloads; keeps metrics, slim report,
    and questionnaire row counts for UI fallbacks.
    """
    if survey is None:
        return {}

    avg_sim = survey.avg_similarity if getattr(survey, "avg_similarity", None) is not None else survey.accuracy_score
    result: Dict[str, Any] = {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "total_personas": survey.total_personas,
        "total_questions": survey.total_questions,
        "accuracy_score": sanitize_for_json(survey.accuracy_score),
        "avg_similarity": sanitize_for_json(avg_sim),
        "actions_data_points": survey.actions_data_points,
        "neuroscience_data_points": survey.neuroscience_data_points,
        "contextual_layer_data_points": survey.contextual_layer_data_points,
        "directional_alignment": sanitize_for_json(survey.directional_alignment),
        "avg_prediction_accuracy": sanitize_for_json(getattr(survey, "avg_prediction_accuracy", None)),
        "avg_relationship_strength": sanitize_for_json(getattr(survey, "avg_relationship_strength", None)),
        "checks_passed": survey.checks_passed,
        "study_metrics": sanitize_for_json(
            {
                "actions_data_points": survey.actions_data_points,
                "neuroscience_data_points": survey.neuroscience_data_points,
                "contextual_layer_data_points": survey.contextual_layer_data_points,
                "avg_similarity": avg_sim,
                "directional_alignment": survey.directional_alignment,
                "avg_prediction_accuracy": getattr(survey, "avg_prediction_accuracy", None),
                "avg_relationship_strength": getattr(survey, "avg_relationship_strength", None),
                "checks_passed": survey.checks_passed,
            }
        ),
        "llm_accuracy_score": sanitize_for_json(getattr(survey, "llm_accuracy_score", None)),
        "llm_avg_similarity": sanitize_for_json(getattr(survey, "llm_avg_similarity", None)),
        "validation_status": survey.validation_status,
        "synthetic_personas": _slim_questionnaire_blob(survey.synthetic_personas, "_question_data_count"),
        "survey_questions": _slim_questionnaire_blob(survey.survey_questions, "_question_data_count"),
        "llm_output": _slim_questionnaire_blob(getattr(survey, "llm_output", None), "_question_data_count"),
        "test_suite_report": _slim_test_suite_report_for_list(survey.test_suite_report),
    }

    if survey.created_at:
        result["created_at"] = survey.created_at.isoformat()
    if survey.validated_at:
        result["validated_at"] = survey.validated_at.isoformat()
    if survey.updated_at:
        result["updated_at"] = survey.updated_at.isoformat()

    return result

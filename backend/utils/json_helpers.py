"""JSON Serialization Helpers - Handle NaN and inf values"""
import json
import math
from typing import Any, Dict


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
        "validation_status": survey.validation_status,
        "synthetic_personas": sanitize_for_json(survey.synthetic_personas),
        "survey_questions": sanitize_for_json(survey.survey_questions),
        "synthetic_responses": sanitize_for_json(survey.synthetic_responses),
        "real_responses": sanitize_for_json(survey.real_responses),
        "test_suite_report": sanitize_for_json(survey.test_suite_report),
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
    keys = (
        "question_comparisons",
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
        "validation_status": survey.validation_status,
        "synthetic_personas": _slim_questionnaire_blob(survey.synthetic_personas, "_question_data_count"),
        "survey_questions": _slim_questionnaire_blob(survey.survey_questions, "_question_data_count"),
        "test_suite_report": _slim_test_suite_report_for_list(survey.test_suite_report),
    }

    if survey.created_at:
        result["created_at"] = survey.created_at.isoformat()
    if survey.validated_at:
        result["validated_at"] = survey.validated_at.isoformat()
    if survey.updated_at:
        result["updated_at"] = survey.updated_at.isoformat()

    return result

"""JSON Serialization Helpers - Handle NaN and inf values"""
import json
import math
from typing import Any, Dict, List, Union


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
    
    result = {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "total_personas": survey.total_personas,
        "total_questions": survey.total_questions,
        "accuracy_score": sanitize_for_json(survey.accuracy_score),
        "confidence_tier": survey.confidence_tier,
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

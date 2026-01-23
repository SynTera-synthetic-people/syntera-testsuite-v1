"""Survey Routes"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.connection import get_db
from backend.models.survey import Survey
from backend.utils.json_helpers import survey_to_dict, sanitize_for_json

router = APIRouter()


class SurveyCreate(BaseModel):
    title: str
    description: str | None = None
    total_personas: int = 100
    total_questions: int = 10


@router.post("/")
async def create_survey(payload: SurveyCreate, db: Session = Depends(get_db)):
    """Create a survey from JSON body sent by the frontend."""
    try:
        survey = Survey(
            title=payload.title,
            description=payload.description,
            total_personas=payload.total_personas,
            total_questions=payload.total_questions,
        )
        db.add(survey)
        db.commit()
        db.refresh(survey)
        return survey_to_dict(survey)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
async def list_surveys(db: Session = Depends(get_db)):
    surveys = db.query(Survey).all()
    return [survey_to_dict(survey) for survey in surveys]


@router.get("/{survey_id}")
async def get_survey(survey_id: str, db: Session = Depends(get_db)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return survey_to_dict(survey)


@router.delete("/{survey_id}")
async def delete_survey(survey_id: str, db: Session = Depends(get_db)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    db.delete(survey)
    db.commit()
    return {"status": "deleted"}


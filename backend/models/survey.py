"""Survey Models"""
from sqlalchemy import Column, String, Integer, DateTime, JSON, Float, Text
from sqlalchemy.sql import func
from database.base import Base
import uuid

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    total_personas = Column(Integer, default=100)
    total_questions = Column(Integer, default=10)
    accuracy_score = Column(Float, nullable=True)
    confidence_tier = Column(String(10), nullable=True)
    validation_status = Column(String(20), default="NOT_TESTED")
    synthetic_personas = Column(JSON)
    survey_questions = Column(JSON)
    synthetic_responses = Column(JSON)
    real_responses = Column(JSON, nullable=True)
    test_suite_report = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    validated_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ValidationRun(Base):
    __tablename__ = "validation_runs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    survey_id = Column(String, nullable=False, index=True)
    overall_accuracy = Column(Float, nullable=False)
    overall_tier = Column(String(10), nullable=False)
    question_results = Column(JSON, nullable=False)
    comparison_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


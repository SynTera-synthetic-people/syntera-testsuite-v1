"""
Test Lab and related SQLAlchemy models.

Canonical Test Lab layout (tables, relationships, change checklist) lives in:
`docs/TEST_LAB_DATABASE_SCHEMA.md`

ERD relationships (keep stable when evolving code):
- test_lab_surveys (1) --defined_by-- (0..1) test_lab_profiles  (survey_id unique)
- test_lab_surveys (1) --historical_log-- (*) test_lab_validation_runs
- test_lab_surveys (1) --source_attribution-- (*) test_lab_leads

Do not rename __tablename__ values without a coordinated DB migration and doc update.
"""
from sqlalchemy import Column, String, Integer, DateTime, JSON, Float, Text, Boolean
from sqlalchemy.sql import func
from database.base import Base
import uuid

class Survey(Base):
    __tablename__ = "test_lab_surveys"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    total_personas = Column(Integer, default=100)
    total_questions = Column(Integer, default=10)
    accuracy_score = Column(Float, nullable=True)
    avg_similarity = Column(Float, nullable=True)
    actions_data_points = Column(Integer, nullable=True)
    neuroscience_data_points = Column(Integer, nullable=True)
    contextual_layer_data_points = Column(Integer, nullable=True)
    directional_alignment = Column(Float, nullable=True)
    avg_prediction_accuracy = Column(Float, nullable=True)
    avg_relationship_strength = Column(Float, nullable=True)
    checks_passed = Column(Integer, nullable=True)
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
    __tablename__ = "test_lab_validation_runs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    survey_id = Column(String, nullable=False, index=True)
    overall_accuracy = Column(Float, nullable=False)
    overall_tier = Column(String(10), nullable=False)
    question_results = Column(JSON, nullable=False)
    comparison_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TestLabProfile(Base):
    __tablename__ = "test_lab_profiles"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    survey_id = Column(String, nullable=False, index=True, unique=True)
    geography = Column(String(512), nullable=True, index=True)
    industry = Column(String(120), nullable=True, index=True)
    scenario = Column(String(120), nullable=True, index=True)
    human_study = Column(JSON, nullable=True)
    synthetic_study = Column(JSON, nullable=True)
    verdict = Column(JSON, nullable=True)
    extra_data = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TestLabVerdict(Base):
    """
    Dedicated verdict table so verdict content can evolve independently.
    Exactly two business columns:
    - survey_id
    - verdict (JSON)
    """

    __tablename__ = "test_lab_verdict"
    survey_id = Column(String, primary_key=True)
    verdict = Column(JSON, nullable=True)


class MarketResearchExtraction(Base):
    """Full snapshot of a Market Research Reverse Engineering run (objectives, questionnaire, context)."""

    __tablename__ = "market_research_extractions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    geography = Column(String(512), nullable=True)
    industry = Column(String(200), nullable=True)
    scenario = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TestLabLead(Base):
    __tablename__ = "test_lab_leads"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    survey_id = Column(String, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    company_name = Column(String(160), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    consent = Column(Boolean, nullable=False, default=True)
    source = Column(String(80), nullable=False, default="view_detailed_comparison")
    extra_data = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TestLabReport(Base):
    """
    Persisted, render-ready report snapshot per survey.

    Note: Survey.test_suite_report stores the raw engine output; this table is for a stable
    report payload suitable for dashboards/export without recomputing/formatting.
    """

    __tablename__ = "test_lab_reports"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    survey_id = Column(String, nullable=False, index=True, unique=True)
    report = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

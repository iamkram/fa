"""Database models for meta-monitoring system"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.shared.database.connection import Base


class MetaEvaluationRun(Base):
    """Tracks meta-monitoring evaluation runs"""
    __tablename__ = "meta_evaluation_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_type = Column(String(50), nullable=False)  # 'daily', 'on_demand', 'post_improvement'
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(20), nullable=False, default='running')  # 'running', 'completed', 'failed'

    # Metrics
    total_queries_evaluated = Column(Integer)
    fact_accuracy_score = Column(Float)
    guardrail_pass_rate = Column(Float)
    avg_response_time_ms = Column(Integer)
    sla_compliance_rate = Column(Float)

    # Comparisons (stored as JSON)
    vs_previous_day = Column(JSONB)  # % changes
    vs_baseline = Column(JSONB)

    # LangSmith integration
    langsmith_run_id = Column(String(255))
    langsmith_project = Column(String(100))

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_eval_runs_started', 'started_at'),
        Index('idx_eval_runs_type', 'run_type'),
    )


class ImprovementProposal(Base):
    """Stores improvement proposals from Research Agent"""
    __tablename__ = "improvement_proposals"

    proposal_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_type = Column(String(50), nullable=False)  # 'prompt_change', 'code_fix', 'config_change'
    component_affected = Column(String(100), nullable=False)  # 'fact_checker', 'hook_writer', etc.

    # Problem analysis
    root_cause = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # 'critical', 'high', 'medium', 'low'
    affected_queries_count = Column(Integer)

    # Proposed solution
    proposal_title = Column(String(255), nullable=False)
    proposal_description = Column(Text, nullable=False)
    proposed_changes = Column(JSONB, nullable=False)  # Specific prompt/code changes

    # Impact estimation
    estimated_improvement_pct = Column(Float)  # e.g., 15.0 = 15% improvement
    estimated_effort_hours = Column(Float)
    risk_level = Column(String(20))  # 'low', 'medium', 'high'

    # Status tracking
    status = Column(String(30), nullable=False, default='pending_review')
    # 'pending_review', 'approved', 'rejected', 'implemented', 'rolled_back'

    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    review_notes = Column(Text)

    # Implementation tracking
    implemented_at = Column(DateTime)
    rollback_at = Column(DateTime)

    # LangSmith integration
    research_run_id = Column(String(255))  # LangSmith run that generated this
    validation_run_id = Column(String(255))  # Validation test run

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    validation_results = relationship("ValidationResult", back_populates="proposal")
    impact_tracking = relationship("ImprovementImpact", back_populates="proposal")

    __table_args__ = (
        Index('idx_proposals_status', 'status'),
        Index('idx_proposals_severity', 'severity'),
        Index('idx_proposals_created', 'created_at'),
    )


class ValidationResult(Base):
    """Stores validation test results for proposals"""
    __tablename__ = "validation_results"

    validation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey('improvement_proposals.proposal_id'), nullable=False)

    # Test execution
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(20), nullable=False, default='running')  # 'running', 'passed', 'failed'

    # Results
    test_dataset_size = Column(Integer)
    tests_passed = Column(Integer)
    tests_failed = Column(Integer)

    # Metrics comparison (before vs after)
    baseline_metrics = Column(JSONB, nullable=False)
    test_metrics = Column(JSONB, nullable=False)
    improvement_delta = Column(JSONB)  # calculated deltas

    # Regression detection
    regressions_detected = Column(Boolean, default=False)
    regression_details = Column(JSONB)

    # Artifacts
    test_output = Column(Text)
    error_logs = Column(Text)
    langsmith_dataset_id = Column(String(255))
    langsmith_run_ids = Column(JSONB)  # Array of run IDs

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    proposal = relationship("ImprovementProposal", back_populates="validation_results")

    __table_args__ = (
        Index('idx_validation_proposal', 'proposal_id'),
        Index('idx_validation_status', 'status'),
    )


class MonitoringAlert(Base):
    """Stores monitoring alerts for errors and anomalies"""
    __tablename__ = "monitoring_alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(50), nullable=False)
    # 'error_spike', 'quality_degradation', 'sla_violation', 'anomaly'

    severity = Column(String(20), nullable=False)  # 'critical', 'high', 'medium', 'low'

    # Details
    alert_title = Column(String(255), nullable=False)
    alert_description = Column(Text, nullable=False)
    affected_component = Column(String(100))

    # Metrics
    metric_name = Column(String(100))
    current_value = Column(Float)
    baseline_value = Column(Float)
    threshold_value = Column(Float)

    # Context
    affected_queries = Column(JSONB)  # Sample query IDs
    langsmith_trace_urls = Column(JSONB)  # Array of URLs

    # Status
    status = Column(String(30), nullable=False, default='open')
    # 'open', 'investigating', 'resolved', 'false_positive'

    assigned_to = Column(String(100))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)

    # Notifications
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_alerts_status', 'status'),
        Index('idx_alerts_severity', 'severity'),
        Index('idx_alerts_created', 'created_at'),
    )


class ImprovementImpact(Base):
    """Tracks post-deployment impact of improvements"""
    __tablename__ = "improvement_impact"

    impact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey('improvement_proposals.proposal_id'), nullable=False)

    # Time periods
    measurement_start = Column(DateTime, nullable=False)
    measurement_end = Column(DateTime, nullable=False)
    measurement_duration_hours = Column(Integer)

    # Before metrics (baseline period)
    before_metrics = Column(JSONB, nullable=False)

    # After metrics (post-implementation)
    after_metrics = Column(JSONB, nullable=False)

    # Calculated improvements
    actual_improvement_pct = Column(Float)  # Actual vs estimated
    statistical_significance = Column(Float)  # p-value

    # ROI calculation
    time_saved_hours = Column(Float)
    cost_savings_usd = Column(Float)
    implementation_cost_hours = Column(Float)
    roi_ratio = Column(Float)  # benefit / cost

    # Verdict
    success = Column(Boolean)
    success_criteria_met = Column(JSONB)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    proposal = relationship("ImprovementProposal", back_populates="impact_tracking")

    __table_args__ = (
        Index('idx_impact_proposal', 'proposal_id'),
    )

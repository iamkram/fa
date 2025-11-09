"""Pydantic models for meta-monitoring API"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class AlertResponse(BaseModel):
    """Response model for monitoring alert"""
    alert_id: UUID
    alert_type: str
    severity: str
    alert_title: str
    alert_description: str
    affected_component: Optional[str] = None
    metric_name: Optional[str] = None
    current_value: Optional[float] = None
    baseline_value: Optional[float] = None
    threshold_value: Optional[float] = None
    status: str
    email_sent: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluationRunResponse(BaseModel):
    """Response model for evaluation run"""
    run_id: UUID
    run_type: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    total_queries_evaluated: Optional[int] = None
    fact_accuracy_score: Optional[float] = None
    guardrail_pass_rate: Optional[float] = None
    avg_response_time_ms: Optional[int] = None
    sla_compliance_rate: Optional[float] = None
    vs_previous_day: Optional[Dict[str, Any]] = None
    vs_baseline: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ProposalResponse(BaseModel):
    """Response model for improvement proposal"""
    proposal_id: UUID
    proposal_type: str
    component_affected: str
    root_cause: str
    severity: str
    proposal_title: str
    proposal_description: str
    estimated_improvement_pct: Optional[float] = None
    estimated_effort_hours: Optional[float] = None
    risk_level: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SystemHealthResponse(BaseModel):
    """Response model for system health status"""
    overall_status: str = Field(..., description="Overall system health: healthy, degraded, critical")
    active_alerts_count: int
    critical_alerts_count: int
    latest_evaluation: Optional[EvaluationRunResponse] = None
    last_24h_metrics: Optional[Dict[str, Any]] = None


class RunMonitoringRequest(BaseModel):
    """Request to run monitoring cycle"""
    force: bool = Field(default=False, description="Force run even if recently executed")


class RunEvaluationRequest(BaseModel):
    """Request to run evaluation"""
    run_type: str = Field(default="on_demand", description="Type of evaluation: daily, on_demand, post_improvement")


class UpdateAlertStatusRequest(BaseModel):
    """Request to update alert status"""
    status: str = Field(..., description="New status: open, investigating, resolved, false_positive")
    resolution_notes: Optional[str] = None
    assigned_to: Optional[str] = None

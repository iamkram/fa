"""FastAPI routes for meta-monitoring system"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from src.shared.database.connection import get_db
from src.shared.models.meta_monitoring import (
    MonitoringAlert,
    MetaEvaluationRun,
    ImprovementProposal
)
from src.meta_monitoring.api.models import (
    AlertResponse,
    EvaluationRunResponse,
    ProposalResponse,
    SystemHealthResponse,
    RunMonitoringRequest,
    RunEvaluationRequest,
    UpdateAlertStatusRequest
)
from src.meta_monitoring.agents.monitoring_agent import run_monitoring_agent
from src.meta_monitoring.agents.evaluation_agent import run_evaluation_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meta-monitoring", tags=["Meta-Monitoring"])


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(db: Session = Depends(get_db)):
    """Get overall system health status"""
    try:
        # Count active alerts
        active_alerts = db.query(MonitoringAlert).filter(
            MonitoringAlert.status == 'open'
        ).all()

        critical_alerts = [a for a in active_alerts if a.severity == 'critical']

        # Get latest evaluation
        latest_eval = db.query(MetaEvaluationRun).filter(
            MetaEvaluationRun.status == 'completed'
        ).order_by(desc(MetaEvaluationRun.completed_at)).first()

        # Determine overall status
        if len(critical_alerts) > 0:
            overall_status = "critical"
        elif len(active_alerts) > 5:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Get last 24h metrics from latest evaluation
        last_24h_metrics = None
        if latest_eval:
            last_24h_metrics = {
                "fact_accuracy": latest_eval.fact_accuracy_score,
                "guardrail_pass_rate": latest_eval.guardrail_pass_rate,
                "avg_response_time_ms": latest_eval.avg_response_time_ms,
                "sla_compliance_rate": latest_eval.sla_compliance_rate
            }

        return SystemHealthResponse(
            overall_status=overall_status,
            active_alerts_count=len(active_alerts),
            critical_alerts_count=len(critical_alerts),
            latest_evaluation=EvaluationRunResponse.from_orm(latest_eval) if latest_eval else None,
            last_24h_metrics=last_24h_metrics
        )

    except Exception as e:
        logger.error(f"Error getting system health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get monitoring alerts with optional filtering"""
    try:
        query = db.query(MonitoringAlert)

        if status:
            query = query.filter(MonitoringAlert.status == status)

        if severity:
            query = query.filter(MonitoringAlert.severity == severity)

        alerts = query.order_by(desc(MonitoringAlert.created_at)).limit(limit).all()

        return [AlertResponse.from_orm(alert) for alert in alerts]

    except Exception as e:
        logger.error(f"Error getting alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/alerts/{alert_id}/status")
async def update_alert_status(
    alert_id: str,
    request: UpdateAlertStatusRequest,
    db: Session = Depends(get_db)
):
    """Update alert status"""
    try:
        alert = db.query(MonitoringAlert).filter(
            MonitoringAlert.alert_id == alert_id
        ).first()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.status = request.status
        alert.updated_at = datetime.utcnow()

        if request.resolution_notes:
            alert.resolution_notes = request.resolution_notes

        if request.assigned_to:
            alert.assigned_to = request.assigned_to

        if request.status == 'resolved':
            alert.resolved_at = datetime.utcnow()

        db.commit()

        return {"message": "Alert status updated", "alert_id": str(alert_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert status: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluations", response_model=List[EvaluationRunResponse])
async def get_evaluations(
    run_type: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get evaluation run history"""
    try:
        query = db.query(MetaEvaluationRun)

        if run_type:
            query = query.filter(MetaEvaluationRun.run_type == run_type)

        evaluations = query.order_by(desc(MetaEvaluationRun.started_at)).limit(limit).all()

        return [EvaluationRunResponse.from_orm(eval) for eval in evaluations]

    except Exception as e:
        logger.error(f"Error getting evaluations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluations/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Get specific evaluation run"""
    try:
        evaluation = db.query(MetaEvaluationRun).filter(
            MetaEvaluationRun.run_id == run_id
        ).first()

        if not evaluation:
            raise HTTPException(status_code=404, detail="Evaluation run not found")

        return EvaluationRunResponse.from_orm(evaluation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting evaluation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/run")
async def trigger_monitoring(request: RunMonitoringRequest = RunMonitoringRequest()):
    """Manually trigger monitoring cycle"""
    try:
        logger.info("[API] Manually triggering monitoring cycle")
        alerts = await run_monitoring_agent()

        return {
            "message": "Monitoring cycle completed",
            "alerts_created": len(alerts),
            "alerts": alerts
        }

    except Exception as e:
        logger.error(f"Error running monitoring: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluation/run")
async def trigger_evaluation(request: RunEvaluationRequest = RunEvaluationRequest()):
    """Manually trigger evaluation"""
    try:
        logger.info(f"[API] Manually triggering {request.run_type} evaluation")
        results = await run_evaluation_agent(run_type=request.run_type)

        return results

    except Exception as e:
        logger.error(f"Error running evaluation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals", response_model=List[ProposalResponse])
async def get_proposals(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get improvement proposals (Phase 2 feature)"""
    try:
        query = db.query(ImprovementProposal)

        if status:
            query = query.filter(ImprovementProposal.status == status)

        if severity:
            query = query.filter(ImprovementProposal.severity == severity)

        proposals = query.order_by(desc(ImprovementProposal.created_at)).limit(limit).all()

        return [ProposalResponse.from_orm(prop) for prop in proposals]

    except Exception as e:
        logger.error(f"Error getting proposals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/latest")
async def get_latest_metrics(db: Session = Depends(get_db)):
    """Get latest evaluation metrics"""
    try:
        latest_eval = db.query(MetaEvaluationRun).filter(
            MetaEvaluationRun.status == 'completed'
        ).order_by(desc(MetaEvaluationRun.completed_at)).first()

        if not latest_eval:
            return {
                "metrics": {
                    "fact_accuracy": None,
                    "guardrail_pass_rate": None,
                    "avg_response_time_ms": None,
                    "sla_compliance_rate": None
                }
            }

        return {
            "metrics": {
                "fact_accuracy": latest_eval.fact_accuracy_score,
                "guardrail_pass_rate": latest_eval.guardrail_pass_rate,
                "avg_response_time_ms": latest_eval.avg_response_time_ms,
                "sla_compliance_rate": latest_eval.sla_compliance_rate
            }
        }

    except Exception as e:
        logger.error(f"Error getting latest metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/stats")
async def get_alert_stats(db: Session = Depends(get_db)):
    """Get alert statistics"""
    try:
        total_alerts = db.query(MonitoringAlert).count()
        active_alerts = db.query(MonitoringAlert).filter(MonitoringAlert.status == 'open').count()
        critical_alerts = db.query(MonitoringAlert).filter(
            MonitoringAlert.severity == 'critical',
            MonitoringAlert.status == 'open'
        ).count()
        high_alerts = db.query(MonitoringAlert).filter(
            MonitoringAlert.severity == 'high',
            MonitoringAlert.status == 'open'
        ).count()

        # Resolved in last 24 hours
        from datetime import timedelta
        resolved_24h = db.query(MonitoringAlert).filter(
            MonitoringAlert.status == 'resolved',
            MonitoringAlert.updated_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()

        return {
            "total": total_alerts,
            "active_count": active_alerts,
            "critical_count": critical_alerts,
            "high_count": high_alerts,
            "resolved_24h": resolved_24h
        }

    except Exception as e:
        logger.error(f"Error getting alert stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals/stats")
async def get_proposal_stats(db: Session = Depends(get_db)):
    """Get proposal statistics"""
    try:
        total_proposals = db.query(ImprovementProposal).count()
        pending_proposals = db.query(ImprovementProposal).filter(
            ImprovementProposal.status == 'pending_review'
        ).count()
        approved_proposals = db.query(ImprovementProposal).filter(
            ImprovementProposal.status == 'approved'
        ).count()
        implemented_proposals = db.query(ImprovementProposal).filter(
            ImprovementProposal.status == 'implemented'
        ).count()

        return {
            "total": total_proposals,
            "pending": pending_proposals,
            "approved": approved_proposals,
            "implemented": implemented_proposals,
            "rejected": total_proposals - pending_proposals - approved_proposals - implemented_proposals
        }

    except Exception as e:
        logger.error(f"Error getting proposal stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/trend")
async def get_metrics_trend(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Get metrics trend over time"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        evaluations = db.query(MetaEvaluationRun).filter(
            MetaEvaluationRun.status == 'completed',
            MetaEvaluationRun.completed_at >= start_date
        ).order_by(MetaEvaluationRun.completed_at).all()

        trend_data = []
        for eval in evaluations:
            trend_data.append({
                "evaluated_at": eval.completed_at.isoformat(),
                "metrics": {
                    "fact_accuracy": eval.fact_accuracy_score,
                    "guardrail_pass_rate": eval.guardrail_pass_rate,
                    "avg_response_time_ms": eval.avg_response_time_ms,
                    "sla_compliance_rate": eval.sla_compliance_rate,
                    "total_queries": eval.total_queries_evaluated
                }
            })

        return trend_data

    except Exception as e:
        logger.error(f"Error getting metrics trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Research Agent Endpoints (Phase 2)
# ============================================================================

@router.post("/research/analyze-alert/{alert_id}")
async def analyze_alert(alert_id: str, db: Session = Depends(get_db)):
    """Trigger research agent to analyze a specific alert and propose fix"""
    try:
        from src.meta_monitoring.agents.research_agent import run_research_agent

        logger.info(f"[API] Triggering research agent for alert {alert_id}")
        proposal = await run_research_agent(alert_id=alert_id)

        if not proposal:
            return {
                "success": False,
                "message": "No actionable proposal generated for this alert"
            }

        return {
            "success": True,
            "message": "Improvement proposal created",
            "proposal": proposal
        }

    except Exception as e:
        logger.error(f"Error analyzing alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research/batch-analyze")
async def batch_analyze_alerts(max_alerts: int = 5):
    """Trigger research agent to analyze multiple recent alerts"""
    try:
        from src.meta_monitoring.agents.research_agent import run_research_agent

        logger.info(f"[API] Triggering batch analysis of up to {max_alerts} alerts")
        proposals = await run_research_agent(max_alerts=max_alerts)

        return {
            "success": True,
            "message": f"Created {len(proposals)} proposals from {max_alerts} alerts",
            "proposals": proposals
        }

    except Exception as e:
        logger.error(f"Error in batch analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Validation Agent Endpoints (Phase 2)
# ============================================================================

@router.post("/validation/validate-proposal/{proposal_id}")
async def validate_proposal(proposal_id: str, run_tests: bool = True):
    """Trigger validation agent to test an improvement proposal"""
    try:
        from src.meta_monitoring.agents.validation_agent import run_validation_agent

        logger.info(f"[API] Triggering validation for proposal {proposal_id}")
        results = await run_validation_agent(proposal_id, run_tests=run_tests)

        return {
            "success": results.get("status") in ["passed", "skipped"],
            "message": f"Validation {results.get('status')}",
            "results": results
        }

    except Exception as e:
        logger.error(f"Error validating proposal {proposal_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validation/results/{proposal_id}")
async def get_validation_results(proposal_id: str, db: Session = Depends(get_db)):
    """Get validation results for a proposal"""
    try:
        from src.shared.models.meta_monitoring import ValidationResult

        results = db.query(ValidationResult).filter(
            ValidationResult.proposal_id == proposal_id
        ).order_by(desc(ValidationResult.started_at)).all()

        return {
            "success": True,
            "count": len(results),
            "results": [
                {
                    "validation_id": str(r.validation_id),
                    "status": r.status,
                    "started_at": r.started_at.isoformat(),
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "tests_passed": r.tests_passed,
                    "tests_failed": r.tests_failed,
                    "regressions_detected": r.regressions_detected,
                    "improvement_delta": r.improvement_delta
                }
                for r in results
            ]
        }

    except Exception as e:
        logger.error(f"Error getting validation results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Proposal Management Endpoints (Phase 2)
# ============================================================================

@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, approved_by: str, db: Session = Depends(get_db)):
    """Approve an improvement proposal"""
    try:
        proposal = db.query(ImprovementProposal).filter(
            ImprovementProposal.proposal_id == proposal_id
        ).first()

        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        proposal.status = 'approved'
        proposal.reviewed_by = approved_by
        proposal.reviewed_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "message": "Proposal approved",
            "proposal_id": proposal_id,
            "status": "approved"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving proposal: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    rejected_by: str,
    reason: str,
    db: Session = Depends(get_db)
):
    """Reject an improvement proposal"""
    try:
        proposal = db.query(ImprovementProposal).filter(
            ImprovementProposal.proposal_id == proposal_id
        ).first()

        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        proposal.status = 'rejected'
        proposal.reviewed_by = rejected_by
        proposal.reviewed_at = datetime.utcnow()
        proposal.review_notes = reason

        db.commit()

        return {
            "success": True,
            "message": "Proposal rejected",
            "proposal_id": proposal_id,
            "status": "rejected"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting proposal: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

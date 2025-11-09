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
                "date": eval.completed_at.isoformat(),
                "fact_accuracy": eval.fact_accuracy_score,
                "guardrail_pass_rate": eval.guardrail_pass_rate,
                "avg_response_time_ms": eval.avg_response_time_ms,
                "sla_compliance_rate": eval.sla_compliance_rate
            })

        return {
            "period_days": days,
            "data_points": len(trend_data),
            "trend": trend_data
        }

    except Exception as e:
        logger.error(f"Error getting metrics trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

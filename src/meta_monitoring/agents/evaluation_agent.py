"""Evaluation Agent - Runs comprehensive daily quality evaluations"""

from langchain_anthropic import ChatAnthropic
from langsmith import Client
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
import logging
import asyncio
from statistics import mean
import uuid

from src.config.settings import settings
from src.shared.database.connection import get_db
from src.shared.models.meta_monitoring import MetaEvaluationRun

logger = logging.getLogger(__name__)


class EvaluationAgent:
    """Agent for running comprehensive daily quality evaluations"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.0,
            max_tokens=4000,
            anthropic_api_key=settings.anthropic_api_key
        )
        # LangSmith client for querying traces and datasets
        self.langsmith_client = Client(api_key=settings.langsmith_api_key)
        self.main_project = "fa-ai-dev"  # Main system project
        self.meta_project = "fa-ai-meta-monitoring"  # Meta-monitoring project

    async def run_daily_evaluation(self, run_type: str = "daily") -> Dict[str, Any]:
        """Run comprehensive evaluation of system quality

        Args:
            run_type: Type of evaluation run ('daily', 'on_demand', 'post_improvement')

        Returns:
            Evaluation results dictionary
        """
        logger.info(f"[EvaluationAgent] Starting {run_type} evaluation")

        db = next(get_db())
        run_id = uuid.uuid4()

        try:
            # Create evaluation run record
            eval_run = MetaEvaluationRun(
                run_id=run_id,
                run_type=run_type,
                started_at=datetime.utcnow(),
                status='running',
                langsmith_project=self.meta_project
            )
            db.add(eval_run)
            db.commit()

            # 1. Fetch runs from last 24 hours
            recent_runs = await self._fetch_last_24h_runs()

            if not recent_runs:
                logger.warning("[EvaluationAgent] No runs found in last 24 hours")
                eval_run.status = 'completed'
                eval_run.completed_at = datetime.utcnow()
                eval_run.total_queries_evaluated = 0
                db.commit()
                return {"status": "completed", "total_queries": 0}

            # 2. Calculate metrics
            metrics = await self._calculate_evaluation_metrics(recent_runs)

            # 3. Compare with previous day
            previous_metrics = await self._get_previous_day_metrics(db)
            vs_previous_day = self._calculate_deltas(metrics, previous_metrics) if previous_metrics else None

            # 4. Compare with baseline
            baseline_metrics = await self._get_baseline_metrics(db)
            vs_baseline = self._calculate_deltas(metrics, baseline_metrics) if baseline_metrics else None

            # 5. Update evaluation run record
            eval_run.completed_at = datetime.utcnow()
            eval_run.status = 'completed'
            eval_run.total_queries_evaluated = metrics['total_queries']
            eval_run.fact_accuracy_score = metrics.get('fact_accuracy')
            eval_run.guardrail_pass_rate = metrics.get('guardrail_pass_rate')
            eval_run.avg_response_time_ms = metrics.get('avg_response_time_ms')
            eval_run.sla_compliance_rate = metrics.get('sla_compliance_rate')
            eval_run.vs_previous_day = vs_previous_day
            eval_run.vs_baseline = vs_baseline

            db.commit()

            logger.info(f"[EvaluationAgent] Evaluation complete - {metrics['total_queries']} queries evaluated")

            return {
                "run_id": str(run_id),
                "status": "completed",
                "metrics": metrics,
                "vs_previous_day": vs_previous_day,
                "vs_baseline": vs_baseline
            }

        except Exception as e:
            logger.error(f"[EvaluationAgent] Error in evaluation: {e}", exc_info=True)
            eval_run.status = 'failed'
            eval_run.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": str(e)}

        finally:
            db.close()

    async def _fetch_last_24h_runs(self) -> List[Dict[str, Any]]:
        """Fetch all runs from last 24 hours"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)

            runs = list(self.langsmith_client.list_runs(
                project_name=self.main_project,
                start_time=start_time,
                end_time=end_time,
                is_root=True
            ))

            logger.info(f"[EvaluationAgent] Fetched {len(runs)} runs from last 24 hours")

            # Convert to dict format
            run_data = []
            for run in runs:
                run_data.append({
                    "run_id": str(run.id),
                    "name": run.name,
                    "status": run.status,
                    "start_time": run.start_time,
                    "end_time": run.end_time,
                    "latency_ms": run.latency_ms if hasattr(run, 'latency_ms') else None,
                    "error": run.error if hasattr(run, 'error') else None,
                    "inputs": run.inputs,
                    "outputs": run.outputs,
                    "feedback_stats": run.feedback_stats if hasattr(run, 'feedback_stats') else {},
                })

            return run_data

        except Exception as e:
            logger.error(f"[EvaluationAgent] Error fetching runs: {e}", exc_info=True)
            return []

    async def _calculate_evaluation_metrics(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive evaluation metrics"""

        total_queries = len(runs)
        successful_runs = [r for r in runs if r.get('status') == 'success']
        error_runs = [r for r in runs if r.get('status') == 'error' or r.get('error')]

        # Response time metrics
        latencies = [r.get('latency_ms', 0) for r in successful_runs if r.get('latency_ms')]
        avg_response_time_ms = int(mean(latencies)) if latencies else 0

        # SLA compliance (< 3 seconds = 3000ms)
        sla_threshold_ms = 3000
        sla_compliant = [l for l in latencies if l < sla_threshold_ms]
        sla_compliance_rate = len(sla_compliant) / len(latencies) if latencies else 0

        # Extract fact accuracy from feedback (if available)
        fact_accuracy_scores = []
        guardrail_passes = []

        for run in runs:
            feedback = run.get('feedback_stats', {})
            if 'fact_accuracy' in feedback:
                fact_accuracy_scores.append(feedback['fact_accuracy'])
            if 'guardrail_pass' in feedback:
                guardrail_passes.append(1 if feedback['guardrail_pass'] else 0)

        fact_accuracy = mean(fact_accuracy_scores) if fact_accuracy_scores else None
        guardrail_pass_rate = mean(guardrail_passes) if guardrail_passes else None

        # Calculate error rate
        error_rate = len(error_runs) / total_queries if total_queries > 0 else 0

        return {
            "total_queries": total_queries,
            "successful_queries": len(successful_runs),
            "failed_queries": len(error_runs),
            "error_rate": error_rate,
            "avg_response_time_ms": avg_response_time_ms,
            "sla_compliance_rate": sla_compliance_rate,
            "fact_accuracy": fact_accuracy,
            "guardrail_pass_rate": guardrail_pass_rate,
            "evaluation_timestamp": datetime.utcnow().isoformat()
        }

    async def _get_previous_day_metrics(self, db: Session) -> Optional[Dict[str, Any]]:
        """Get metrics from previous day's evaluation"""
        try:
            # Find most recent completed evaluation run (excluding today)
            yesterday = datetime.utcnow() - timedelta(days=1)

            previous_run = db.query(MetaEvaluationRun).filter(
                MetaEvaluationRun.status == 'completed',
                MetaEvaluationRun.run_type == 'daily',
                MetaEvaluationRun.completed_at < yesterday
            ).order_by(desc(MetaEvaluationRun.completed_at)).first()

            if not previous_run:
                return None

            return {
                "total_queries": previous_run.total_queries_evaluated,
                "fact_accuracy": previous_run.fact_accuracy_score,
                "guardrail_pass_rate": previous_run.guardrail_pass_rate,
                "avg_response_time_ms": previous_run.avg_response_time_ms,
                "sla_compliance_rate": previous_run.sla_compliance_rate
            }

        except Exception as e:
            logger.error(f"[EvaluationAgent] Error fetching previous metrics: {e}", exc_info=True)
            return None

    async def _get_baseline_metrics(self, db: Session) -> Optional[Dict[str, Any]]:
        """Get baseline metrics"""
        try:
            baseline_run = db.query(MetaEvaluationRun).filter(
                MetaEvaluationRun.run_type == 'baseline',
                MetaEvaluationRun.status == 'completed'
            ).first()

            if not baseline_run:
                # Use hardcoded baseline if not in database
                return {
                    "total_queries": 100,
                    "fact_accuracy": 0.93,
                    "guardrail_pass_rate": 0.98,
                    "avg_response_time_ms": 2000,
                    "sla_compliance_rate": 0.95
                }

            return {
                "total_queries": baseline_run.total_queries_evaluated,
                "fact_accuracy": baseline_run.fact_accuracy_score,
                "guardrail_pass_rate": baseline_run.guardrail_pass_rate,
                "avg_response_time_ms": baseline_run.avg_response_time_ms,
                "sla_compliance_rate": baseline_run.sla_compliance_rate
            }

        except Exception as e:
            logger.error(f"[EvaluationAgent] Error fetching baseline: {e}", exc_info=True)
            return None

    def _calculate_deltas(
        self,
        current: Dict[str, Any],
        comparison: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate percentage deltas between current and comparison metrics"""

        deltas = {}

        metrics_to_compare = [
            'fact_accuracy',
            'guardrail_pass_rate',
            'avg_response_time_ms',
            'sla_compliance_rate'
        ]

        for metric in metrics_to_compare:
            current_val = current.get(metric)
            comparison_val = comparison.get(metric)

            if current_val is not None and comparison_val is not None and comparison_val != 0:
                # For response time, negative delta is good (lower is better)
                # For others, positive delta is good (higher is better)
                delta_pct = ((current_val - comparison_val) / comparison_val) * 100

                deltas[metric] = {
                    "current": current_val,
                    "comparison": comparison_val,
                    "delta_pct": round(delta_pct, 2),
                    "direction": "improved" if (
                        (metric == 'avg_response_time_ms' and delta_pct < 0) or
                        (metric != 'avg_response_time_ms' and delta_pct > 0)
                    ) else "degraded"
                }

        return deltas


# Main entry point
async def run_evaluation_agent(run_type: str = "daily"):
    """Run the evaluation agent"""
    agent = EvaluationAgent()
    results = await agent.run_daily_evaluation(run_type=run_type)
    return results


if __name__ == "__main__":
    # For testing
    import asyncio
    asyncio.run(run_evaluation_agent())

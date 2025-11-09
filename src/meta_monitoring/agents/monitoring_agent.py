"""Monitoring Agent - Continuously monitors system for errors and anomalies"""

from langchain_anthropic import ChatAnthropic
from langsmith import Client
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging
import asyncio
from statistics import mean, stdev

from src.config.settings import settings
from src.shared.database.connection import get_db
from src.shared.models.meta_monitoring import MonitoringAlert, MetaEvaluationRun

logger = logging.getLogger(__name__)


class MonitoringAgent:
    """Agent for continuous monitoring of system health and error detection"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.0,
            max_tokens=4000,
            anthropic_api_key=settings.anthropic_api_key
        )
        # LangSmith client for querying traces
        self.langsmith_client = Client(api_key=settings.langsmith_api_key)
        self.main_project = "fa-ai-dev"  # Main system project
        self.meta_project = "fa-ai-meta-monitoring"  # Meta-monitoring project

        # Baseline thresholds (from database or defaults)
        self.baseline_error_rate = 0.02  # 2% error rate
        self.baseline_response_time_ms = 2000  # 2 seconds
        self.baseline_fact_accuracy = 0.93  # 93% accuracy
        self.baseline_guardrail_pass_rate = 0.98  # 98% pass rate

        # Alert thresholds (percentage increase that triggers alert)
        self.thresholds = {
            "critical": 0.50,  # 50% degradation
            "high": 0.25,      # 25% degradation
            "medium": 0.15,    # 15% degradation
            "low": 0.10        # 10% degradation
        }

    async def run_monitoring_cycle(self) -> List[Dict[str, Any]]:
        """Run one monitoring cycle - analyze recent system activity

        Returns:
            List of detected alerts
        """
        logger.info("[MonitoringAgent] Starting monitoring cycle")

        try:
            # 1. Fetch recent runs from LangSmith (last 5 minutes)
            recent_runs = await self._fetch_recent_runs(minutes=5)

            if not recent_runs:
                logger.info("[MonitoringAgent] No recent runs found")
                return []

            # 2. Calculate current metrics
            current_metrics = self._calculate_metrics(recent_runs)

            # 3. Compare against baseline
            anomalies = self._detect_anomalies(current_metrics)

            # 4. Analyze patterns with LLM if anomalies detected
            alerts = []
            if anomalies:
                logger.info(f"[MonitoringAgent] Detected {len(anomalies)} anomalies")
                alerts = await self._analyze_anomalies(anomalies, recent_runs)

            # 5. Store alerts in database
            if alerts:
                await self._store_alerts(alerts)

            logger.info(f"[MonitoringAgent] Monitoring cycle complete - {len(alerts)} alerts created")
            return alerts

        except Exception as e:
            logger.error(f"[MonitoringAgent] Error in monitoring cycle: {e}", exc_info=True)
            return []

    async def _fetch_recent_runs(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """Fetch recent runs from LangSmith main project"""
        try:
            # Calculate time window
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=minutes)

            # Query LangSmith for runs in time window
            runs = list(self.langsmith_client.list_runs(
                project_name=self.main_project,
                start_time=start_time,
                end_time=end_time,
                is_root=True  # Only root runs
            ))

            logger.info(f"[MonitoringAgent] Fetched {len(runs)} runs from {start_time} to {end_time}")

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
                    "trace_url": f"https://smith.langchain.com/o/{settings.langsmith_org_id}/projects/p/{run.project_id}/r/{run.id}"
                })

            return run_data

        except Exception as e:
            logger.error(f"[MonitoringAgent] Error fetching runs from LangSmith: {e}", exc_info=True)
            return []

    def _calculate_metrics(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate metrics from recent runs"""
        if not runs:
            return {}

        total_runs = len(runs)
        error_runs = [r for r in runs if r.get('status') == 'error' or r.get('error')]
        successful_runs = [r for r in runs if r.get('status') == 'success']

        # Calculate error rate
        error_rate = len(error_runs) / total_runs if total_runs > 0 else 0

        # Calculate average response time (for successful runs)
        latencies = [r.get('latency_ms', 0) for r in successful_runs if r.get('latency_ms')]
        avg_latency_ms = mean(latencies) if latencies else 0

        # Calculate response time percentiles
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

        # Extract feedback stats (if available)
        fact_accuracy_scores = []
        guardrail_pass_rates = []

        for run in runs:
            feedback = run.get('feedback_stats', {})
            if 'fact_accuracy' in feedback:
                fact_accuracy_scores.append(feedback['fact_accuracy'])
            if 'guardrail_pass' in feedback:
                guardrail_pass_rates.append(1 if feedback['guardrail_pass'] else 0)

        fact_accuracy = mean(fact_accuracy_scores) if fact_accuracy_scores else None
        guardrail_pass_rate = mean(guardrail_pass_rates) if guardrail_pass_rates else None

        return {
            "total_runs": total_runs,
            "error_rate": error_rate,
            "error_count": len(error_runs),
            "avg_latency_ms": avg_latency_ms,
            "p95_latency_ms": p95_latency,
            "fact_accuracy": fact_accuracy,
            "guardrail_pass_rate": guardrail_pass_rate,
            "sample_errors": [r.get('error', '')[:200] for r in error_runs[:5]],  # First 5 errors
            "timestamp": datetime.utcnow()
        }

    def _detect_anomalies(self, current_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies by comparing current metrics to baseline"""
        anomalies = []

        # Check error rate
        if current_metrics.get('error_rate', 0) > 0:
            error_increase = (current_metrics['error_rate'] - self.baseline_error_rate) / max(self.baseline_error_rate, 0.01)
            if error_increase > self.thresholds['low']:
                severity = self._determine_severity(error_increase)
                anomalies.append({
                    "type": "error_spike",
                    "metric_name": "error_rate",
                    "current_value": current_metrics['error_rate'],
                    "baseline_value": self.baseline_error_rate,
                    "percent_change": error_increase * 100,
                    "severity": severity,
                    "details": f"Error rate increased by {error_increase*100:.1f}%"
                })

        # Check response time
        if current_metrics.get('avg_latency_ms', 0) > 0:
            latency_increase = (current_metrics['avg_latency_ms'] - self.baseline_response_time_ms) / self.baseline_response_time_ms
            if latency_increase > self.thresholds['low']:
                severity = self._determine_severity(latency_increase)
                anomalies.append({
                    "type": "sla_violation",
                    "metric_name": "avg_latency_ms",
                    "current_value": current_metrics['avg_latency_ms'],
                    "baseline_value": self.baseline_response_time_ms,
                    "percent_change": latency_increase * 100,
                    "severity": severity,
                    "details": f"Response time increased by {latency_increase*100:.1f}%"
                })

        # Check fact accuracy (if available)
        if current_metrics.get('fact_accuracy') is not None:
            accuracy_decrease = (self.baseline_fact_accuracy - current_metrics['fact_accuracy']) / self.baseline_fact_accuracy
            if accuracy_decrease > self.thresholds['low']:
                severity = self._determine_severity(accuracy_decrease)
                anomalies.append({
                    "type": "quality_degradation",
                    "metric_name": "fact_accuracy",
                    "current_value": current_metrics['fact_accuracy'],
                    "baseline_value": self.baseline_fact_accuracy,
                    "percent_change": -accuracy_decrease * 100,
                    "severity": severity,
                    "details": f"Fact accuracy decreased by {accuracy_decrease*100:.1f}%"
                })

        # Check guardrail pass rate (if available)
        if current_metrics.get('guardrail_pass_rate') is not None:
            guardrail_decrease = (self.baseline_guardrail_pass_rate - current_metrics['guardrail_pass_rate']) / self.baseline_guardrail_pass_rate
            if guardrail_decrease > self.thresholds['low']:
                severity = self._determine_severity(guardrail_decrease)
                anomalies.append({
                    "type": "quality_degradation",
                    "metric_name": "guardrail_pass_rate",
                    "current_value": current_metrics['guardrail_pass_rate'],
                    "baseline_value": self.baseline_guardrail_pass_rate,
                    "percent_change": -guardrail_decrease * 100,
                    "severity": severity,
                    "details": f"Guardrail pass rate decreased by {guardrail_decrease*100:.1f}%"
                })

        return anomalies

    def _determine_severity(self, percent_change: float) -> str:
        """Determine severity level based on percent change"""
        abs_change = abs(percent_change)
        if abs_change >= self.thresholds['critical']:
            return 'critical'
        elif abs_change >= self.thresholds['high']:
            return 'high'
        elif abs_change >= self.thresholds['medium']:
            return 'medium'
        else:
            return 'low'

    async def _analyze_anomalies(
        self,
        anomalies: List[Dict[str, Any]],
        recent_runs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use LLM to analyze anomalies and create detailed alerts"""

        # Prepare context for LLM
        anomaly_summary = "\n".join([
            f"- {a['type']}: {a['metric_name']} changed by {a['percent_change']:.1f}% "
            f"(current: {a['current_value']:.4f}, baseline: {a['baseline_value']:.4f})"
            for a in anomalies
        ])

        # Get sample errors
        error_runs = [r for r in recent_runs if r.get('error')]
        error_sample = "\n".join([
            f"- {r.get('name', 'Unknown')}: {r.get('error', '')[:200]}"
            for r in error_runs[:5]
        ])

        prompt = f"""You are a monitoring agent analyzing system health metrics.

DETECTED ANOMALIES:
{anomaly_summary}

SAMPLE ERRORS ({len(error_runs)} total):
{error_sample if error_sample else "No errors"}

TASK:
For each anomaly, provide:
1. Alert title (concise, actionable)
2. Alert description (what's happening and potential impact)
3. Affected component (guess based on error messages)
4. Recommended action

Output JSON array of alerts with this structure:
[
  {{
    "alert_title": "string",
    "alert_description": "string",
    "affected_component": "string",
    "recommended_action": "string",
    "alert_type": "error_spike|quality_degradation|sla_violation|anomaly",
    "severity": "critical|high|medium|low"
  }}
]
"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()

            # Parse JSON, handling markdown code blocks
            if content.startswith('```'):
                start = content.find('\n')
                end = content.rfind('```')
                if start != -1 and end != -1:
                    content = content[start+1:end].strip()

            import json
            alerts = json.loads(content)

            # Merge with anomaly data
            for i, alert in enumerate(alerts):
                if i < len(anomalies):
                    alert.update({
                        "metric_name": anomalies[i]['metric_name'],
                        "current_value": anomalies[i]['current_value'],
                        "baseline_value": anomalies[i]['baseline_value'],
                        "threshold_value": anomalies[i]['baseline_value'] * (1 + self.thresholds[anomalies[i]['severity']])
                    })

            return alerts

        except Exception as e:
            logger.error(f"[MonitoringAgent] Error analyzing anomalies with LLM: {e}", exc_info=True)
            # Fallback: create basic alerts
            return [{
                "alert_title": f"{a['type'].replace('_', ' ').title()} Detected",
                "alert_description": a['details'],
                "affected_component": "Unknown",
                "recommended_action": "Investigate recent changes",
                "alert_type": a['type'],
                "severity": a['severity'],
                "metric_name": a['metric_name'],
                "current_value": a['current_value'],
                "baseline_value": a['baseline_value'],
                "threshold_value": a['baseline_value'] * (1 + self.thresholds[a['severity']])
            } for a in anomalies]

    async def _store_alerts(self, alerts: List[Dict[str, Any]]):
        """Store alerts in database"""
        try:
            db = next(get_db())

            for alert_data in alerts:
                alert = MonitoringAlert(
                    alert_type=alert_data['alert_type'],
                    severity=alert_data['severity'],
                    alert_title=alert_data['alert_title'],
                    alert_description=alert_data['alert_description'],
                    affected_component=alert_data.get('affected_component'),
                    metric_name=alert_data.get('metric_name'),
                    current_value=alert_data.get('current_value'),
                    baseline_value=alert_data.get('baseline_value'),
                    threshold_value=alert_data.get('threshold_value'),
                    status='open',
                    email_sent=False
                )

                db.add(alert)

            db.commit()
            logger.info(f"[MonitoringAgent] Stored {len(alerts)} alerts in database")

        except Exception as e:
            logger.error(f"[MonitoringAgent] Error storing alerts: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


# Main entry point for running the monitoring agent
async def run_monitoring_agent():
    """Run the monitoring agent once"""
    agent = MonitoringAgent()
    alerts = await agent.run_monitoring_cycle()
    return alerts


if __name__ == "__main__":
    # For testing
    import asyncio
    asyncio.run(run_monitoring_agent())

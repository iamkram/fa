"""Research Agent - Analyzes errors and proposes improvements"""

from langchain_anthropic import ChatAnthropic
from langsmith import Client
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging
import json
import uuid

from src.config.settings import settings
from src.shared.database.connection import get_db
from src.shared.models.meta_monitoring import (
    MonitoringAlert,
    ImprovementProposal,
    MetaEvaluationRun
)

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Agent for root cause analysis and improvement proposal generation"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.3,  # Some creativity for problem-solving
            max_tokens=8000,
            anthropic_api_key=settings.anthropic_api_key
        )
        # LangSmith client for analyzing traces
        self.langsmith_client = Client(api_key=settings.langsmith_api_key)
        self.main_project = "fa-ai-dev"
        self.meta_project = "fa-ai-meta-monitoring"

    async def analyze_alert_and_propose_fix(
        self,
        alert: MonitoringAlert,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """Analyze an alert and generate improvement proposal

        Args:
            alert: MonitoringAlert to analyze
            db: Database session

        Returns:
            Improvement proposal dict or None if no actionable fix found
        """
        logger.info(f"[ResearchAgent] Analyzing alert {alert.alert_id}: {alert.alert_title}")

        try:
            # 1. Gather context about the alert
            context = await self._gather_alert_context(alert)

            # 2. Fetch related LangSmith traces
            trace_details = await self._fetch_trace_details(alert)

            # 3. Perform root cause analysis
            root_cause_analysis = await self._perform_root_cause_analysis(
                alert, context, trace_details
            )

            if not root_cause_analysis:
                logger.warning(f"[ResearchAgent] No root cause found for alert {alert.alert_id}")
                return None

            # 4. Generate improvement proposal
            proposal = await self._generate_improvement_proposal(
                alert, root_cause_analysis, trace_details
            )

            if not proposal:
                logger.warning(f"[ResearchAgent] No proposal generated for alert {alert.alert_id}")
                return None

            # 5. Store proposal in database
            proposal_record = self._store_proposal(proposal, db)

            logger.info(
                f"[ResearchAgent] Created proposal {proposal_record.proposal_id}: "
                f"{proposal_record.proposal_title} "
                f"(est. {proposal_record.estimated_improvement_pct}% improvement, "
                f"{proposal_record.estimated_effort_hours}h effort)"
            )

            return {
                "proposal_id": str(proposal_record.proposal_id),
                "title": proposal_record.proposal_title,
                "estimated_improvement_pct": proposal_record.estimated_improvement_pct,
                "estimated_effort_hours": proposal_record.estimated_effort_hours,
                "status": proposal_record.status
            }

        except Exception as e:
            logger.error(f"[ResearchAgent] Error analyzing alert {alert.alert_id}: {e}", exc_info=True)
            return None

    async def _gather_alert_context(self, alert: MonitoringAlert) -> Dict[str, Any]:
        """Gather contextual information about the alert"""
        db = next(get_db())

        try:
            # Get similar alerts
            similar_alerts = db.query(MonitoringAlert).filter(
                MonitoringAlert.alert_type == alert.alert_type,
                MonitoringAlert.created_at >= datetime.utcnow() - timedelta(days=7)
            ).order_by(MonitoringAlert.created_at.desc()).limit(10).all()

            # Get recent evaluation metrics
            recent_eval = db.query(MetaEvaluationRun).filter(
                MetaEvaluationRun.status == 'completed'
            ).order_by(MetaEvaluationRun.completed_at.desc()).first()

            return {
                "similar_alerts_count": len(similar_alerts),
                "similar_alerts_sample": [
                    {
                        "title": a.alert_title,
                        "severity": a.severity,
                        "created_at": a.created_at.isoformat()
                    }
                    for a in similar_alerts[:3]
                ],
                "recent_metrics": {
                    "fact_accuracy": recent_eval.fact_accuracy_score if recent_eval else None,
                    "guardrail_pass_rate": recent_eval.guardrail_pass_rate if recent_eval else None,
                    "avg_response_time_ms": recent_eval.avg_response_time_ms if recent_eval else None
                } if recent_eval else {}
            }
        finally:
            db.close()

    async def _fetch_trace_details(self, alert: MonitoringAlert) -> List[Dict[str, Any]]:
        """Fetch detailed trace information from LangSmith"""
        try:
            if not alert.langsmith_trace_urls:
                return []

            trace_details = []

            # Parse trace URLs to get run IDs
            # URLs are in format: https://smith.langchain.com/o/{org}/projects/p/{project}/r/{run_id}
            for url in (alert.langsmith_trace_urls if isinstance(alert.langsmith_trace_urls, list) else []):
                try:
                    run_id = url.split('/r/')[-1]
                    run = self.langsmith_client.read_run(run_id)

                    trace_details.append({
                        "run_id": str(run.id),
                        "name": run.name,
                        "status": run.status,
                        "error": run.error if hasattr(run, 'error') else None,
                        "inputs": run.inputs,
                        "outputs": run.outputs,
                        "latency_ms": run.latency_ms if hasattr(run, 'latency_ms') else None,
                        "url": url
                    })
                except Exception as e:
                    logger.warning(f"Failed to fetch trace {url}: {e}")

            return trace_details[:5]  # Limit to 5 traces

        except Exception as e:
            logger.error(f"Error fetching trace details: {e}", exc_info=True)
            return []

    async def _perform_root_cause_analysis(
        self,
        alert: MonitoringAlert,
        context: Dict[str, Any],
        trace_details: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to perform root cause analysis"""

        # Build comprehensive context for analysis
        trace_summary = "\n".join([
            f"- Run {i+1}: {t['name']} - Status: {t['status']}"
            f"{' - Error: ' + t['error'] if t.get('error') else ''}"
            f" - Latency: {t.get('latency_ms', 'N/A')}ms"
            for i, t in enumerate(trace_details)
        ])

        prompt = f"""You are an AI system reliability engineer analyzing production issues.

ALERT DETAILS:
- Type: {alert.alert_type}
- Severity: {alert.severity}
- Title: {alert.alert_title}
- Description: {alert.alert_description}
- Component: {alert.affected_component or 'Unknown'}
- Metric: {alert.metric_name or 'N/A'}
- Current Value: {alert.current_value or 'N/A'}
- Baseline Value: {alert.baseline_value or 'N/A'}

CONTEXT:
- Similar alerts in last 7 days: {context.get('similar_alerts_count', 0)}
- Recent system metrics: {json.dumps(context.get('recent_metrics', {}), indent=2)}

LANGSMITH TRACES:
{trace_summary if trace_summary else "No trace data available"}

TASK:
Perform a detailed root cause analysis. Identify:
1. The underlying technical cause (be specific - prompt issue, code bug, data quality, etc.)
2. Why this is happening (system design flaw, edge case, degradation over time, etc.)
3. What component is responsible (fact_checker, hook_writer, guardrails, etc.)
4. How widespread the impact is (% of queries affected)

Output JSON:
{{
  "root_cause": "Specific technical explanation of what's causing the issue",
  "component_responsible": "exact component name (e.g., fact_checker, input_guardrails)",
  "category": "prompt_issue|code_bug|data_quality|configuration|infrastructure",
  "confidence_score": 0.0-1.0,
  "affected_queries_estimate_pct": 5.0,
  "is_actionable": true|false,
  "reasoning": "Brief explanation of your analysis"
}}

Be precise and actionable. If the issue is not clear or not actionable, set is_actionable to false.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()

            # Parse JSON response
            if content.startswith('```'):
                start = content.find('\n')
                end = content.rfind('```')
                if start != -1 and end != -1:
                    content = content[start+1:end].strip()

            analysis = json.loads(content)

            if not analysis.get('is_actionable'):
                logger.info(f"[ResearchAgent] Analysis not actionable: {analysis.get('reasoning')}")
                return None

            return analysis

        except Exception as e:
            logger.error(f"[ResearchAgent] Error in root cause analysis: {e}", exc_info=True)
            return None

    async def _generate_improvement_proposal(
        self,
        alert: MonitoringAlert,
        root_cause: Dict[str, Any],
        trace_details: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Generate specific improvement proposal based on root cause"""

        prompt = f"""You are an AI system improvement specialist. Based on the root cause analysis, propose a specific fix.

ROOT CAUSE ANALYSIS:
- Cause: {root_cause['root_cause']}
- Component: {root_cause['component_responsible']}
- Category: {root_cause['category']}
- Affected Queries: ~{root_cause['affected_queries_estimate_pct']}%

ALERT INFO:
- Type: {alert.alert_type}
- Severity: {alert.severity}
- Metric Impact: {alert.metric_name} = {alert.current_value} (baseline: {alert.baseline_value})

TASK:
Propose a specific, implementable fix. Be concrete and detailed.

For PROMPT ISSUES:
- Provide the exact prompt change (show before/after or specific modifications)
- Explain why this will fix the issue

For CODE BUGS:
- Identify the file and function
- Describe the specific code change needed

For CONFIGURATION:
- Specify exact config parameter and new value

Output JSON:
{{
  "proposal_type": "prompt_change|code_fix|config_change|data_fix",
  "proposal_title": "Clear, concise title (50 chars max)",
  "proposal_description": "Detailed description of the fix",
  "proposed_changes": {{
    "change_type": "specific change type",
    "target_file": "file path or 'LangSmith prompt'",
    "target_component": "component name",
    "specific_change": "Exact change to make (code diff, new prompt text, config value, etc.)",
    "before": "Current state (if applicable)",
    "after": "Proposed state"
  }},
  "estimated_improvement_pct": 15.0,
  "estimated_effort_hours": 2.0,
  "risk_level": "low|medium|high",
  "test_plan": "How to validate this fix works",
  "rollback_plan": "How to safely rollback if it fails"
}}

Be specific and practical. Estimate improvement conservatively.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()

            # Parse JSON response
            if content.startswith('```'):
                start = content.find('\n')
                end = content.rfind('```')
                if start != -1 and end != -1:
                    content = content[start+1:end].strip()

            proposal = json.loads(content)

            # Add root cause to proposal
            proposal['root_cause'] = root_cause['root_cause']
            proposal['severity'] = alert.severity
            proposal['affected_queries_count'] = int(
                root_cause['affected_queries_estimate_pct'] * 100  # Rough estimate
            )

            return proposal

        except Exception as e:
            logger.error(f"[ResearchAgent] Error generating proposal: {e}", exc_info=True)
            return None

    def _store_proposal(
        self,
        proposal: Dict[str, Any],
        db: Session
    ) -> ImprovementProposal:
        """Store improvement proposal in database"""

        proposal_record = ImprovementProposal(
            proposal_id=uuid.uuid4(),
            proposal_type=proposal['proposal_type'],
            component_affected=proposal['proposed_changes']['target_component'],
            root_cause=proposal['root_cause'],
            severity=proposal['severity'],
            affected_queries_count=proposal.get('affected_queries_count', 0),
            proposal_title=proposal['proposal_title'],
            proposal_description=proposal['proposal_description'],
            proposed_changes=proposal['proposed_changes'],
            estimated_improvement_pct=proposal.get('estimated_improvement_pct'),
            estimated_effort_hours=proposal.get('estimated_effort_hours'),
            risk_level=proposal.get('risk_level', 'medium'),
            status='pending_review'
        )

        db.add(proposal_record)
        db.commit()
        db.refresh(proposal_record)

        return proposal_record

    async def batch_analyze_alerts(
        self,
        max_alerts: int = 5
    ) -> List[Dict[str, Any]]:
        """Analyze recent unresolved alerts and generate proposals

        Args:
            max_alerts: Maximum number of alerts to analyze

        Returns:
            List of created proposals
        """
        logger.info(f"[ResearchAgent] Batch analyzing up to {max_alerts} alerts")

        db = next(get_db())
        proposals = []

        try:
            # Get unresolved alerts that don't already have proposals
            # (Check by linking alert ID in future enhancement)
            alerts = db.query(MonitoringAlert).filter(
                MonitoringAlert.status == 'open',
                MonitoringAlert.severity.in_(['critical', 'high'])
            ).order_by(
                MonitoringAlert.severity.desc(),
                MonitoringAlert.created_at.desc()
            ).limit(max_alerts).all()

            for alert in alerts:
                proposal = await self.analyze_alert_and_propose_fix(alert, db)
                if proposal:
                    proposals.append(proposal)

            logger.info(f"[ResearchAgent] Created {len(proposals)} proposals from {len(alerts)} alerts")
            return proposals

        except Exception as e:
            logger.error(f"[ResearchAgent] Error in batch analysis: {e}", exc_info=True)
            return proposals
        finally:
            db.close()


# Main entry point
async def run_research_agent(alert_id: Optional[str] = None, max_alerts: int = 5):
    """Run the research agent

    Args:
        alert_id: Specific alert ID to analyze, or None for batch analysis
        max_alerts: Maximum alerts to analyze in batch mode
    """
    agent = ResearchAgent()

    if alert_id:
        # Analyze specific alert
        db = next(get_db())
        try:
            alert = db.query(MonitoringAlert).filter(
                MonitoringAlert.alert_id == alert_id
            ).first()

            if not alert:
                logger.error(f"Alert {alert_id} not found")
                return None

            return await agent.analyze_alert_and_propose_fix(alert, db)
        finally:
            db.close()
    else:
        # Batch analysis
        return await agent.batch_analyze_alerts(max_alerts=max_alerts)


if __name__ == "__main__":
    # For testing
    import asyncio
    asyncio.run(run_research_agent())

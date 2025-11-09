#!/usr/bin/env python3
"""
Seed Meta-Monitoring Database with Realistic Test Data

Generates realistic meta-monitoring data for testing the dashboard and full workflow:
- Evaluation runs spanning the last 7 days with varying metrics
- Alerts based on threshold violations
- Improvement proposals linked to alerts
- Validation results for proposals
- Mix of statuses (active, resolved, pending, approved, rejected)
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import random
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.shared.database.connection import get_db
from src.shared.models.meta_monitoring import (
    MetaEvaluationRun,
    MonitoringAlert,
    ImprovementProposal,
    ValidationResult
)


def generate_evaluation_runs(db, num_runs=12):
    """Generate evaluation runs spanning the last 7 days"""
    print(f"\n📊 Generating {num_runs} evaluation runs...")

    runs = []
    now = datetime.utcnow()

    for i in range(num_runs):
        # Spread runs over last 7 days
        days_ago = (num_runs - i - 1) * 7 / num_runs
        start_time = now - timedelta(days=days_ago)
        completion_time = start_time + timedelta(minutes=random.randint(5, 15))

        # Generate realistic varying metrics
        # Simulate gradual degradation then improvement
        if i < 4:
            # Good period
            fact_accuracy = random.uniform(0.94, 0.98)
            guardrail_rate = random.uniform(0.95, 0.99)
            response_time = random.randint(800, 1200)
            sla_compliance = random.uniform(0.96, 0.99)
        elif i < 8:
            # Degradation period
            fact_accuracy = random.uniform(0.82, 0.90)
            guardrail_rate = random.uniform(0.88, 0.94)
            response_time = random.randint(1400, 2200)
            sla_compliance = random.uniform(0.85, 0.92)
        else:
            # Recovery period
            fact_accuracy = random.uniform(0.90, 0.96)
            guardrail_rate = random.uniform(0.92, 0.97)
            response_time = random.randint(900, 1400)
            sla_compliance = random.uniform(0.93, 0.97)

        total_queries = random.randint(150, 350)

        # Calculate vs_previous_day if not first run
        vs_prev = None
        if i > 0:
            prev_run = runs[-1]
            vs_prev = {
                "fact_accuracy_change": round((fact_accuracy - prev_run.fact_accuracy_score) * 100, 2),
                "guardrail_change": round((guardrail_rate - prev_run.guardrail_pass_rate) * 100, 2),
                "response_time_change": round((response_time - prev_run.avg_response_time_ms) / prev_run.avg_response_time_ms * 100, 2)
            }

        run = MetaEvaluationRun(
            run_id=uuid.uuid4(),
            run_type='daily' if i % 3 != 0 else 'on_demand',
            started_at=start_time,
            completed_at=completion_time,
            status='completed',
            total_queries_evaluated=total_queries,
            fact_accuracy_score=round(fact_accuracy, 4),
            guardrail_pass_rate=round(guardrail_rate, 4),
            avg_response_time_ms=response_time,
            sla_compliance_rate=round(sla_compliance, 4),
            vs_previous_day=vs_prev,
            vs_baseline={
                "fact_accuracy_vs_baseline": round((fact_accuracy - 0.95) * 100, 2),
                "guardrail_vs_baseline": round((guardrail_rate - 0.95) * 100, 2)
            },
            langsmith_project="fa-ai-meta-monitoring",
            created_at=start_time
        )

        db.add(run)
        runs.append(run)

    db.commit()
    print(f"✓ Created {len(runs)} evaluation runs")
    return runs


def generate_alerts(db, eval_runs):
    """Generate alerts based on low metrics"""
    print(f"\n🚨 Generating alerts...")

    alerts = []

    # Find runs with degraded metrics
    for run in eval_runs:
        # Alert if fact accuracy < 0.90
        if run.fact_accuracy_score and run.fact_accuracy_score < 0.90:
            severity = "critical" if run.fact_accuracy_score < 0.85 else "high"
            status = random.choice(["open", "open", "investigating"])

            alert = MonitoringAlert(
                alert_id=uuid.uuid4(),
                alert_type="quality_degradation",
                severity=severity,
                alert_title=f"Fact Accuracy Dropped to {run.fact_accuracy_score*100:.1f}%",
                alert_description=f"Fact accuracy has fallen below acceptable threshold. Current value: {run.fact_accuracy_score*100:.1f}%, expected: >90%",
                affected_component="fact_checker",
                metric_name="fact_accuracy_score",
                current_value=run.fact_accuracy_score,
                baseline_value=0.95,
                threshold_value=0.90,
                affected_queries={"sample_query_ids": [str(uuid.uuid4()) for _ in range(5)]},
                langsmith_trace_urls=["https://smith.langchain.com/o/sample/trace/" + str(uuid.uuid4())[:8]],
                status=status,
                created_at=run.completed_at,
                updated_at=run.completed_at
            )

            # Some alerts get resolved
            if status == "investigating":
                alert.status = "resolved"
                alert.resolved_at = run.completed_at + timedelta(hours=2)
                alert.resolution_notes = "Metrics improved after prompt adjustment"

            db.add(alert)
            alerts.append(alert)

        # Alert if guardrail rate < 0.92
        if run.guardrail_pass_rate and run.guardrail_pass_rate < 0.92:
            severity = "high" if run.guardrail_pass_rate < 0.90 else "medium"

            alert = MonitoringAlert(
                alert_id=uuid.uuid4(),
                alert_type="quality_degradation",
                severity=severity,
                alert_title=f"Guardrail Pass Rate at {run.guardrail_pass_rate*100:.1f}%",
                alert_description=f"Guardrail pass rate has decreased. Current: {run.guardrail_pass_rate*100:.1f}%, expected: >92%",
                affected_component="guardrails",
                metric_name="guardrail_pass_rate",
                current_value=run.guardrail_pass_rate,
                baseline_value=0.95,
                threshold_value=0.92,
                affected_queries={"sample_query_ids": [str(uuid.uuid4()) for _ in range(3)]},
                status="open",
                created_at=run.completed_at,
                updated_at=run.completed_at
            )

            db.add(alert)
            alerts.append(alert)

        # Alert if response time > 2000ms
        if run.avg_response_time_ms and run.avg_response_time_ms > 2000:
            alert = MonitoringAlert(
                alert_id=uuid.uuid4(),
                alert_type="sla_violation",
                severity="medium",
                alert_title=f"High Response Time: {run.avg_response_time_ms:.0f}ms",
                alert_description=f"Average response time exceeds SLA. Current: {run.avg_response_time_ms:.0f}ms, expected: <2000ms",
                affected_component="response_pipeline",
                metric_name="avg_response_time_ms",
                current_value=float(run.avg_response_time_ms),
                baseline_value=1200.0,
                threshold_value=2000.0,
                status="resolved",
                resolved_at=run.completed_at + timedelta(hours=4),
                resolution_notes="Performance improved after database optimization",
                created_at=run.completed_at,
                updated_at=run.completed_at + timedelta(hours=4)
            )

            db.add(alert)
            alerts.append(alert)

    db.commit()
    print(f"✓ Created {len(alerts)} alerts")
    return alerts


def generate_proposals(db, alerts):
    """Generate improvement proposals from alerts"""
    print(f"\n💡 Generating improvement proposals...")

    proposals = []

    # Create proposals for some critical/high severity alerts
    high_priority_alerts = [a for a in alerts if a.severity in ["critical", "high"] and a.status == "open"]

    for i, alert in enumerate(high_priority_alerts[:5]):  # Limit to 5 proposals

        # Determine proposal type based on alert type
        if alert.alert_type == "quality_degradation" and alert.metric_name == "fact_accuracy_score":
            proposal_type = "prompt_change"
            component = "fact_checker"
            title = "Optimize fact-checking prompts to improve accuracy"
            description = "Analysis suggests prompt engineering improvements could boost fact accuracy by refining instructions and examples."
            root_cause = "Current prompts lack specific guidance for handling ambiguous financial data and market-specific terminology"
            improvement_pct = random.uniform(5.0, 8.0)
            effort_hours = random.uniform(4.0, 8.0)
            risk = "low"
        elif alert.alert_type == "quality_degradation" and alert.metric_name == "guardrail_pass_rate":
            proposal_type = "code_fix"
            component = "guardrails"
            title = "Update guardrail rules for better coverage"
            description = "Add new guardrail patterns to catch edge cases identified in recent failures."
            root_cause = "Existing guardrail rules don't cover new edge cases found in recent query patterns"
            improvement_pct = random.uniform(3.0, 5.0)
            effort_hours = random.uniform(2.0, 4.0)
            risk = "low"
        else:
            proposal_type = "config_change"
            component = "response_pipeline"
            title = "Adjust timeout and caching settings"
            description = "Optimize configuration parameters to reduce response latency."
            root_cause = "Current timeout values are too conservative, and cache hit rate is suboptimal"
            improvement_pct = random.uniform(15.0, 20.0)
            effort_hours = random.uniform(1.0, 2.0)
            risk = "medium"

        # Vary proposal statuses
        if i == 0:
            status = "implemented"
            reviewed_at = alert.created_at + timedelta(days=1)
            implemented_at = reviewed_at + timedelta(hours=6)
            review_notes = "Approved for implementation. Metrics show clear degradation pattern."
            reviewed_by = "system_admin"
        elif i == 1:
            status = "rejected"
            reviewed_at = alert.created_at + timedelta(days=1)
            review_notes = "Insufficient confidence in proposed solution. Requires more research."
            reviewed_by = "system_admin"
            implemented_at = None
        else:
            status = "pending_review"
            reviewed_at = None
            review_notes = None
            reviewed_by = None
            implemented_at = None

        proposal = ImprovementProposal(
            proposal_id=uuid.uuid4(),
            proposal_type=proposal_type,
            component_affected=component,
            root_cause=root_cause,
            severity=alert.severity,
            affected_queries_count=random.randint(50, 200),
            proposal_title=title,
            proposal_description=description,
            proposed_changes={
                "change_type": proposal_type,
                "component": component,
                "specific_changes": {
                    "prompts" if proposal_type == "prompt_change" else "config": "detailed_changes_here"
                },
                "rollback_plan": "Revert to previous configuration if metrics don't improve within 24h"
            },
            estimated_improvement_pct=round(improvement_pct, 2),
            estimated_effort_hours=round(effort_hours, 2),
            risk_level=risk,
            status=status,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            review_notes=review_notes,
            implemented_at=implemented_at,
            research_run_id=f"langsmith_run_{uuid.uuid4().hex[:16]}",
            created_at=alert.created_at + timedelta(hours=12),
            updated_at=reviewed_at if reviewed_at else alert.created_at + timedelta(hours=12)
        )

        db.add(proposal)
        proposals.append(proposal)

    db.commit()
    print(f"✓ Created {len(proposals)} improvement proposals")
    return proposals


def generate_validation_results(db, proposals):
    """Generate validation results for proposals"""
    print(f"\n🧪 Generating validation results...")

    validations = []

    # Create validation for implemented and some pending_review proposals
    for proposal in proposals:
        if proposal.status in ["implemented", "pending_review"]:

            # Determine validation outcome
            if proposal.status == "implemented":
                passed = True
                test_size = random.randint(80, 120)
                tests_passed = random.randint(int(test_size * 0.95), test_size)
                tests_failed = test_size - tests_passed
                baseline_metrics = {
                    "fact_accuracy_score": 0.86,
                    "guardrail_pass_rate": 0.90,
                    "avg_response_time_ms": 1800,
                    "sla_compliance_rate": 0.88
                }
                test_metrics = {
                    "fact_accuracy_score": 0.92,
                    "guardrail_pass_rate": 0.94,
                    "avg_response_time_ms": 1650,
                    "sla_compliance_rate": 0.95
                }
                improvement_delta = {
                    "fact_accuracy_improvement": round((0.92 - 0.86) * 100, 2),
                    "guardrail_improvement": round((0.94 - 0.90) * 100, 2),
                    "response_time_improvement": round((1650 - 1800) / 1800 * 100, 2)
                }
            else:
                passed = random.choice([True, False])
                test_size = random.randint(80, 120)
                if passed:
                    tests_passed = random.randint(int(test_size * 0.92), test_size)
                    tests_failed = test_size - tests_passed
                    baseline_metrics = {
                        "fact_accuracy_score": 0.87,
                        "guardrail_pass_rate": 0.89,
                        "avg_response_time_ms": 1950,
                        "sla_compliance_rate": 0.86
                    }
                    test_metrics = {
                        "fact_accuracy_score": 0.91,
                        "guardrail_pass_rate": 0.93,
                        "avg_response_time_ms": 1700,
                        "sla_compliance_rate": 0.92
                    }
                    improvement_delta = {
                        "fact_accuracy_improvement": round((0.91 - 0.87) * 100, 2),
                        "guardrail_improvement": round((0.93 - 0.89) * 100, 2),
                        "response_time_improvement": round((1700 - 1950) / 1950 * 100, 2)
                    }
                else:
                    tests_passed = random.randint(int(test_size * 0.70), int(test_size * 0.85))
                    tests_failed = test_size - tests_passed
                    baseline_metrics = {
                        "fact_accuracy_score": 0.87,
                        "guardrail_pass_rate": 0.89,
                        "avg_response_time_ms": 1950,
                        "sla_compliance_rate": 0.86
                    }
                    test_metrics = {
                        "fact_accuracy_score": 0.85,  # Got worse
                        "guardrail_pass_rate": 0.87,
                        "avg_response_time_ms": 2100,
                        "sla_compliance_rate": 0.84
                    }
                    improvement_delta = {
                        "fact_accuracy_improvement": round((0.85 - 0.87) * 100, 2),
                        "guardrail_improvement": round((0.87 - 0.89) * 100, 2),
                        "response_time_improvement": round((2100 - 1950) / 1950 * 100, 2)
                    }

            validation = ValidationResult(
                validation_id=uuid.uuid4(),
                proposal_id=proposal.proposal_id,
                started_at=proposal.created_at + timedelta(hours=2),
                completed_at=proposal.created_at + timedelta(hours=3),
                status="passed" if passed else "failed",
                test_dataset_size=test_size,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                baseline_metrics=baseline_metrics,
                test_metrics=test_metrics,
                improvement_delta=improvement_delta,
                regressions_detected=not passed,
                regression_details={"critical_regressions": ["fact_accuracy dropped by 2%"]} if not passed else None,
                test_output=f"Validation completed with {tests_passed}/{test_size} tests passing",
                error_logs="" if passed else "Some edge cases failed validation",
                langsmith_dataset_id=f"dataset_{uuid.uuid4().hex[:16]}",
                langsmith_run_ids=[f"run_{uuid.uuid4().hex[:8]}" for _ in range(3)],
                created_at=proposal.created_at + timedelta(hours=3)
            )

            db.add(validation)
            validations.append(validation)

    db.commit()
    print(f"✓ Created {len(validations)} validation results")
    return validations


def print_summary(eval_runs, alerts, proposals, validations):
    """Print summary of generated data"""
    print(f"\n" + "="*60)
    print("📋 SEED DATA SUMMARY")
    print("="*60)

    print(f"\n✓ Evaluation Runs: {len(eval_runs)}")
    print(f"  - Date range: {eval_runs[-1].started_at.strftime('%Y-%m-%d')} to {eval_runs[0].started_at.strftime('%Y-%m-%d')}")

    print(f"\n✓ Alerts: {len(alerts)}")
    alert_status = {}
    alert_severity = {}
    for alert in alerts:
        alert_status[alert.status] = alert_status.get(alert.status, 0) + 1
        alert_severity[alert.severity] = alert_severity.get(alert.severity, 0) + 1

    print(f"  Status breakdown:")
    for status, count in alert_status.items():
        print(f"    - {status}: {count}")
    print(f"  Severity breakdown:")
    for severity, count in alert_severity.items():
        print(f"    - {severity}: {count}")

    print(f"\n✓ Improvement Proposals: {len(proposals)}")
    proposal_status = {}
    for proposal in proposals:
        proposal_status[proposal.status] = proposal_status.get(proposal.status, 0) + 1
    print(f"  Status breakdown:")
    for status, count in proposal_status.items():
        print(f"    - {status}: {count}")

    print(f"\n✓ Validation Results: {len(validations)}")
    validation_status = {}
    for validation in validations:
        validation_status[validation.status] = validation_status.get(validation.status, 0) + 1
    print(f"  Status breakdown:")
    for status, count in validation_status.items():
        print(f"    - {status}: {count}")

    print(f"\n" + "="*60)
    print("✅ Database seeding complete!")
    print("="*60)
    print(f"\n🌐 View dashboard at: http://localhost:8000/dashboard/")
    print()


def main():
    """Main seed data generation function"""
    print("\n" + "="*60)
    print("🌱 META-MONITORING DATABASE SEEDING")
    print("="*60)

    # Get database session
    db = next(get_db())

    try:
        # Generate data
        eval_runs = generate_evaluation_runs(db, num_runs=12)
        alerts = generate_alerts(db, eval_runs)
        proposals = generate_proposals(db, alerts)
        validations = generate_validation_results(db, proposals)

        # Print summary
        print_summary(eval_runs, alerts, proposals, validations)

    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    exit(main())

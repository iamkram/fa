# Meta-Monitoring and Continuous Improvement System

## Overview

This module implements an intelligent meta-monitoring system that continuously monitors, evaluates, and improves the FA AI System through automated analysis, validation, and feedback loops.

## Status

🚧 **IN PROGRESS - Phase 1** 🚧

**Current Progress**:
- ✅ Planning complete (30-page implementation plan in `/docs/META_MONITORING_PLAN.md`)
- ✅ Database schema created (5 new tables)
- ✅ Database migration SQL ready
- ⏳ Agent implementations (pending)
- ⏳ API endpoints (pending)
- ⏳ UI components (pending)

## Architecture

```
Meta-Monitoring System
│
├── Agents
│   ├── Monitoring Agent   - Continuous error detection (every 5 min)
│   ├── Research Agent     - Root cause analysis + improvement proposals
│   ├── Validation Agent   - Pre-deployment testing in sandbox
│   └── Evaluation Agent   - Daily quality scoring + ROI tracking
│
├── Infrastructure
│   ├── Email Notifier     - Critical/hourly/daily alerts
│   ├── Daily Scheduler    - APScheduler for automated tasks
│   └── API Layer          - FastAPI endpoints for admin control
│
└── UI
    └── Admin Dashboard    - React UI for monitoring and approvals
```

## Database Schema

### New Tables

1. **meta_evaluation_runs** - Tracks daily evaluation runs
   - Metrics: fact accuracy, guardrail pass rate, SLA compliance
   - Comparisons vs previous day and baseline

2. **improvement_proposals** - Stores improvement suggestions from Research Agent
   - Root cause analysis
   - Estimated % improvement and effort
   - Review workflow (pending → approved → implemented)

3. **validation_results** - Pre-deployment test results
   - Test suite execution
   - Baseline vs test metrics comparison
   - Regression detection

4. **monitoring_alerts** - Active alerts for errors and anomalies
   - Severity levels (critical/high/medium/low)
   - LangSmith trace URLs for debugging
   - Email notification tracking

5. **improvement_impact** - Post-deployment ROI tracking
   - Before/after metrics
   - Statistical significance
   - ROI calculation

### Migration

Run the migration to create tables:
```bash
PGPASSWORD=dev_password psql -h localhost -U dev_user -d fa_ai_dev -f scripts/migrations/add_meta_monitoring_tables.sql
```

## Implementation Phases

### Phase 1: Foundation & Monitoring (10 days) - IN PROGRESS
- ✅ Database schema
- ⏳ Monitoring Agent
- ⏳ Evaluation Agent
- ⏳ Email notifications
- ⏳ Basic admin dashboard

### Phase 2: Intelligence & Analysis (12 days) - PENDING
- Research Agent
- Validation Agent
- Proposal management
- LangSmith prompt versioning
- Admin review UI

### Phase 3: Automation & Scheduling (8 days) - PENDING
- Daily scheduler
- Auto-approval logic
- Rollback mechanism
- Trend analysis
- Performance tracking

## Key Features

### 1. Continuous Monitoring
- Runs every 5 minutes
- Detects: error spikes, quality degradation, SLA violations, anomalies
- Triggers Research Agent when issues detected

### 2. Improvement Proposals
- Automated root cause analysis
- Specific fix recommendations
- Effort estimation (hours)
- % improvement prediction

### 3. Pre-Deployment Validation
- Tests changes in sandbox
- Golden test dataset (100 cases)
- Prevents regressions
- Statistical significance testing

### 4. Email Notifications
- **Immediate** (< 5 min): Critical errors, security issues
- **Hourly**: High-priority alerts
- **Daily** (9 AM): System health digest

### 5. Admin Dashboard
- Real-time metrics
- Active alerts
- Proposal review workflow
- Trend visualization
- LangSmith integration

## Directory Structure

```
src/meta_monitoring/
├── agents/
│   ├── monitoring_agent.py    # Error detection
│   ├── research_agent.py      # Improvement proposals
│   ├── validation_agent.py    # Pre-deployment testing
│   └── evaluation_agent.py    # Quality scoring
│
├── api/
│   ├── routes.py              # FastAPI endpoints
│   └── models.py              # Pydantic models
│
├── scheduler/
│   └── daily_scheduler.py     # APScheduler jobs
│
├── notifications/
│   ├── email_notifier.py      # Email service
│   └── templates/             # Email templates
│
├── validation/
│   ├── test_runner.py         # Validation test execution
│   └── rollback_manager.py    # Safe rollback
│
└── utils/
    ├── metrics_calculator.py  # Metric calculations
    └── anomaly_detector.py    # Statistical anomaly detection
```

## LangSmith Integration

All meta-monitoring agents use prompts stored in LangSmith hub:

- `meta_error_analyzer` - Analyzes error patterns
- `meta_improvement_proposer` - Proposes improvements
- `meta_root_cause_analyzer` - Identifies root causes
- `meta_validation_evaluator` - Evaluates validation results
- `meta_anomaly_detector` - Detects statistical anomalies
- `meta_impact_calculator` - Calculates improvement impact

All operations are traced to **separate LangSmith project**:
- Project: `fa-ai-meta-monitoring` (to avoid circular dependencies)

## Safety Features

1. **Pre-Validation**: All changes tested before deployment
2. **Gradual Rollout**: 10% → 50% → 100% deployment
3. **Auto-Rollback**: Automatic revert if metrics degrade > 5%
4. **Human Approval**: Required for high-impact changes
5. **Exclusion List**: Meta-monitoring doesn't monitor itself

## Next Steps

1. Run database migration
2. Implement Monitoring Agent
3. Implement Evaluation Agent
4. Set up email notification system
5. Create API endpoints
6. Build admin dashboard
7. Test end-to-end workflow

## Resources

- **Full Plan**: `/docs/META_MONITORING_PLAN.md`
- **Database Models**: `/src/shared/models/meta_monitoring.py`
- **Migration SQL**: `/scripts/migrations/add_meta_monitoring_tables.sql`
- **LangSmith**: https://smith.langchain.com

---

**Version**: 1.0
**Status**: Phase 1 - In Progress
**Started**: 2025-11-08
**Estimated Completion**: 3-4 weeks (with 2 devs)

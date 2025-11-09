# Meta-Monitoring and Continuous Improvement System

## Overview

This module implements an intelligent meta-monitoring system that continuously monitors, evaluates, and improves the FA AI System through automated analysis, validation, and feedback loops.

## Status

✅ **PHASE 1 & 2 COMPLETE** ✅

**Current Progress**:
- ✅ Phase 1: Foundation & Basic Monitoring (COMPLETE)
  - ✅ Planning complete (30-page implementation plan in `/docs/META_MONITORING_PLAN.md`)
  - ✅ Database schema created and migrated (5 new tables)
  - ✅ Monitoring Agent (continuous error detection every 5 min)
  - ✅ Evaluation Agent (daily quality assessment at 3 AM)
  - ✅ Email Notifier (3-tier: immediate/hourly/daily)
  - ✅ API endpoints (14 routes total)
  - ✅ Daily Scheduler with APScheduler (4 automated jobs)

- ✅ Phase 2: Automated Improvement (COMPLETE)
  - ✅ Research Agent (root cause analysis + improvement proposals)
  - ✅ Validation Agent (pre-deployment testing with regression detection)
  - ✅ LangSmith prompts (5 comprehensive prompts stored in prompts/)
  - ✅ Extended API routes (6 new routes for research, validation, proposals)
  - ✅ Human-in-the-loop approval workflow

- ⏳ Phase 3: Admin Dashboard & Testing (IN PROGRESS)
  - ⏳ Admin Dashboard UI (React/Next.js)
  - ⏳ End-to-end workflow testing

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

### Phase 1: Foundation & Monitoring - ✅ COMPLETE
- ✅ Database schema (5 tables)
- ✅ Monitoring Agent (error detection every 5 min)
- ✅ Evaluation Agent (daily quality at 3 AM)
- ✅ Email notifications (3-tier: immediate/hourly/daily)
- ✅ API endpoints (8 routes)
- ✅ Daily scheduler with APScheduler (4 jobs)

### Phase 2: Intelligence & Analysis - ✅ COMPLETE
- ✅ Research Agent (root cause + proposals)
- ✅ Validation Agent (pre-deployment testing)
- ✅ Proposal management API (approve/reject)
- ✅ LangSmith prompts (5 comprehensive prompts)
- ✅ Human-in-the-loop approval workflow

### Phase 3: Dashboard & Testing - ⏳ IN PROGRESS
- ⏳ Admin dashboard UI (React/Next.js)
- ⏳ End-to-end workflow testing
- ⏳ Performance tracking dashboard

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

## Completed

1. ✅ Database migration run and verified (5 tables created)
2. ✅ Monitoring Agent implemented (continuous error detection)
3. ✅ Evaluation Agent implemented (daily quality assessment)
4. ✅ Email notification system ready (SendGrid/AWS SES integration)
5. ✅ API endpoints created (14 routes)
6. ✅ Research Agent implemented (root cause + proposals)
7. ✅ Validation Agent implemented (pre-deployment testing)
8. ✅ LangSmith prompts created (5 prompts)
9. ✅ Daily scheduler implemented (4 automated jobs)

## Next Steps

1. Build Admin Dashboard UI (React/Next.js)
2. Test end-to-end workflow
3. Upload LangSmith prompts to hub
4. Deploy to production

## Resources

- **Full Plan**: `/docs/META_MONITORING_PLAN.md`
- **Database Models**: `/src/shared/models/meta_monitoring.py`
- **Migration SQL**: `/scripts/migrations/add_meta_monitoring_tables.sql`
- **LangSmith**: https://smith.langchain.com

---

**Version**: 2.0
**Status**: Phase 1 & 2 Complete, Phase 3 In Progress
**Started**: 2025-11-08
**Phase 1 & 2 Completed**: 2025-11-08

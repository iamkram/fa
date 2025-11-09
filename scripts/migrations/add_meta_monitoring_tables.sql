-- Meta-Monitoring System Database Migration
-- Created: 2025-11-08
-- Description: Adds tables for meta-monitoring, evaluation, and continuous improvement

-- Meta evaluation runs
CREATE TABLE IF NOT EXISTS meta_evaluation_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'running',

    -- Metrics
    total_queries_evaluated INTEGER,
    fact_accuracy_score FLOAT,
    guardrail_pass_rate FLOAT,
    avg_response_time_ms INTEGER,
    sla_compliance_rate FLOAT,

    -- Comparisons
    vs_previous_day JSONB,
    vs_baseline JSONB,

    -- LangSmith
    langsmith_run_id VARCHAR(255),
    langsmith_project VARCHAR(100),

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_started ON meta_evaluation_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_eval_runs_type ON meta_evaluation_runs(run_type);

-- Improvement proposals
CREATE TABLE IF NOT EXISTS improvement_proposals (
    proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type VARCHAR(50) NOT NULL,
    component_affected VARCHAR(100) NOT NULL,

    -- Problem analysis
    root_cause TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    affected_queries_count INTEGER,

    -- Proposed solution
    proposal_title VARCHAR(255) NOT NULL,
    proposal_description TEXT NOT NULL,
    proposed_changes JSONB NOT NULL,

    -- Impact estimation
    estimated_improvement_pct FLOAT,
    estimated_effort_hours FLOAT,
    risk_level VARCHAR(20),

    -- Status
    status VARCHAR(30) NOT NULL DEFAULT 'pending_review',
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    review_notes TEXT,

    -- Implementation
    implemented_at TIMESTAMP,
    rollback_at TIMESTAMP,

    -- LangSmith
    research_run_id VARCHAR(255),
    validation_run_id VARCHAR(255),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON improvement_proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_severity ON improvement_proposals(severity);
CREATE INDEX IF NOT EXISTS idx_proposals_created ON improvement_proposals(created_at DESC);

-- Validation results
CREATE TABLE IF NOT EXISTS validation_results (
    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES improvement_proposals(proposal_id),

    -- Test execution
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'running',

    -- Results
    test_dataset_size INTEGER,
    tests_passed INTEGER,
    tests_failed INTEGER,

    -- Metrics comparison
    baseline_metrics JSONB NOT NULL,
    test_metrics JSONB NOT NULL,
    improvement_delta JSONB,

    -- Regression detection
    regressions_detected BOOLEAN DEFAULT FALSE,
    regression_details JSONB,

    -- Artifacts
    test_output TEXT,
    error_logs TEXT,
    langsmith_dataset_id VARCHAR(255),
    langsmith_run_ids JSONB,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validation_proposal ON validation_results(proposal_id);
CREATE INDEX IF NOT EXISTS idx_validation_status ON validation_results(status);

-- Monitoring alerts
CREATE TABLE IF NOT EXISTS monitoring_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,

    -- Details
    alert_title VARCHAR(255) NOT NULL,
    alert_description TEXT NOT NULL,
    affected_component VARCHAR(100),

    -- Metrics
    metric_name VARCHAR(100),
    current_value FLOAT,
    baseline_value FLOAT,
    threshold_value FLOAT,

    -- Context
    affected_queries JSONB,
    langsmith_trace_urls JSONB,

    -- Status
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    assigned_to VARCHAR(100),
    resolved_at TIMESTAMP,
    resolution_notes TEXT,

    -- Notifications
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON monitoring_alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON monitoring_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON monitoring_alerts(created_at DESC);

-- Improvement impact tracking
CREATE TABLE IF NOT EXISTS improvement_impact (
    impact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES improvement_proposals(proposal_id),

    -- Time periods
    measurement_start TIMESTAMP NOT NULL,
    measurement_end TIMESTAMP NOT NULL,
    measurement_duration_hours INTEGER,

    -- Before/after metrics
    before_metrics JSONB NOT NULL,
    after_metrics JSONB NOT NULL,

    -- Calculated improvements
    actual_improvement_pct FLOAT,
    statistical_significance FLOAT,

    -- ROI
    time_saved_hours FLOAT,
    cost_savings_usd FLOAT,
    implementation_cost_hours FLOAT,
    roi_ratio FLOAT,

    -- Verdict
    success BOOLEAN,
    success_criteria_met JSONB,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_impact_proposal ON improvement_impact(proposal_id);

-- Add columns to existing tables
ALTER TABLE batch_run_audit
ADD COLUMN IF NOT EXISTS langsmith_run_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS quality_score FLOAT,
ADD COLUMN IF NOT EXISTS improvement_suggestions JSONB;

ALTER TABLE stock_summaries
ADD COLUMN IF NOT EXISTS quality_flags JSONB,
ADD COLUMN IF NOT EXISTS confidence_score FLOAT,
ADD COLUMN IF NOT EXISTS validation_passed BOOLEAN DEFAULT TRUE;

-- Insert baseline metrics for comparison
INSERT INTO meta_evaluation_runs (
    run_id,
    run_type,
    status,
    fact_accuracy_score,
    guardrail_pass_rate,
    avg_response_time_ms,
    sla_compliance_rate
) VALUES (
    gen_random_uuid(),
    'baseline',
    'completed',
    0.93,  -- baseline fact accuracy
    0.98,  -- baseline guardrail pass rate
    2000,  -- baseline response time (2s)
    0.95   -- baseline SLA compliance
) ON CONFLICT DO NOTHING;

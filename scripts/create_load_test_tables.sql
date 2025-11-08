-- Load Test Tables for Performance Testing
-- Tracks load test runs and individual request metrics

-- Load Test Runs Table
CREATE TABLE IF NOT EXISTS load_test_runs (
    id SERIAL PRIMARY KEY,
    test_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed', 'cancelled'

    -- Configuration
    concurrent_users INTEGER NOT NULL,
    total_requests INTEGER NOT NULL,
    duration_seconds INTEGER,
    query_type VARCHAR(50) DEFAULT 'chat',

    -- Results Summary
    requests_completed INTEGER DEFAULT 0,
    requests_failed INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT,
    min_response_time_ms FLOAT,
    max_response_time_ms FLOAT,
    p50_response_time_ms FLOAT,
    p95_response_time_ms FLOAT,
    p99_response_time_ms FLOAT,
    requests_per_second FLOAT,

    -- Timestamps
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Metadata
    initiated_by VARCHAR(255),
    configuration JSONB DEFAULT '{}'::jsonb,
    error_summary JSONB DEFAULT '{}'::jsonb,

    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);

-- Load Test Requests Table (Individual request tracking)
CREATE TABLE IF NOT EXISTS load_test_requests (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES load_test_runs(id) ON DELETE CASCADE,

    -- Request Info
    fa_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    query_text TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT 'chat',

    -- Response Info
    status_code INTEGER,
    success BOOLEAN DEFAULT FALSE,
    response_time_ms FLOAT,
    error_message TEXT,
    langsmith_url TEXT,  -- LangSmith trace URL for debugging

    -- Timestamps
    sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- Response Data (optional, can be large)
    response_summary JSONB DEFAULT '{}'::jsonb
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_load_test_runs_status ON load_test_runs (status);
CREATE INDEX IF NOT EXISTS idx_load_test_runs_created ON load_test_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_load_test_requests_run_id ON load_test_requests (run_id);
CREATE INDEX IF NOT EXISTS idx_load_test_requests_success ON load_test_requests (run_id, success);
CREATE INDEX IF NOT EXISTS idx_load_test_requests_sent_at ON load_test_requests (sent_at);

-- Trigger to auto-update timestamps
CREATE OR REPLACE FUNCTION update_load_test_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.completed_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_load_test_completed
BEFORE UPDATE OF status ON load_test_runs
FOR EACH ROW
WHEN (NEW.status IN ('completed', 'failed', 'cancelled') AND OLD.status != NEW.status)
EXECUTE FUNCTION update_load_test_timestamp();

-- Comments for documentation
COMMENT ON TABLE load_test_runs IS 'Tracks load test execution runs and aggregated metrics';
COMMENT ON TABLE load_test_requests IS 'Individual request logs for each load test run';
COMMENT ON COLUMN load_test_runs.concurrent_users IS 'Number of simulated concurrent users';
COMMENT ON COLUMN load_test_runs.requests_per_second IS 'Throughput metric (requests/second)';

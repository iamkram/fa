-- Admin Tables for Kill Switch Feature
-- Creates system_status and system_status_audit tables

-- System Status Table (singleton - only one row)
CREATE TABLE IF NOT EXISTS system_status (
    id SERIAL PRIMARY KEY,
    status VARCHAR(50) NOT NULL DEFAULT 'active',  -- 'active', 'maintenance', 'degraded'
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    reason TEXT,
    initiated_by VARCHAR(255),
    initiated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    maintenance_message TEXT,
    expected_restoration TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Ensure only one row exists
CREATE UNIQUE INDEX IF NOT EXISTS idx_system_status_singleton ON system_status ((1));

-- Initial active status row
INSERT INTO system_status (status, enabled, reason, initiated_by)
VALUES ('active', TRUE, 'System initialized', 'system')
ON CONFLICT DO NOTHING;

-- Audit Trail Table
CREATE TABLE IF NOT EXISTS system_status_audit (
    id SERIAL PRIMARY KEY,
    status VARCHAR(50) NOT NULL,
    enabled BOOLEAN NOT NULL,
    reason TEXT,
    initiated_by VARCHAR(255),
    maintenance_message TEXT,
    expected_restoration TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_status_audit_created ON system_status_audit (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_status_audit_status ON system_status_audit (status);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_system_status_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS trigger_update_system_status_updated_at ON system_status;
CREATE TRIGGER trigger_update_system_status_updated_at
    BEFORE UPDATE ON system_status
    FOR EACH ROW
    EXECUTE FUNCTION update_system_status_updated_at();

-- Comments for documentation
COMMENT ON TABLE system_status IS 'Stores current system operational status (kill switch state)';
COMMENT ON TABLE system_status_audit IS 'Audit trail for all system status changes';
COMMENT ON COLUMN system_status.status IS 'Current status: active, maintenance, or degraded';
COMMENT ON COLUMN system_status.enabled IS 'Whether system is accepting requests (FALSE when in maintenance)';
COMMENT ON COLUMN system_status.reason IS 'Reason for current status';
COMMENT ON COLUMN system_status.maintenance_message IS 'User-facing message during maintenance';
COMMENT ON COLUMN system_status.expected_restoration IS 'Expected time when service will be restored';

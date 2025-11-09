# Phase 5: Integration Testing & Seed Data Generation

## Overview
Complete end-to-end integration testing of the meta-monitoring system with real data to validate the full workflow from monitoring → evaluation → alerts → proposals → validation → approval → implementation.

## Objectives

1. **Generate Realistic Seed Data**
   - Create sample evaluation runs with realistic metrics
   - Generate alerts based on threshold violations
   - Create improvement proposals from alerts
   - Add validation results for proposals

2. **Test Complete Workflow**
   - Run monitoring agent to detect issues
   - Trigger evaluation agent to assess quality
   - Generate alerts for degraded metrics
   - Research and propose improvements
   - Validate proposals with dry-run testing
   - Test approval workflow

3. **Verify Dashboard Functionality**
   - Confirm all pages display real data correctly
   - Test filtering and sorting
   - Verify charts render with actual metrics
   - Test manual controls integration

4. **Performance & Observability**
   - Verify scheduler runs correctly
   - Test auto-refresh functionality
   - Validate API response times
   - Check database query performance

## Phase 5 Tasks

### Task 1: Create Seed Data Script
**File**: `scripts/seed_meta_monitoring_data.py`

Generate realistic test data:
- 10-15 evaluation runs spanning the last 7 days
- Varying metrics (fact accuracy: 0.85-0.98, guardrail rate: 0.90-0.99)
- 5-8 alerts (mix of critical, high, medium severity)
- 3-5 improvement proposals (pending, approved, rejected)
- 2-3 validation results

### Task 2: End-to-End Workflow Test
**File**: `tests/meta_monitoring/test_integration_workflow.py`

Test complete flow:
1. Trigger evaluation manually via API
2. Verify alert generation from low metrics
3. Trigger proposal generation from alert
4. Run validation on proposal
5. Approve/reject proposal via API
6. Verify state transitions in database

### Task 3: Dashboard Verification
**Test Script**: Manual verification checklist

For each dashboard page:
- [ ] Overview: System health shows correct status
- [ ] Overview: Metrics display with real values
- [ ] Overview: Recent alerts table populates
- [ ] Overview: Proposals summary shows data
- [ ] Alerts: Table displays all alerts correctly
- [ ] Alerts: Filtering works (severity, status)
- [ ] Alerts: Modal view shows full details
- [ ] Proposals: Table shows all proposals
- [ ] Proposals: Filtering works (status, type)
- [ ] Proposals: Approve/reject actions work
- [ ] Metrics: Current metrics display correctly
- [ ] Metrics: Charts render with real data
- [ ] Metrics: Timeframe filtering works
- [ ] Controls: System status displays correctly
- [ ] Controls: Manual triggers work (evaluation, proposal, validation)

### Task 4: API Integration Tests
**File**: `tests/meta_monitoring/test_api_integration.py`

Test all 15 meta-monitoring API endpoints:
1. GET /api/meta-monitoring/health
2. GET /api/meta-monitoring/metrics/latest
3. GET /api/meta-monitoring/alerts
4. GET /api/meta-monitoring/alerts/stats
5. POST /api/meta-monitoring/alerts/{id}/acknowledge
6. POST /api/meta-monitoring/alerts/{id}/resolve
7. GET /api/meta-monitoring/proposals
8. GET /api/meta-monitoring/proposals/stats
9. GET /api/meta-monitoring/proposals/{id}
10. POST /api/meta-monitoring/proposals/{id}/approve
11. POST /api/meta-monitoring/proposals/{id}/reject
12. GET /api/meta-monitoring/metrics/trends
13. POST /api/meta-monitoring/control/evaluate
14. POST /api/meta-monitoring/control/generate-proposal
15. POST /api/meta-monitoring/control/validate-proposal

### Task 5: Performance Benchmarks
**File**: `scripts/benchmark_meta_monitoring.py`

Measure performance:
- Dashboard page load times
- API endpoint response times
- Database query execution times
- Chart rendering performance
- Auto-refresh impact

### Task 6: Production Readiness Checklist

**Error Handling**:
- [ ] API endpoints return proper error codes
- [ ] Database errors are caught and logged
- [ ] Agent failures are handled gracefully
- [ ] Frontend shows user-friendly error messages

**Logging**:
- [ ] All agents log to LangSmith
- [ ] Database operations are logged
- [ ] API requests are logged
- [ ] Errors include stack traces

**Security**:
- [ ] No sensitive data in logs
- [ ] API endpoints validate input
- [ ] SQL injection prevention verified
- [ ] XSS prevention in dashboard

**Scalability**:
- [ ] Database connection pooling configured
- [ ] Indexes on frequently queried columns
- [ ] Pagination for large result sets
- [ ] Cache headers for static assets

## Success Criteria

1. **Seed Data**: Database populated with realistic test data
2. **Workflow**: Complete alert → proposal → validation → approval flow works
3. **Dashboard**: All 5 pages display real data without errors
4. **API**: All 15 endpoints return valid responses
5. **Performance**: Page loads < 2s, API responses < 500ms
6. **Tests**: Integration test suite passes (10+ tests)

## Timeline

- **Task 1-2**: Seed data + workflow tests (2-3 hours)
- **Task 3-4**: Dashboard verification + API tests (2-3 hours)
- **Task 5-6**: Performance + production readiness (1-2 hours)

**Total Estimated Time**: 5-8 hours

## Deliverables

1. `scripts/seed_meta_monitoring_data.py` - Seed data generator
2. `tests/meta_monitoring/test_integration_workflow.py` - Integration tests
3. `tests/meta_monitoring/test_api_integration.py` - API tests
4. `scripts/benchmark_meta_monitoring.py` - Performance benchmarks
5. `docs/PHASE5_RESULTS.md` - Test results and findings
6. Git commit with all Phase 5 work

## Next Steps After Phase 5

**Phase 6 Options**:
- **Production Deployment**: Docker compose, environment configs, CI/CD
- **Advanced Features**: Trend analysis, anomaly detection, A/B testing support
- **Notification System**: Email/Slack alerts for critical issues
- **Audit Trail**: Complete change history and rollback capability

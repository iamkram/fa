# Admin Dashboard Implementation Plan

## Overview

Build a lightweight, real-time admin dashboard for the meta-monitoring system using HTML/CSS/JavaScript served by FastAPI.

## Architecture Decision

**Approach**: Static HTML/CSS/JavaScript dashboard served by FastAPI
- **Why**: Simpler to integrate, no build step, uses existing FastAPI server
- **Alternative**: Next.js/React app would require separate server and more complexity

## Available API Endpoints (15 total)

### System Health & Metrics
1. `GET /meta-monitoring/health` - Overall system status
2. `GET /meta-monitoring/metrics/trend` - Trend data

### Alerts
3. `GET /meta-monitoring/alerts` - List alerts (filterable)
4. `PUT /meta-monitoring/alerts/{alert_id}/status` - Update alert status

### Evaluations
5. `GET /meta-monitoring/evaluations` - List evaluation runs
6. `GET /meta-monitoring/evaluations/{run_id}` - Get specific evaluation

### Manual Triggers
7. `POST /meta-monitoring/monitoring/run` - Manually run monitoring
8. `POST /meta-monitoring/evaluation/run` - Manually run evaluation

### Proposals
9. `GET /meta-monitoring/proposals` - List proposals (filterable)
10. `POST /meta-monitoring/research/analyze-alert/{alert_id}` - Generate proposal from alert
11. `POST /meta-monitoring/research/batch-analyze` - Batch analyze alerts

### Validation
12. `POST /meta-monitoring/validation/validate-proposal/{proposal_id}` - Validate proposal
13. `GET /meta-monitoring/validation/results/{proposal_id}` - Get validation results

### Approval Workflow
14. `POST /meta-monitoring/proposals/{proposal_id}/approve` - Approve proposal
15. `POST /meta-monitoring/proposals/{proposal_id}/reject` - Reject proposal

## Dashboard Pages/Sections

### 1. Overview Dashboard (Home)
**Components**:
- System Health Status Card
  - Overall status badge (healthy/degraded/critical)
  - Active alerts count
  - Critical alerts count
  - Latest evaluation summary

- Key Metrics Grid (from last 24h)
  - Fact Accuracy
  - Guardrail Pass Rate
  - Avg Response Time
  - SLA Compliance Rate

- Recent Alerts Table (top 10)
  - Severity badge
  - Alert type
  - Title
  - Time
  - Quick action buttons

- Active Proposals Summary
  - Pending review count
  - Approved count
  - Quick links

**Auto-refresh**: Every 30 seconds

### 2. Alerts Page
**Components**:
- Filter Panel
  - Status: Open/Resolved/All
  - Severity: Critical/High/Medium/Low/All
  - Time range selector

- Alerts Table
  - Severity badge
  - Alert type
  - Title & description
  - Affected component
  - Metric values (current/baseline/threshold)
  - LangSmith trace URLs (clickable)
  - Created timestamp
  - Actions: Mark resolved, Generate proposal

- Alert Detail Modal
  - Full details
  - Related traces
  - Timeline
  - Action buttons

**Auto-refresh**: Every 15 seconds

### 3. Proposals Page
**Components**:
- Status Tabs
  - Pending Review
  - Approved
  - Rejected
  - All

- Proposals Table
  - Type badge
  - Title
  - Component affected
  - Severity
  - Estimated improvement %
  - Estimated effort (hours)
  - Risk level
  - Created timestamp
  - Status
  - Actions

- Proposal Detail Modal
  - Full root cause analysis
  - Proposed changes (with code diff)
  - Estimated impact
  - Test plan
  - Rollback plan
  - Validation results (if validated)
  - Approve/Reject buttons

**Auto-refresh**: Every 60 seconds

### 4. Metrics & Trends Page
**Components**:
- Time Range Selector
  - Last 24 hours
  - Last 7 days
  - Last 30 days
  - Custom range

- Line Charts (using Chart.js)
  - Fact Accuracy over time
  - Guardrail Pass Rate over time
  - Response Time over time
  - SLA Compliance over time

- Evaluation Runs Table
  - Timestamp
  - Run type (daily/manual)
  - Status
  - Total queries evaluated
  - All metrics
  - Comparison vs baseline

**Auto-refresh**: Every 120 seconds

### 5. Manual Controls Page
**Components**:
- Run Monitoring Button
  - Immediately execute monitoring agent
  - Show progress/results

- Run Evaluation Button
  - Choose evaluation type (daily/test)
  - Show progress/results

- Batch Analyze Alerts Button
  - Select time range
  - Generate proposals for all actionable alerts
  - Show batch results

## UI Technology Stack

### Core Technologies
- **HTML5** - Structure
- **CSS3** - Styling (no framework, custom styles)
- **Vanilla JavaScript** - Interactivity
- **Chart.js** - Data visualization
- **Fetch API** - API calls

### Styling Approach
- Clean, modern design
- Dark mode option
- Responsive layout (mobile-friendly)
- Color-coded severity levels:
  - Critical: Red (#EF4444)
  - High: Orange (#F59E0B)
  - Medium: Yellow (#FBBF24)
  - Low: Blue (#3B82F6)

### Key Features
- Auto-refresh with visual indicator
- Toast notifications for actions
- Loading states
- Error handling
- Confirmation dialogs for destructive actions

## File Structure

```
src/meta_monitoring/dashboard/
├── static/
│   ├── css/
│   │   └── dashboard.css        # All styles
│   ├── js/
│   │   ├── api.js              # API client
│   │   ├── utils.js            # Helper functions
│   │   ├── overview.js         # Overview page logic
│   │   ├── alerts.js           # Alerts page logic
│   │   ├── proposals.js        # Proposals page logic
│   │   ├── metrics.js          # Metrics page logic
│   │   └── controls.js         # Manual controls logic
│   └── lib/
│       └── chart.min.js        # Chart.js library
└── templates/
    ├── base.html               # Base template with navigation
    ├── overview.html           # Overview dashboard
    ├── alerts.html             # Alerts page
    ├── proposals.html          # Proposals page
    ├── metrics.html            # Metrics & trends page
    └── controls.html           # Manual controls page
```

## Implementation Phases

### Phase 4A: Setup & Infrastructure (1-2 hours)
- [x] Create dashboard directory structure
- [ ] Add FastAPI routes to serve HTML templates
- [ ] Create base.html with navigation
- [ ] Create dashboard.css with base styles
- [ ] Create api.js client

### Phase 4B: Overview Dashboard (2-3 hours)
- [ ] Create overview.html template
- [ ] Build system health card component
- [ ] Build metrics grid component
- [ ] Build recent alerts table
- [ ] Add auto-refresh logic

### Phase 4C: Alerts Page (2-3 hours)
- [ ] Create alerts.html template
- [ ] Build filter panel
- [ ] Build alerts table with actions
- [ ] Build alert detail modal
- [ ] Add alert status update functionality

### Phase 4D: Proposals Page (3-4 hours)
- [ ] Create proposals.html template
- [ ] Build status tabs
- [ ] Build proposals table
- [ ] Build proposal detail modal
- [ ] Implement approve/reject actions
- [ ] Show validation results

### Phase 4E: Metrics & Trends (2-3 hours)
- [ ] Create metrics.html template
- [ ] Integrate Chart.js
- [ ] Build time range selector
- [ ] Build line charts for all metrics
- [ ] Build evaluation runs table

### Phase 4F: Manual Controls (1-2 hours)
- [ ] Create controls.html template
- [ ] Add run monitoring button
- [ ] Add run evaluation button
- [ ] Add batch analyze button
- [ ] Show progress indicators

### Phase 4G: Polish & Testing (2-3 hours)
- [ ] Add error handling
- [ ] Add loading states
- [ ] Add toast notifications
- [ ] Add confirmation dialogs
- [ ] Test all workflows
- [ ] Mobile responsive testing

## Total Estimated Time: 13-20 hours

## Success Criteria

1. ✅ Dashboard loads and displays real data from API
2. ✅ Auto-refresh works on all pages
3. ✅ All 15 API endpoints are utilized
4. ✅ Proposal approval/rejection workflow works
5. ✅ Charts display metrics trends correctly
6. ✅ Manual controls trigger agents successfully
7. ✅ Mobile responsive
8. ✅ Error handling for all API calls

## Next Steps

1. Start with Phase 4A: Setup & Infrastructure
2. Create FastAPI routes to serve dashboard
3. Build base template with navigation
4. Implement overview dashboard
5. Iterate through remaining phases

# Meta-Monitoring LangSmith Prompts

This directory contains prompts for the meta-monitoring and continuous improvement system. These prompts should be uploaded to LangSmith Hub for centralized management and version control.

## Prompts Overview

### 1. **meta_anomaly_detector.md**
- **Purpose**: Detect anomalies in production metrics and assign severity levels
- **Model**: Claude Sonnet 4 (claude-sonnet-4-20250514)
- **Temperature**: 0.0 (deterministic)
- **Used by**: MonitoringAgent (`src/meta_monitoring/agents/monitoring_agent.py`)
- **Input**: Current metrics, baseline metrics, error samples
- **Output**: Anomaly detection results with severity classification

### 2. **meta_root_cause_analyzer.md**
- **Purpose**: Perform deep root cause analysis of alerts
- **Model**: Claude Sonnet 4 (claude-sonnet-4-20250514)
- **Temperature**: 0.3 (creative problem-solving)
- **Used by**: ResearchAgent (`src/meta_monitoring/agents/research_agent.py`)
- **Input**: Alert details, LangSmith traces, system context
- **Output**: Root cause with technical details and actionability assessment

### 3. **meta_improvement_proposer.md**
- **Purpose**: Generate specific, implementable improvement proposals
- **Model**: Claude Sonnet 4 (claude-sonnet-4-20250514)
- **Temperature**: 0.3 (creative problem-solving)
- **Used by**: ResearchAgent (`src/meta_monitoring/agents/research_agent.py`)
- **Input**: Root cause analysis, alert details
- **Output**: Detailed proposal with effort estimates, test plan, rollback plan

### 4. **meta_validation_evaluator.md**
- **Purpose**: Evaluate validation test results and make deployment recommendations
- **Model**: Claude Sonnet 4 (claude-sonnet-4-20250514)
- **Temperature**: 0.0 (strict evaluation)
- **Used by**: ValidationAgent (`src/meta_monitoring/agents/validation_agent.py`)
- **Input**: Validation test results, baseline metrics, improvement deltas
- **Output**: APPROVE/REJECT/NEEDS_REVIEW recommendation with detailed analysis

### 5. **meta_impact_calculator.md**
- **Purpose**: Calculate actual ROI and impact after deployment
- **Model**: Claude Sonnet 4 (claude-sonnet-4-20250514)
- **Temperature**: 0.0 (precise calculations)
- **Used by**: Future ImpactAnalysisAgent (Phase 3)
- **Input**: Pre/post deployment metrics, estimates, validation results
- **Output**: Actual improvement metrics, ROI score, estimate accuracy

### 6. **meta_error_analyzer.md** (To be created in future)
- **Purpose**: Analyze error patterns and trends
- **Used by**: MonitoringAgent for deep error analysis

## Upload to LangSmith Hub

To upload these prompts to LangSmith:

```bash
# Install LangSmith CLI if not already installed
pip install langsmith

# Upload each prompt
langsmith hub push meta_anomaly_detector --file src/meta_monitoring/prompts/meta_anomaly_detector.md
langsmith hub push meta_root_cause_analyzer --file src/meta_monitoring/prompts/meta_root_cause_analyzer.md
langsmith hub push meta_improvement_proposer --file src/meta_monitoring/prompts/meta_improvement_proposer.md
langsmith hub push meta_validation_evaluator --file src/meta_monitoring/prompts/meta_validation_evaluator.md
langsmith hub push meta_impact_calculator --file src/meta_monitoring/prompts/meta_impact_calculator.md
```

## Integration with Agents

Update agents to load prompts from LangSmith:

```python
from langchain import hub

# Load prompt from LangSmith Hub
anomaly_prompt = hub.pull("meta_anomaly_detector")

# Use with LLM
response = llm.invoke(anomaly_prompt.format(
    current_metrics=current_metrics,
    baseline_metrics=baseline_metrics
))
```

## Prompt Versioning

- All prompts are version-controlled in LangSmith Hub
- Use semantic versioning: v1.0.0, v1.1.0, v2.0.0
- Test new versions in development before promoting to production
- Rollback capability: Revert to previous version with one click

## Best Practices

1. **Test locally first**: Validate prompt changes with test cases before uploading
2. **Document changes**: Include version notes when updating prompts
3. **A/B testing**: Compare new prompt versions against current production
4. **Monitor performance**: Track prompt effectiveness metrics in LangSmith
5. **Iterate based on data**: Use actual agent performance to refine prompts

## Prompt Maintenance Schedule

- **Weekly**: Review prompt performance metrics
- **Monthly**: Analyze edge cases and failure modes
- **Quarterly**: Major prompt optimization based on accumulated data

## Related Documentation

- Meta-Monitoring Plan: `docs/META_MONITORING_PLAN.md`
- Agent Implementation: `src/meta_monitoring/agents/`
- Database Schema: `scripts/migrations/add_meta_monitoring_tables.sql`

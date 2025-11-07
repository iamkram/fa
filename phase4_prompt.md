
# Phase 4: Production Scaling & Advanced Features

Save as: `phase4_prompt.md`
````markdown
# Phase 4: Production Scaling, Optimization & Advanced Features

## Context

You have completed Phase 3 with:
- ✅ Interactive query system with Deep Agents UI
- ✅ Multi-agent research pipeline
- ✅ Input/output guardrails
- ✅ EDO context integration via MCP
- ✅ Real-time news research
- ✅ Memory and conversation management

## Phase 4 Objectives

Prepare system for production at scale:
1. **Scale batch to 1,000 stocks** with optimized concurrency (< 4 hours)
2. **Support 4,000 FAs** with 500 concurrent queries
3. **Implement cost optimization** (reduce to < $0.40/stock, < $0.08/query)
4. **Add advanced guardrails** (hallucination detection, uncertainty quantification)
5. **Build A/B testing framework** for prompt optimization
6. **Set up monitoring & alerting** (CloudWatch, LangSmith)
7. **Configure blue-green deployment** for zero-downtime releases
8. **Create comprehensive evaluation suite** for CI/CD
9. **Generate production documentation** and runbooks

---

## Task 4.1: Batch Scaling to 1,000 Stocks

### Optimize Orchestrator

Update `src/batch/orchestrator.py`:
```python
class BatchOrchestrator:
    """Enhanced orchestrator with caching and optimization"""
    
    def __init__(self, max_concurrency: int = 100):  # Increased from 50
        self.max_concurrency = max_concurrency
        self.graph = create_phase2_batch_graph()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.cache_manager = EmbeddingCacheManager()  # New
    
    async def process_stock_with_caching(
        self,
        stock: Stock,
        batch_run_id: str
    ) -> dict:
        """Process stock with embedding cache"""
        
        async with self.semaphore:
            # Check if source data has changed
            current_hash = await self._compute_source_hash(stock)
            cached_hash = await self.cache_manager.get_hash(stock.ticker)
            
            if current_hash == cached_hash:
                logger.info(f"[Cache] Using cached embeddings for {stock.ticker}")
                # Skip re-embedding, use cached vectors
                # ... implementation
            
            # Process normally if cache miss
            result = await self.graph.ainvoke(...)
            
            # Update cache
            await self.cache_manager.set_hash(stock.ticker, current_hash)
            
            return result
```

### Create Embedding Cache Manager

Create `src/shared/utils/caching.py`:
```python
"""
Embedding cache to avoid re-embedding unchanged content
"""

import hashlib
import redis
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class EmbeddingCacheManager:
    """Manage embedding cache in Redis"""
    
    def __init__(self):
        self.redis_client = redis.from_url(get_settings().redis_url)
        self.ttl = 604800  # 7 days
    
    def _embedding_key(self, identifier: str) -> str:
        return f"embedding_hash:{identifier}"
    
    async def get_hash(self, identifier: str) -> Optional[str]:
        """Get cached hash for identifier"""
        key = self._embedding_key(identifier)
        cached = self.redis_client.get(key)
        return cached.decode() if cached else None
    
    async def set_hash(self, identifier: str, content_hash: str):
        """Store content hash"""
        key = self._embedding_key(identifier)
        self.redis_client.setex(key, self.ttl, content_hash)
    
    def compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content"""
        return hashlib.sha256(content.encode()).hexdigest()
```

### Optimize Database Writes

Create `src/batch/nodes/bulk_storage.py`:
```python
def bulk_storage_node(states: List[BatchGraphState], config) -> Dict[str, Any]:
    """Bulk insert summaries (50 at a time)"""
    
    with db_manager.get_session() as session:
        # Prepare all summaries
        summaries = []
        citations = []
        
        for state in states:
            summary = StockSummary(...)
            summaries.append(summary)
        
        # Bulk insert
        session.bulk_save_objects(summaries, return_defaults=True)
        session.commit()
        
        logger.info(f"Bulk inserted {len(summaries)} summaries")
```

---

## Task 4.2: Cost Optimization

### Create Cost Tracker

Create `src/shared/utils/cost_tracker.py`:
```python
"""
Track LLM token usage and costs
"""

from typing import Dict
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    timestamp: datetime

class CostTracker:
    """Track costs across all LLM calls"""
    
    # Pricing (per 1M tokens)
    PRICING = {
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-20250514": {"input": 0.25, "output": 1.25},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "text-embedding-3-large": {"input": 0.13, "output": 0.0}
    }
    
    def __init__(self):
        self.usage_by_agent = {}
    
    def record_usage(
        self,
        agent_name: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ):
        """Record token usage"""
        if agent_name not in self.usage_by_agent:
            self.usage_by_agent[agent_name] = []
        
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
            timestamp=datetime.utcnow()
        )
        
        self.usage_by_agent[agent_name].append(usage)
    
    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost for a call"""
        if model not in self.PRICING:
            logger.warning(f"Unknown model: {model}")
            return 0.0
        
        pricing = self.PRICING[model]
        cost = (
            (prompt_tokens / 1_000_000) * pricing["input"] +
            (completion_tokens / 1_000_000) * pricing["output"]
        )
        return cost
    
    def get_total_cost(self) -> float:
        """Get total cost across all agents"""
        total = 0.0
        for agent, usages in self.usage_by_agent.items():
            for usage in usages:
                total += self.calculate_cost(
                    usage.model,
                    usage.prompt_tokens,
                    usage.completion_tokens
                )
        return total
    
    def get_cost_by_agent(self) -> Dict[str, float]:
        """Get cost breakdown by agent"""
        costs = {}
        for agent, usages in self.usage_by_agent.items():
            agent_cost = sum(
                self.calculate_cost(u.model, u.prompt_tokens, u.completion_tokens)
                for u in usages
            )
            costs[agent] = agent_cost
        return costs

# Global tracker
cost_tracker = CostTracker()
```

### Create Model Router for Cost Optimization

Create `src/shared/utils/model_router.py`:
```python
"""
Route tasks to appropriate models based on complexity
"""

from typing import Literal
import logging

logger = logging.getLogger(__name__)

class ModelRouter:
    """Route LLM tasks to cost-appropriate models"""
    
    # Task complexity → Model mapping
    TASK_MODEL_MAP = {
        # Complex creative tasks → Sonnet
        "summary_generation": "claude-sonnet-4-20250514",
        "response_writing": "claude-sonnet-4-20250514",
        
        # Structured extraction → Haiku
        "claim_extraction": "claude-haiku-4-20250514",
        "fact_checking": "claude-haiku-4-20250514",
        "classification": "claude-haiku-4-20250514",
        "guardrails": "claude-haiku-4-20250514"
    }
    
    @classmethod
    def get_model_for_task(
        cls,
        task: Literal[
            "summary_generation",
            "response_writing",
            "claim_extraction",
            "fact_checking",
            "classification",
            "guardrails"
        ]
    ) -> str:
        """Get appropriate model for task"""
        model = cls.TASK_MODEL_MAP.get(task, "claude-sonnet-4-20250514")
        logger.debug(f"Routing task '{task}' to model '{model}'")
        return model
```

### Create Cost Dashboard

Create `dashboards/cost_dashboard.py`:
```python
"""
Streamlit dashboard for cost monitoring
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from src.shared.utils.cost_tracker import cost_tracker
from src.shared.database.connection import db_manager
from src.shared.models.database import BatchRunAudit

st.title("FA AI System - Cost Dashboard")

# Date range selector
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", datetime.utcnow() - timedelta(days=7))
with col2:
    end_date = st.date_input("End Date", datetime.utcnow())

# Batch Process Costs
st.header("Batch Process Costs")

with db_manager.get_session() as session:
    audits = session.query(BatchRunAudit).filter(
        BatchRunAudit.run_date >= start_date,
        BatchRunAudit.run_date <= end_date
    ).all()
    
    if audits:
        df_batch = pd.DataFrame([{
            "Date": a.run_date,
            "Stocks Processed": a.total_stocks_processed,
            "Duration (min)": (a.end_timestamp - a.start_timestamp).total_seconds() / 60,
            "Success Rate": f"{(a.successful_summaries / a.total_stocks_processed * 100):.1f}%"
        } for a in audits])
        
        st.dataframe(df_batch)
        
        # Cost estimates (would be calculated from actual token usage)
        total_stocks = sum(a.total_stocks_processed for a in audits)
        estimated_cost = total_stocks * 0.40  # $0.40 per stock target
        
        st.metric("Total Estimated Cost", f"${estimated_cost:.2f}")
        st.metric("Cost per Stock", f"${estimated_cost / total_stocks:.2f}")

# Agent Cost Breakdown
st.header("Cost by Agent")

agent_costs = cost_tracker.get_cost_by_agent()
if agent_costs:
    df_agents = pd.DataFrame([
        {"Agent": agent, "Cost": f"${cost:.2f}"}
        for agent, cost in sorted(agent_costs.items(), key=lambda x: x[1], reverse=True)
    ])
    st.dataframe(df_agents)

# Run dashboard: streamlit run dashboards/cost_dashboard.py
```

---

## Task 4.3: Advanced Hallucination Detection

Create `src/shared/utils/hallucination_detector.py`:
```python
"""
Multi-layer hallucination detection
"""

from typing import Dict, Any, List
import logging
from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)

class HallucinationDetector:
    """Detect hallucinations using multiple techniques"""
    
    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-haiku-4-20250514",
            temperature=0.0
        )
    
    async def detect(
        self,
        response_text: str,
        source_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect potential hallucinations
        
        Returns: {
            "has_hallucination": bool,
            "confidence": float,
            "flagged_claims": List[str]
        }
        """
        
        checks = []
        
        # 1. Cross-source consistency check
        consistency_result = await self._check_cross_source_consistency(
            response_text,
            source_context
        )
        checks.append(consistency_result)
        
        # 2. Temporal consistency check
        temporal_result = self._check_temporal_consistency(response_text)
        checks.append(temporal_result)
        
        # 3. Uncertainty quantification
        uncertainty_result = await self._quantify_uncertainty(response_text)
        checks.append(uncertainty_result)
        
        # Aggregate results
        has_hallucination = any(c["has_issue"] for c in checks)
        flagged_claims = []
        for c in checks:
            flagged_claims.extend(c.get("flagged_claims", []))
        
        return {
            "has_hallucination": has_hallucination,
            "confidence": 1.0 - (sum(c.get("severity", 0) for c in checks) / len(checks)),
            "flagged_claims": flagged_claims,
            "check_details": checks
        }
    
    async def _check_cross_source_consistency(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify claims appear in multiple sources"""
        
        prompt = f"""
        Response: {response}
        
        Available sources:
        - BlueMatrix: {context.get('bluematrix_summary', 'N/A')}
        - EDGAR: {context.get('edgar_summary', 'N/A')}
        - FactSet: {context.get('factset_summary', 'N/A')}
        
        Identify any claims in the response that:
        1. Don't appear in ANY source
        2. Contradict information in sources
        3. Are only in one source but stated as fact
        
        Output JSON: {{
            "has_issue": bool,
            "severity": 0.0-1.0,
            "flagged_claims": [...]
        }}
        """
        
        response = await self.llm.ainvoke(prompt)
        
        # Parse response
        # ... implementation
        
        return {"has_issue": False, "severity": 0.0, "flagged_claims": []}
    
    def _check_temporal_consistency(self, response: str) -> Dict[str, Any]:
        """Check for temporally impossible claims"""
        import re
        from datetime import datetime
        
        # Extract dates
        date_pattern = r'\b\d{1,2}/\d{1,2}/\d{4}\b'
        dates = re.findall(date_pattern, response)
        
        # Check for future dates
        flagged = []
        for date_str in dates:
            try:
                date = datetime.strptime(date_str, "%m/%d/%Y")
                if date > datetime.utcnow():
                    flagged.append(f"Future date detected: {date_str}")
            except ValueError:
                continue
        
        return {
            "has_issue": len(flagged) > 0,
            "severity": 1.0 if flagged else 0.0,
            "flagged_claims": flagged
        }
    
    async def _quantify_uncertainty(self, response: str) -> Dict[str, Any]:
        """Flag low-confidence claims"""
        
        # Look for hedging language
        hedge_words = ["may", "might", "could", "possibly", "perhaps", "unclear", "uncertain"]
        
        hedges_found = [word for word in hedge_words if word in response.lower()]
        
        return {
            "has_issue": False,  # Hedging is good, not an issue
            "severity": 0.0,
            "flagged_claims": [],
            "hedge_count": len(hedges_found)
        }
```

---

## Task 4.4: A/B Testing Framework

Create `src/shared/utils/ab_testing.py`:
```python
"""
A/B testing framework for prompts and models
"""

import hashlib
from typing import Dict, Any, Literal
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ABVariant:
    """Single A/B test variant"""
    name: str
    prompt_version: str
    model: str
    traffic_percentage: int

class ABTestManager:
    """Manage A/B tests"""
    
    def __init__(self):
        self.active_tests = {}
    
    def register_test(
        self,
        test_name: str,
        variants: list[ABVariant],
        metrics: list[str],
        duration_hours: int = 72
    ):
        """Register a new A/B test"""
        # Validate traffic percentages sum to 100
        total_traffic = sum(v.traffic_percentage for v in variants)
        assert total_traffic == 100, "Traffic percentages must sum to 100"
        
        self.active_tests[test_name] = {
            "variants": variants,
            "metrics": metrics,
            "start_time": datetime.utcnow(),
            "duration_hours": duration_hours,
            "results": {v.name: {"calls": 0, "metrics": {}} for v in variants}
        }
        
        logger.info(f"Registered A/B test: {test_name}")
    
    def get_variant(
        self,
        test_name: str,
        user_id: str
    ) -> ABVariant:
        """Assign user to variant based on consistent hashing"""
        
        if test_name not in self.active_tests:
            logger.warning(f"Test {test_name} not found, using default")
            return None
        
        test = self.active_tests[test_name]
        variants = test["variants"]
        
        # Hash user_id to get consistent assignment
        hash_value = int(hashlib.md5(f"{test_name}:{user_id}".encode()).hexdigest(), 16)
        bucket = hash_value % 100
        
        # Assign to variant based on traffic percentages
        cumulative = 0
        for variant in variants:
            cumulative += variant.traffic_percentage
            if bucket < cumulative:
                return variant
        
        return variants[-1]  # Fallback
    
    def record_metric(
        self,
        test_name: str,
        variant_name: str,
        metric_name: str,
        value: float
    ):
        """Record metric for variant"""
        
        if test_name not in self.active_tests:
            return
        
        test = self.active_tests[test_name]
        results = test["results"][variant_name]
        
        results["calls"] += 1
        
        if metric_name not in results["metrics"]:
            results["metrics"][metric_name] = []
        
        results["metrics"][metric_name].append(value)
    
    def get_results(self, test_name: str) -> Dict[str, Any]:
        """Get test results"""
        
        if test_name not in self.active_tests:
            return {}
        
        test = self.active_tests[test_name]
        
        # Calculate statistics for each variant
        summary = {}
        for variant_name, results in test["results"].items():
            metrics_summary = {}
            for metric_name, values in results["metrics"].items():
                if values:
                    metrics_summary[metric_name] = {
                        "mean": sum(values) / len(values),
                        "count": len(values),
                        "min": min(values),
                        "max": max(values)
                    }
            
            summary[variant_name] = {
                "total_calls": results["calls"],
                "metrics": metrics_summary
            }
        
        return summary

# Global manager
ab_test_manager = ABTestManager()
```

### Example A/B Test Configuration

Create `config/ab_tests.yaml`:
```yaml
tests:
  - name: "medium_writer_prompt_v2"
    variants:
      - name: "control"
        prompt_version: "medium_writer_v1"
        model: "claude-sonnet-4-20250514"
        traffic_percentage: 90
      
      - name: "treatment"
        prompt_version: "medium_writer_v2"
        model: "claude-sonnet-4-20250514"
        traffic_percentage: 10
    
    metrics:
      - "fact_check_pass_rate"
      - "word_count"
      - "generation_time_ms"
    
    duration_hours: 72
    
    success_criteria:
      fact_check_pass_rate: "> control + 0.02"  # 2% improvement
```

---

## Task 4.5: Monitoring & Alerting

### Create CloudWatch Metrics Publisher

Create `src/shared/utils/metrics.py`:
```python
"""
Publish custom metrics to CloudWatch
"""

import boto3
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class MetricsPublisher:
    """Publish metrics to AWS CloudWatch"""
    
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        self.namespace = "FAAdvisorAI"
    
    def publish(
        self,
        metric_name: str,
        value: float,
        unit: str = "None",
        dimensions: Dict[str, str] = None
    ):
        """Publish a metric"""
        
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': datetime.utcnow()
        }
        
        if dimensions:
            metric_data['Dimensions'] = [
                {'Name': k, 'Value': v} for k, v in dimensions.items()
            ]
        
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
        except Exception as e:
            logger.error(f"Failed to publish metric: {str(e)}")
    
    def publish_batch_metrics(self, batch_run_id: str, stats: Dict[str, Any]):
        """Publish batch run metrics"""
        
        self.publish("StocksProcessed", stats["total_stocks"], "Count")
        self.publish("FactCheckPassRate", stats["pass_rate"], "Percent")
        self.publish("BatchDuration", stats["duration_seconds"], "Seconds")
        self.publish("CostPerStock", stats["cost_per_stock"], "None")
    
    def publish_query_metrics(self, query_type: str, latency_ms: int):
        """Publish interactive query metrics"""
        
        self.publish(
            "QueryLatency",
            latency_ms,
            "Milliseconds",
            dimensions={"QueryType": query_type}
        )

# Global publisher
metrics_publisher = MetricsPublisher()
```

### Create Monitoring Dashboard Configuration

Create `infrastructure/monitoring/cloudwatch_dashboard.json`:
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["FAAdvisorAI", "StocksProcessed", {"stat": "Sum"}],
          [".", "FactCheckPassRate", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Batch Process Metrics",
        "yAxis": {
          "left": {"min": 0}
        }
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["FAAdvisorAI", "QueryLatency", {"stat": "p95", "dimensions": {"QueryType": "simple"}}],
          ["...", {"dimensions": {"QueryType": "deep"}}]
        ],
        "period": 60,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Interactive Query Latency (P95)",
        "yAxis": {
          "left": {"min": 0, "max": 10000}
        }
      }
    }
  ]
}
```

---

## Task 4.6-4.9: Production Features Summary

Due to length, here are the remaining tasks to implement:

### 4.6: Blue-Green Deployment
- **File**: `infrastructure/deployment/blue_green.tf`
- **Scripts**: `deploy_green.sh`, `shift_traffic.sh`, `rollback.sh`
- **Implementation**: ECS task definitions, ALB target groups, Route53 weighted routing

### 4.7: Comprehensive Evaluation Suite
- **Files**: `langsmith/evaluators/fact_accuracy_evaluator.py`
- **Datasets**: `regression_test_suite.json` (100 stocks with verified summaries)
- **CI Integration**: Pre-deployment evaluation pipeline

### 4.8: Production Documentation
- **Files**: 
  - `docs/DEPLOYMENT.md`
  - `docs/OPERATIONS.md`
  - `docs/ARCHITECTURE.md`
  - `runbooks/batch_failure.md`
  - `runbooks/high_latency.md`

### 4.9: Final Integration Testing
- Load testing with Locust
- Performance benchmarks
- Cost validation

## Validation Commands - Phase 4
```bash
# 1. Test scaling with 1,000 stocks
python src/batch/run_phase2_batch.py --limit 1000 --concurrency 100

# 2. Verify cost per stock < $0.40
python -c "
from dashboards.cost_dashboard import get_cost_stats
stats = get_cost_stats()
assert stats['cost_per_stock'] < 0.40
print(f'✅ Cost per stock: ${stats[\"cost_per_stock\"]:.2f}')
"

# 3. Test concurrent queries
python tests/load/test_500_concurrent_queries.py

# 4. Run A/B test
python scripts/run_ab_test.py --test medium_writer_v2 --duration 72

# 5. Verify monitoring
aws cloudwatch get-metric-statistics \
  --namespace FAAdvisorAI \
  --metric-name FactCheckPassRate \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-02T00:00:00Z \
  --period 3600 \
  --statistics Average

# 6. Test blue-green deployment
./scripts/deploy_green.sh v1.0.0
./scripts/shift_traffic.sh --green-percent 10
# Monitor for 1 hour
./scripts/shift_traffic.sh --green-percent 100

# 7. Run evaluation suite
pytest langsmith/evaluators/ -v
python scripts/run_evaluation_suite.py
```

## Success Criteria - Phase 4

- [ ] 1,000 stocks processed in < 4 hours
- [ ] Embedding cache hit rate > 60%
- [ ] Cost per stock < $0.40
- [ ] Cost per query < $0.08
- [ ] 500 concurrent FAs supported
- [ ] Query latency P95 < 10s
- [ ] Hallucination detection catches test cases
- [ ] A/B test framework operational
- [ ] CloudWatch metrics publishing
- [ ] Blue-green deployment successful
- [ ] Evaluation suite passes
- [ ] All documentation complete

## Production Checklist

- [ ] Environment variables configured
- [ ] API keys secured (AWS Secrets Manager)
- [ ] Database backups enabled
- [ ] Monitoring dashboards deployed
- [ ] Alerts configured
- [ ] Runbooks tested
- [ ] Load testing passed
- [ ] Security audit complete
- [ ] Compliance review passed
- [ ] Stakeholder sign-off

---

**End of Phase 4 Prompt**

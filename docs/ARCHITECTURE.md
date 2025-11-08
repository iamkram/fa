# FA AI System - Architecture Documentation

## System Overview

The Financial Advisor AI System is an enterprise-grade AI application that generates multi-tiered stock summaries by ingesting data from multiple sources, embedding content in vector databases, and using LangGraph workflows with Claude models.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud (Production)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐         ┌──────────────────────────────┐       │
│  │  Route53   │────────▶│   Application Load Balancer   │       │
│  │    DNS     │         │  (Blue-Green Target Groups)   │       │
│  └────────────┘         └──────────────────────────────┘       │
│                                      │                           │
│                         ┌────────────┴────────────┐             │
│                         │                         │             │
│                    ┌────▼─────┐           ┌──────▼────┐         │
│                    │   Blue   │           │   Green   │         │
│                    │ ECS Tasks│           │ ECS Tasks │         │
│                    │  (v1.0)  │           │  (v1.1)   │         │
│                    └────┬─────┘           └──────┬────┘         │
│                         │                        │              │
│  ┌──────────────────────┴────────────────────────┴─────────┐   │
│  │                  Shared Data Layer                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │ PostgreSQL   │  │  pgvector    │  │    Redis     │  │   │
│  │  │ RDS (16)     │  │  (HNSW idx)  │  │   (Cache)    │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  └──────────────────────────────────────────────────────────   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  CloudWatch Monitoring                    │  │
│  │  Logs │ Metrics │ Dashboards │ Alarms │ Tracing         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     External Dependencies                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Anthropic   │  │   OpenAI     │  │  LangSmith   │          │
│  │   Claude     │  │  Embeddings  │  │   Tracing    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │     SEC      │  │  BlueMatrix  │  │   FactSet    │          │
│  │    EDGAR     │  │   Reports    │  │ Fundamentals │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Batch Processing System

**Purpose:** Nightly processing of 1,000 stocks to generate summaries

**Technology Stack:**
- LangGraph 1.0 (Workflow orchestration)
- asyncio (Concurrent processing)
- SQLAlchemy (Database ORM)
- OpenAI embeddings (text-embedding-3-small)

**Key Workflows:**

#### Phase 1: Multi-Source Ingestion Graph

```python
# src/batch/graphs/parallel_ingestion.py
parallel_ingestion_graph:
  START
    ├──▶ edgar_ingestion_node (Fetch SEC filings)
    ├──▶ bluematrix_ingestion_node (Fetch analyst reports)
    └──▶ factset_ingestion_node (Fetch fundamentals)
         ↓
  aggregate_sources_node (Combine all data)
         ↓
    ├──▶ vectorize_edgar (Chunk + Embed + Store)
    ├──▶ vectorize_bluematrix (Chunk + Embed + Store)
    └──▶ vectorize_factset (Chunk + Embed + Store)
         ↓
  END
```

#### Phase 2: Summary Generation & Validation Graph

```python
# src/batch/graphs/phase2_with_validation.py
phase2_validation_graph:
  START → run_phase1_graph
    ↓
  hook_writer (10-word summary)
    ↓
  medium_writer (100-150 word summary)
    ↓
  expanded_writer (200-250 word summary)
    ↓
  fact_checker (3-layer hallucination detection)
    ↓
  citation_linker (Link claims to sources)
    ↓
  validation_node (Quality checks)
    ↓
  storage_node (Save to PostgreSQL)
    ↓
  END
```

**Concurrent Processing:**
- **Concurrency Level:** 100 simultaneous stocks
- **Batching Strategy:** Process in chunks of 100
- **Estimated Throughput:** 250-300 stocks/hour
- **Target SLA:** < 4 hours for 1,000 stocks

**Data Flow:**
1. Load stock tickers from database
2. For each stock (concurrent):
   - Fetch data from 3 sources in parallel
   - Chunk text into 800-char segments
   - Generate embeddings (batch of 100)
   - Store vectors in pgvector with HNSW index
   - Generate 3-tier summaries using Claude
   - Run fact-checking and validation
   - Store results with citations
3. Publish metrics to CloudWatch

---

### 2. Interactive Query System

**Purpose:** Real-time question answering about stocks

**Technology Stack:**
- FastAPI (REST API)
- LangGraph (Query routing)
- pgvector (Semantic search)
- Claude 3.5 Sonnet (Generation)

**Query Flow:**

```
User Query
    ↓
classify_intent (Determine query type)
    ↓
    ├──▶ simple_path (cached/hook summary)
    ├──▶ medium_path (vector search → Sonnet)
    └──▶ deep_path (multi-source research → Sonnet)
         ↓
guardrails (PII check, fact validation)
    ↓
response_formatter (JSON + citations)
    ↓
User Response
```

**API Endpoints:**

```python
POST /query
{
  "ticker": "AAPL",
  "question": "What were the Q4 2024 earnings?",
  "tier": "medium"  # or "hook", "expanded"
}

Response:
{
  "answer": "Apple reported Q4 2024 revenue of $94.9B...",
  "citations": [
    {"claim": "revenue of $94.9B", "source": "EDGAR 10-K", "doc_id": "..."}
  ],
  "tier": "medium",
  "processing_time_ms": 1247,
  "cost": 0.023
}
```

**Performance Targets:**
- P50 latency: < 1s
- P95 latency: < 3s
- P99 latency: < 5s
- Cost per query: < $0.08

---

### 3. Vector Store Architecture

**Technology:** PostgreSQL 16 + pgvector extension

**Collections:**

```sql
-- EDGAR Filings (10-K, 10-Q, 8-K)
CREATE TABLE edgar_filings (
  id SERIAL PRIMARY KEY,
  doc_id VARCHAR(255),
  stock_id VARCHAR(50),
  ticker VARCHAR(10),
  filing_type VARCHAR(10),
  chunk_text TEXT,
  embedding vector(1536),  -- OpenAI text-embedding-3-small
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_edgar_embedding ON edgar_filings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- BlueMatrix Reports
CREATE TABLE bluematrix_reports (
  id SERIAL PRIMARY KEY,
  report_id VARCHAR(255),
  stock_id VARCHAR(50),
  ticker VARCHAR(10),
  analyst_name VARCHAR(255),
  chunk_text TEXT,
  embedding vector(1536),
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bluematrix_embedding ON bluematrix_reports
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- FactSet Data
CREATE TABLE factset_data (
  id SERIAL PRIMARY KEY,
  data_id VARCHAR(255),
  stock_id VARCHAR(50),
  ticker VARCHAR(10),
  data_type VARCHAR(50),  -- 'price', 'fundamental', 'estimate'
  chunk_text TEXT,
  embedding vector(1536),
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_factset_embedding ON factset_data
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Index Parameters:**
- **m:** 16 (maximum connections per element)
  - Higher m = better recall, more memory
- **ef_construction:** 64 (build-time search depth)
  - Higher ef = better index quality, slower build
- **ef_search:** 40 (query-time search depth)
  - Set at query time for recall/speed tradeoff

**Search Strategy:**

```python
# Hybrid search: Vector + metadata filters
results = vector_store.similarity_search(
    query_embedding=query_vector,
    collection="bluematrix_reports",
    limit=10,
    filter={"ticker": "AAPL", "created_at": {"$gte": "2024-01-01"}}
)
```

---

### 4. LLM Integration

**Primary Model:** Claude 3.5 Sonnet (claude-3-5-sonnet-20241022)
- Context window: 200K tokens
- Pricing: $3/MTok input, $15/MTok output
- Use cases: Summary generation, fact-checking, complex queries

**Secondary Model:** Claude 3.5 Haiku (claude-3-5-haiku-20241022)
- Context window: 200K tokens
- Pricing: $0.80/MTok input, $4.00/MTok output
- Use cases: Hook summaries, simple queries, classification

**Model Router:**

```python
# src/shared/utils/model_router.py
class TaskComplexity(Enum):
    SIMPLE = "simple"      # Use Haiku (4x cheaper)
    MODERATE = "moderate"  # Use Sonnet
    COMPLEX = "complex"    # Use Sonnet (required)

task_complexity_map = {
    "hook_summary": SIMPLE,
    "medium_summary": MODERATE,
    "expanded_summary": COMPLEX,
    "fact_check": COMPLEX
}
```

**Token Usage Tracking:**

```python
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    model: str
    agent_name: str

    def calculate_cost(self) -> float:
        # Per-request cost tracking
        pricing = MODEL_PRICING[self.model]
        return (input_tokens / 1M) * pricing["input"] + \
               (output_tokens / 1M) * pricing["output"]
```

---

### 5. Quality Assurance System

#### 3-Layer Hallucination Detection

**Layer 1: Cross-Source Consistency (50% weight)**
- LLM-based validation comparing summary against all source data
- Checks for factual accuracy, numerical precision
- Identifies contradictions between sources

**Layer 2: Temporal Consistency (20% weight)**
- Compares current summary with historical summaries
- Detects anomalies in financial trends
- Flags sudden contradictory changes

**Layer 3: Uncertainty Quantification (30% weight)**
- Pattern matching for hedging language
- Detects confidence qualifiers ("possibly", "may", "unclear")
- Flags excessive uncertainty as potential hallucination signal

**Risk Levels:**
```python
class HallucinationRisk(Enum):
    LOW = "low"           # Score < 0.4 → Accept
    MEDIUM = "medium"     # Score 0.4-0.6 → Review
    HIGH = "high"         # Score 0.6-0.8 → Flag
    CRITICAL = "critical" # Score > 0.8 → Reject
```

#### Citation System

**Citation Structure:**
```python
@dataclass
class Citation:
    claim_text: str           # "Revenue grew 8% YoY"
    source_type: str          # "EDGAR", "BlueMatrix", "FactSet"
    source_id: str            # Document ID
    confidence: float         # 0.0-1.0
    page_number: Optional[int]
    quote: Optional[str]      # Exact quote from source
```

**Linkage Process:**
1. Extract claims from summary (using LLM)
2. Search vector store for supporting evidence
3. Rank results by relevance
4. Validate claim-evidence match
5. Store citation with confidence score

---

### 6. Cost Management System

**Cost Tracker:**

```python
# src/shared/utils/cost_tracker.py
class CostTracker:
    def track_usage(self, usage: TokenUsage):
        # Per-agent tracking
        self.usage_by_agent[usage.agent_name].append(usage)

        # Per-model tracking
        self.usage_by_model[usage.model].append(usage)

        # Total cost calculation
        cost = usage.calculate_cost()
        self.total_cost += cost

    def get_summary(self) -> CostSummary:
        return CostSummary(
            total_cost=self.total_cost,
            total_tokens=self.total_input_tokens + self.total_output_tokens,
            cost_by_agent={...},
            cost_by_model={...}
        )
```

**Cost Dashboard:**
- Real-time cost visualization (Streamlit)
- Historical trends (daily, weekly, monthly)
- Cost per stock / cost per query metrics
- Model usage distribution (Sonnet vs Haiku)
- Recommendations for optimization

**Budget Alerts:**
- CloudWatch alarms at 50%, 75%, 90%, 100% of monthly budget
- Automatic throttling at budget limits
- Weekly cost reports to stakeholders

---

### 7. A/B Testing Framework

**Variant Assignment:**

```python
# src/shared/utils/ab_testing.py
class ABTestManager:
    def get_variant(self, test_id: str, user_id: str) -> TestVariant:
        # Consistent hashing for stable assignment
        hash_val = md5(f"{test_id}:{user_id}").hexdigest()
        pct = (int(hash_val, 16) % 10000) / 100.0

        cumulative = 0.0
        for variant in test.variants:
            cumulative += variant.allocation_pct
            if pct < cumulative:
                return variant
```

**Test Configuration:**

```yaml
# config/ab_tests.yaml
- id: summary_tone_test
  name: "Summary Tone A/B Test"
  variants:
    - id: formal
      allocation_pct: 50
      config:
        tone: "formal and professional"
    - id: conversational
      allocation_pct: 50
      config:
        tone: "conversational and friendly"
  metrics:
    - user_satisfaction
    - click_through_rate
```

**Metrics Collection:**
- LangSmith integration for evaluation
- Custom metrics published to CloudWatch
- Statistical significance testing (Chi-square, T-test)

---

### 8. Monitoring & Observability

#### CloudWatch Integration

**Custom Metrics:**

```python
# src/shared/utils/metrics.py
class MetricsPublisher:
    def publish_batch_metric(self, ...):
        self.cloudwatch.put_metric_data(
            Namespace="FA-AI-System",
            MetricData=[
                {
                    "MetricName": "StocksProcessed",
                    "Value": stock_count,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "WorkloadType", "Value": "Batch"}]
                },
                {
                    "MetricName": "BatchSuccessRate",
                    "Value": (successful / total) * 100,
                    "Unit": "Percent"
                }
            ]
        )
```

**Dashboard Widgets:**
1. Batch Volume & Success Rate
2. Query Volume by Tier (Hook, Medium, Expanded)
3. Response Times (P50, P95, P99)
4. Error Rates by Component
5. Cost Metrics (Per Stock, Per Query)
6. Token Usage by Model
7. Guardrail Pass Rate
8. System Health (CPU, Memory, DB Connections)

#### LangSmith Integration

**Tracing:**
- Full request/response traces
- Agent decision logging
- Token usage per step
- Latency breakdown

**Evaluation:**
- Automated regression tests
- Custom evaluators (fact accuracy, citation quality, word count)
- Threshold monitoring
- Trend analysis

---

### 9. Deployment Architecture

#### Blue-Green Deployment

**Infrastructure:**
```hcl
# infrastructure/deployment/blue_green.tf

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-cluster"
}

# Blue Environment
resource "aws_ecs_service" "blue" {
  name = "${var.app_name}-blue-service"
  task_definition = aws_ecs_task_definition.blue.arn
  desired_count = 3

  load_balancer {
    target_group_arn = aws_lb_target_group.blue.arn
    container_name = "app"
    container_port = 8000
  }
}

# Green Environment
resource "aws_ecs_service" "green" {
  name = "${var.app_name}-green-service"
  task_definition = aws_ecs_task_definition.green.arn
  desired_count = 3

  load_balancer {
    target_group_arn = aws_lb_target_group.green.arn
    container_name = "app"
    container_port = 8000
  }
}

# ALB with Weighted Routing
resource "aws_lb_listener" "http" {
  default_action {
    type = "forward"
    forward {
      target_group {
        arn = aws_lb_target_group.blue.arn
        weight = var.blue_weight  # 0-100
      }
      target_group {
        arn = aws_lb_target_group.green.arn
        weight = var.green_weight  # 0-100
      }
    }
  }
}
```

**Deployment Process:**
1. Deploy new version to green (0% traffic)
2. Run smoke tests on green
3. Shift 10% traffic to green
4. Monitor for 15-30 minutes
5. Gradually increase: 25% → 50% → 100%
6. Keep blue running for quick rollback

#### Container Configuration

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY config/ ./config/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "src.interactive.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Data Models

### Stock Summary

```python
# src/shared/database/models.py
class StockSummary(Base):
    __tablename__ = "stock_summaries"

    id = Column(Integer, primary_key=True)
    stock_id = Column(String(50), nullable=False)
    ticker = Column(String(10), nullable=False, index=True)
    company_name = Column(String(255))

    # 3-tier summaries
    hook_summary = Column(Text)          # 25-50 words
    medium_summary = Column(Text)        # 100-150 words
    expanded_summary = Column(Text)      # 200-250 words

    # Validation
    fact_check_status = Column(String(20))  # passed/failed
    fact_check_details = Column(JSON)
    hallucination_risk = Column(String(20))

    # Metadata
    batch_run_id = Column(String(100), index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    citations = relationship("Citation", back_populates="summary")
```

### Citation

```python
class Citation(Base):
    __tablename__ = "citations"

    id = Column(Integer, primary_key=True)
    summary_id = Column(Integer, ForeignKey("stock_summaries.id"))

    claim_text = Column(Text, nullable=False)
    source_type = Column(String(50))  # EDGAR, BlueMatrix, FactSet
    source_id = Column(String(255))
    confidence = Column(Float)
    page_number = Column(Integer)
    exact_quote = Column(Text)

    created_at = Column(DateTime, default=func.now())

    # Relationship
    summary = relationship("StockSummary", back_populates="citations")
```

---

## Security Considerations

### API Keys Management

- **Storage:** AWS Secrets Manager
- **Rotation:** Automated 90-day rotation
- **Access:** IAM roles with least privilege

### Data Encryption

- **At Rest:** RDS encryption with KMS
- **In Transit:** TLS 1.3 for all connections
- **Secrets:** Never logged or stored in plaintext

### PII Detection

```python
# src/shared/utils/guardrails.py
def check_pii(text: str) -> List[PIIFlag]:
    # Detect SSN, credit cards, phone numbers, emails
    # Redact before logging
    # Reject queries containing PII
```

### Network Security

- VPC with private subnets for ECS tasks
- Security groups restricting ingress to ALB only
- NAT Gateway for egress to external APIs
- WAF rules for API protection

---

## Scalability Considerations

### Horizontal Scaling

**ECS Auto-Scaling:**
```hcl
resource "aws_appautoscaling_target" "ecs" {
  max_capacity = 10
  min_capacity = 3
  resource_id = "service/${var.cluster_name}/${var.service_name}"
  scalable_dimension = "ecs:service:DesiredCount"

  # Scale on CPU utilization
  target_tracking_scaling_policy {
    predefined_metric_type = "ECSServiceAverageCPUUtilization"
    target_value = 70.0
  }
}
```

**Database Scaling:**
- Read replicas for query-heavy workloads
- Connection pooling (20 connections per task)
- Database query caching

### Vertical Scaling

**Task Resources:**
```json
{
  "cpu": "2048",      // 2 vCPU
  "memory": "4096",   // 4 GB
  "ephemeral_storage": "40"  // 40 GB
}
```

**When to Scale:**
- CPU > 70% sustained → Increase task count
- Memory > 80% → Increase task memory
- DB connections > 80% pool → Increase pool size

---

## Disaster Recovery

### Backup Strategy

**Database:**
- Automated daily snapshots (7-day retention)
- Point-in-time recovery (5-minute RPO)
- Cross-region replication (production only)

**Application State:**
- Stateless containers (no local persistence)
- Configuration in S3 (versioned)
- Infrastructure as Code (Terraform state in S3)

### Recovery Procedures

**RTO (Recovery Time Objective):** 4 hours
**RPO (Recovery Point Objective):** 5 minutes

**Failure Scenarios:**

1. **Single Task Failure**
   - Auto-recovery: ECS restarts failed tasks
   - RTO: < 5 minutes

2. **Availability Zone Failure**
   - Multi-AZ deployment handles automatically
   - RTO: < 10 minutes

3. **Database Failure**
   - Automated failover to standby (Multi-AZ RDS)
   - RTO: < 15 minutes

4. **Complete Region Failure**
   - Manual failover to DR region
   - Restore from cross-region snapshot
   - RTO: 4 hours

---

## Performance Optimization

### Caching Strategy

**Embedding Cache (Redis):**
```python
# Cache embeddings for 7 days
cache_key = f"embedding:{hash(text)}"
if cached := redis.get(cache_key):
    return cached
else:
    embedding = openai.embed(text)
    redis.setex(cache_key, 604800, embedding)
    return embedding
```

**Query Result Cache:**
- Identical queries cached for 5 minutes
- LRU eviction (max 1000 entries)
- Invalidation on new batch runs

### Database Optimization

**Indexes:**
```sql
-- Critical indexes
CREATE INDEX idx_ticker ON stock_summaries(ticker);
CREATE INDEX idx_batch_run ON stock_summaries(batch_run_id);
CREATE INDEX idx_created_at ON stock_summaries(created_at DESC);

-- Vector indexes
CREATE INDEX USING hnsw (embedding vector_cosine_ops);

-- Composite indexes
CREATE INDEX idx_ticker_date ON stock_summaries(ticker, created_at DESC);
```

**Connection Pooling:**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600
)
```

---

## Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Orchestration** | LangGraph | 1.0 | Workflow management |
| **LLM** | Claude 3.5 Sonnet/Haiku | 20241022 | Text generation |
| **Embeddings** | OpenAI text-embedding-3-small | - | Vector representations |
| **Vector DB** | PostgreSQL + pgvector | 16 + 0.5.1 | Semantic search |
| **Cache** | Redis | 7.x | Embedding cache |
| **Web Framework** | FastAPI | 0.104.1 | REST API |
| **ORM** | SQLAlchemy | 2.0+ | Database ORM |
| **Container** | Docker | 20.10+ | Containerization |
| **Orchestration** | ECS Fargate | - | Container orchestration |
| **Load Balancer** | ALB | - | Traffic distribution |
| **Monitoring** | CloudWatch + LangSmith | - | Observability |
| **IaC** | Terraform | 1.5+ | Infrastructure |

---

## Future Enhancements

1. **Multi-Region Deployment**
   - Active-active in US-EAST-1 and US-WEST-2
   - GeoDNS routing for latency optimization

2. **Advanced RAG**
   - Hypothetical document embeddings
   - Multi-vector retrieval
   - Reranking with cross-encoder

3. **Fine-Tuned Models**
   - Custom Claude fine-tune for financial domain
   - Specialized embedding model

4. **Real-Time Updates**
   - WebSocket connections for streaming
   - Incremental summary updates
   - Live fact-checking

5. **Enhanced Analytics**
   - User behavior tracking
   - Sentiment analysis on queries
   - Predictive cost modeling

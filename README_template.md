# Financial Advisor AI System

Enterprise-grade AI system for generating validated stock summaries and providing real-time financial advisor support.

## Architecture

- **Batch Processing**: Nightly pipeline processing 1,000 stocks with multi-source data ingestion (EDGAR, BlueMatrix, FactSet)
- **Interactive Queries**: Real-time FA queries with deep research capabilities
- **Fact-Checking**: Zero-tolerance validation with 5 retry attempts
- **Technology**: LangGraph 1.0, PostgreSQL + pgvector, LangSmith

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- API Keys: Anthropic, OpenAI, LangSmith

### Setup

1. Clone repository:
```bash
git clone <repository-url>
cd fa-ai-system
```

2. Copy and configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Install dependencies:
```bash
pip install -e ".[dev]"
```

4. Start services:
```bash
docker-compose up -d
```

5. Initialize database:
```bash
python scripts/setup_database.py
python scripts/seed_test_data.py
```

6. Run tests:
```bash
pytest tests/ -v
```

## Development

### Project Structure
```
fa-ai-system/
├── src/
│   ├── batch/          # Batch processing pipeline
│   ├── interactive/    # Real-time query handling
│   └── shared/         # Shared utilities and models
├── tests/              # Test suite
├── prompts/            # LangSmith prompts
└── scripts/            # Setup and utility scripts
```

### Running Batch Process
```bash
# Coming in Phase 1
```

### Running Interactive Server
```bash
# Coming in Phase 3
```

## Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/shared/test_database.py -v
```

## License

Proprietary - Internal Use Only
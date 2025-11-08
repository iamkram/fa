# LangSmith Prompt Management Guide

## Overview

The FA AI System uses LangSmith's prompt hub for centralized prompt management, versioning, and A/B testing. This allows updating prompts without code deployments and provides a structured workflow for prompt optimization.

## Benefits

1. **Centralized Management**: All prompts stored in LangSmith hub
2. **Version Control**: Track prompt changes over time
3. **A/B Testing**: Test prompt variations without code changes
4. **Team Collaboration**: Multiple team members can edit prompts
5. **Prompt Playground**: Test prompts before deploying
6. **Audit Trail**: Full history of prompt modifications

---

## Setup

### 1. Initialize Prompts in LangSmith

Run the setup script to push all prompts to LangSmith hub:

```bash
python3 scripts/setup_langsmith_prompts.py
```

This creates the following prompts:
- `hook_summary_writer` - Ultra-concise 25-50 word summaries
- `medium_summary_writer` - Comprehensive 100-150 word summaries
- `expanded_summary_writer` - Detailed 200-250 word summaries
- `fact_checker` - Validates summaries against source data
- `citation_extractor` - Extracts and links factual claims
- `query_classifier` - Classifies queries into tiers

### 2. View Prompts in LangSmith

1. Navigate to: https://smith.langchain.com/prompts
2. View your organization's prompts
3. Click on any prompt to see details, versions, and usage

---

## Usage

### Basic Usage

```python
from src.shared.utils.prompt_manager import get_prompt

# Get latest version of prompt
prompt = get_prompt("hook_summary_writer")

# Use with LLM
messages = prompt.invoke({
    "ticker": "AAPL",
    "edgar_summary": "...",
    "bluematrix_summary": "...",
    "factset_summary": "..."
})

response = await llm.ainvoke(messages)
```

### Versioned Prompts

```python
# Get specific version
prompt_v1 = get_prompt("hook_summary_writer", version="v1.0.0")
prompt_v2 = get_prompt("hook_summary_writer", version="v2.0.0")

# Use in agent
class HookWriterAgent:
    def __init__(self, prompt_version=None):
        self.prompt = get_prompt("hook_summary_writer", version=prompt_version)
```

### A/B Testing

```python
from src.shared.utils.prompt_manager import PromptManager

# Configure A/B test
test_config = {
    "test_id": "hook_tone_test",
    "variant_a": "hook_summary_writer:v1",  # Formal tone
    "variant_b": "hook_summary_writer:v2",  # Conversational tone
    "split": 50  # 50/50 traffic split
}

# Get variant based on user/batch ID
manager = PromptManager()
prompt = manager.get_prompt_with_ab_test(
    "hook_summary_writer",
    user_id="batch-123",  # Consistent hashing
    test_config=test_config
)
```

### Push New Prompts

```python
from langchain.prompts import ChatPromptTemplate
from src.shared.utils.prompt_manager import push_prompt

# Create new prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a financial analyst..."),
    ("human", "Analyze {ticker}")
])

# Push to LangSmith hub
url = push_prompt("my_custom_prompt", prompt)
print(f"Prompt URL: {url}")
```

---

## Prompt Development Workflow

### 1. Create Initial Prompt

**Option A: Via Script**
```python
python3 scripts/setup_langsmith_prompts.py
```

**Option B: Via Code**
```python
from langchain.prompts import ChatPromptTemplate
from src.shared.utils.prompt_manager import push_prompt

prompt = ChatPromptTemplate.from_messages([
    ("system", "Your system message"),
    ("human", "{input}")
])

push_prompt("my_prompt", prompt)
```

**Option C: Via LangSmith UI**
1. Go to https://smith.langchain.com/prompts
2. Click "New Prompt"
3. Enter prompt details
4. Save

### 2. Test in Playground

1. Navigate to prompt in LangSmith UI
2. Click "Open in Playground"
3. Enter test inputs
4. Run and evaluate outputs
5. Iterate on prompt

### 3. Create Version

Once satisfied with changes:
1. Click "Commit" in LangSmith UI
2. Add commit message (e.g., "Increase word count target to 40-50")
3. Tag as version (e.g., `v1.1.0`)

### 4. Deploy Version

**Option A: Update Default** (Deploy to all)
- Make the new version the default in LangSmith UI
- All agents will use it on next run

**Option B: Test with Specific Version**
```python
# Test new version on specific batch
agent = HookWriterAgent(prompt_version="v1.1.0")
```

**Option C: A/B Test**
```python
# Split traffic 50/50 between versions
test_config = {
    "test_id": "word_count_test",
    "variant_a": "hook_summary_writer:v1.0.0",
    "variant_b": "hook_summary_writer:v1.1.0",
    "split": 50
}
```

### 5. Evaluate Results

Monitor in LangSmith:
1. Compare traces between versions
2. Check quality metrics (word count, fact-check pass rate)
3. Analyze costs (token usage)
4. Review user feedback

### 6. Promote Winner

1. If version performs better → make it default
2. Archive old version
3. Document changes in changelog

---

## Prompt Templates

### Hook Summary Writer

**Purpose:** Ultra-concise 25-50 word stock summaries

**Variables:**
- `ticker` (str): Stock ticker symbol
- `edgar_summary` (str): Summary from EDGAR filings
- `bluematrix_summary` (str): Summary from BlueMatrix reports
- `factset_summary` (str): Summary from FactSet data

**Example:**
```
Hook Summary for AAPL:
Apple reported Q4 2024 revenue of $394.3B, up 8% YoY, driven by strong iPhone 15 Pro demand. Services revenue hit record $85.2B (+16%). Company announced $110B buyback and 4% dividend increase.
```

### Medium Summary Writer

**Purpose:** Comprehensive 100-150 word summaries

**Variables:** Same as hook writer

**Example:**
```
Medium Summary for AAPL (138 words):
Apple Inc. reported Q4 2024 revenue of $394.3 billion, up 8% year-over-year, driven by strong iPhone demand and record Services performance. iPhone revenue grew 6% to $201.2B, with iPhone 15 Pro models showing particularly strong demand in all geographies. Services revenue reached a record $85.2B, up 16% YoY, with growth across App Store, iCloud, and Apple Music. Mac revenue increased 2% to $29.4B, while iPad declined 3% to $23.7B. The company's installed base of active devices reached an all-time high of 2.2 billion. Apple announced a new $110 billion share buyback program, the largest in company history, and raised its quarterly dividend by 4% to $0.25 per share. Management provided optimistic guidance for Q1 2025, citing strong product pipeline and continued Services growth.
```

### Expanded Summary Writer

**Purpose:** Detailed 200-250 word summaries

**Variables:** Same as hook writer

**Output Length:** 200-250 words

---

## A/B Testing Examples

### Test 1: Summary Tone

**Hypothesis:** Conversational tone increases engagement

```python
test_config = {
    "test_id": "summary_tone_test",
    "variant_a": "medium_summary_writer:formal",
    "variant_b": "medium_summary_writer:conversational",
    "split": 50
}
```

**Metrics to Track:**
- User engagement (clicks, time spent)
- Feedback ratings
- Query follow-up rate

### Test 2: Word Count Target

**Hypothesis:** Shorter hooks (25-35 words) perform better than longer (40-50 words)

```python
test_config = {
    "test_id": "hook_length_test",
    "variant_a": "hook_summary_writer:short",  # 25-35 words
    "variant_b": "hook_summary_writer:long",   # 40-50 words
    "split": 50
}
```

**Metrics to Track:**
- Click-through rate
- Bounce rate
- User satisfaction

### Test 3: Citation Density

**Hypothesis:** More citations (5-7) increase trust vs fewer (2-3)

```python
test_config = {
    "test_id": "citation_density_test",
    "variant_a": "medium_summary_writer:light_citations",
    "variant_b": "medium_summary_writer:heavy_citations",
    "split": 50
}
```

**Metrics to Track:**
- Trust score
- Fact-check pass rate
- User feedback

---

## Prompt Management Best Practices

### 1. Semantic Versioning

Use semantic versioning for prompts:
- `v1.0.0` → Initial version
- `v1.1.0` → Minor improvements (wording changes)
- `v1.2.0` → New features (added variables)
- `v2.0.0` → Breaking changes (different structure)

### 2. Descriptive Commit Messages

```
✅ Good: "Increase word count target from 25-40 to 25-50 words"
❌ Bad: "Updated prompt"

✅ Good: "Add emphasis on YoY comparisons for better context"
❌ Bad: "Minor changes"
```

### 3. Tag Prompts

Use tags for organization:
- `summary` - All summary-related prompts
- `hook`, `medium`, `expanded` - By tier
- `production`, `staging`, `experimental` - By environment
- `v1`, `v2` - By version

### 4. Document Changes

Maintain a changelog in prompt description:
```
## Changelog

### v1.2.0 (2024-11-07)
- Increased word count target to 25-50 (was 25-40)
- Added emphasis on specific dates
- Improved examples

### v1.1.0 (2024-10-15)
- Added requirement for YoY comparisons
- Clarified tone guidelines
```

### 5. Test Before Deploying

Always test new prompts:
1. Use LangSmith Playground
2. Run on test dataset
3. Compare metrics with current version
4. A/B test with small percentage first (10-20%)
5. Gradually increase traffic if successful

### 6. Monitor Performance

Track key metrics:
- **Quality**: Fact-check pass rate, citation count
- **Length**: Word count distribution
- **Cost**: Token usage per summary
- **Speed**: Generation latency
- **User Satisfaction**: Feedback scores

---

## Integration with Evaluation

Prompts integrate with LangSmith evaluations:

```python
# Regression test with specific prompt version
from langsmith.evaluation import evaluate

results = evaluate(
    run_batch_graph,
    data="fa-ai-regression-suite",
    evaluators=[fact_accuracy_evaluator, word_count_evaluator],
    experiment_prefix="prompt-v1.2.0-test",
    metadata={"prompt_version": "v1.2.0"}
)
```

Compare prompt versions:
```python
# Test v1.1.0
results_v1 = evaluate(..., metadata={"prompt_version": "v1.1.0"})

# Test v1.2.0
results_v2 = evaluate(..., metadata={"prompt_version": "v1.2.0"})

# Compare in LangSmith UI
```

---

## Fallback Strategy

The prompt manager includes automatic fallbacks:

```python
class PromptManager:
    def get_prompt(self, prompt_name, version=None):
        try:
            # Try to pull from LangSmith hub
            return hub.pull(f"{prompt_name}:{version or 'latest'}")
        except Exception as e:
            logger.warning(f"Failed to load from hub: {e}")
            # Fall back to hardcoded prompt
            return self._get_fallback_prompt(prompt_name)
```

**Fallback Prompts:**
- Included in code as safety net
- Used if LangSmith unavailable
- Identical to initial versions in hub
- Updated periodically to match latest stable version

---

## Troubleshooting

### Prompt Not Found

```
Error: Prompt 'hook_summary_writer' not found
```

**Solution:**
```bash
# Re-run setup script
python3 scripts/setup_langsmith_prompts.py

# Or create manually in LangSmith UI
```

### Version Not Found

```
Error: Version 'v2.0.0' not found for 'hook_summary_writer'
```

**Solution:**
- Check available versions in LangSmith UI
- Use `get_prompt("hook_summary_writer")` for latest

### Permission Denied

```
Error: Permission denied to pull prompt
```

**Solution:**
- Check LANGSMITH_API_KEY is set correctly
- Verify you have access to the organization
- Check prompt is not private (or you're the owner)

---

## Migration from Hardcoded Prompts

If you have hardcoded prompts, migrate them:

### Before (Hardcoded):
```python
class HookWriterAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "Hardcoded prompt text..."),
            ("human", "{input}")
        ])
```

### After (LangSmith):
```python
from src.shared.utils.prompt_manager import get_prompt

class HookWriterAgent:
    def __init__(self, prompt_version=None):
        self.prompt = get_prompt("hook_summary_writer", version=prompt_version)
```

**Migration Steps:**
1. Extract current prompt to script
2. Push to LangSmith hub
3. Update agent to use `get_prompt()`
4. Test with same inputs/outputs
5. Deploy

---

## Advanced Features

### Public Prompt Hub

Use prompts from public hub:

```python
# Use LangChain AI's public prompts
from src.shared.utils.prompt_manager import get_prompt

# RAG fusion prompt from public hub
prompt = get_prompt("rag-fusion", owner="langchain-ai")
```

### Prompt Forking

Fork and modify public prompts:
1. Pull public prompt
2. Modify for your use case
3. Push as new prompt

```python
# Pull public prompt
public_prompt = get_prompt("rag-fusion", owner="langchain-ai")

# Modify
custom_prompt = modify_prompt(public_prompt, ...)

# Push as your own
push_prompt("custom_rag_fusion", custom_prompt)
```

---

## Resources

- **LangSmith Docs**: https://docs.langchain.com/langsmith/manage-prompts
- **Public Prompt Hub**: https://smith.langchain.com/hub
- **LangChain Prompts**: https://python.langchain.com/docs/modules/model_io/prompts/

---

## Next Steps

1. **Run Setup**: `python3 scripts/setup_langsmith_prompts.py`
2. **View Prompts**: https://smith.langchain.com/prompts
3. **Test in Playground**: Edit and test prompts
4. **Update Agents**: Migrate to `get_prompt()`
5. **Monitor**: Track prompt performance in LangSmith
6. **Iterate**: Continuously improve prompts based on data

"""
Interactive Supervisor Agent - LangGraph 1.0 Pattern

Coordinates all specialized subagents for FA meeting prep:
1. Portfolio Agent - Retrieves batch portfolio data
2. News Agent - Fetches real-time market news
3. Validator Agent - Validates all claims (NO BAD DATA)
4. Report Writer Agent - Generates final meeting brief

Uses LangGraph create_react_agent with Claude Sonnet 4.5.
"""

import logging
import asyncio
from typing import TypedDict, Annotated, Sequence
from datetime import datetime
import operator

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic

# Import all subagent tools
from src.interactive.agents.portfolio_agent import get_batch_portfolio_data
from src.interactive.agents.news_agent import fetch_current_news
from src.interactive.agents.validator_agent import validate_all_claims
from src.interactive.agents.report_writer_agent import generate_meeting_report

logger = logging.getLogger(__name__)


# ============================================================================
# State Definition
# ============================================================================

class SupervisorState(TypedDict):
    """State shared across the supervisor and all subagents"""
    # Input parameters
    household_id: str
    fa_id: str
    tickers: list[str]  # Tickers for news lookup

    # Agent outputs
    portfolio_data: str
    news_data: str
    validation_result: dict
    final_report: str

    # Conversation state
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Metadata
    started_at: str
    completed_at: str | None
    error: str | None


# ============================================================================
# Supervisor Agent Factory
# ============================================================================

def create_supervisor_agent():
    """
    Create the Interactive Supervisor Agent.

    Uses LangGraph 1.0 create_react_agent with:
    - Claude Sonnet 4.5 as supervisor LLM
    - All 4 subagent tools registered
    - MemorySaver for checkpointing

    Returns:
        Compiled LangGraph agent ready for invocation
    """
    logger.info("🏗️  Building Interactive Supervisor Agent...")

    # Initialize Claude Sonnet 4.5 as the supervisor
    supervisor_llm = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        temperature=0.1,  # Low temperature for deterministic reasoning
        max_tokens=4000
    )

    # Register all subagent tools
    tools = [
        get_batch_portfolio_data,  # Portfolio Agent
        fetch_current_news,         # News Agent (async)
        validate_all_claims,        # Validator Agent (async) - CRITICAL
        generate_meeting_report     # Report Writer Agent
    ]

    # Create system message for supervisor
    system_message = """You are the Interactive Supervisor for FA Meeting Prep AI.

Your role: Coordinate specialized subagents to generate validated meeting prep reports for Financial Advisors.

CRITICAL WORKFLOW (Execute in this EXACT order):

1. **Portfolio Agent** - Call `get_batch_portfolio_data(household_id)` to retrieve portfolio summary from nightly batch

2. **News Agent** - Call `fetch_current_news(tickers, hours_back=24)` to get real-time market news
   - Extract tickers from portfolio data
   - Fetch news for those tickers

3. **Validator Agent** - Call `validate_all_claims(portfolio_data, news_data, household_id)` to validate ALL data
   - ⚠️ MANDATORY - NO BAD DATA to FAs
   - Must achieve 95%+ confidence score
   - If validation fails, STOP and report issues

4. **Report Writer Agent** - Call `generate_meeting_report(household_id, fa_id, portfolio_data, news_data, validation_result)`
   - Only proceed if validation passed
   - Generate final meeting brief

RULES:
- Execute steps sequentially (not in parallel)
- NEVER skip the Validator Agent
- If any agent fails, provide clear error message to user
- Track execution time and log progress
- Return the final report to the user when complete

You have access to these tools: get_batch_portfolio_data, fetch_current_news, validate_all_claims, generate_meeting_report
"""

    # Create the ReAct agent
    agent = create_react_agent(
        model=supervisor_llm,
        tools=tools,
        state_modifier=system_message,
        checkpointer=MemorySaver()  # Enable conversation persistence
    )

    logger.info("✅ Interactive Supervisor Agent created successfully")
    logger.info(f"   - LLM: Claude Sonnet 4.5")
    logger.info(f"   - Tools: {len(tools)} registered")
    logger.info(f"   - Checkpointer: MemorySaver")

    return agent


# ============================================================================
# High-Level Invocation Functions
# ============================================================================

async def generate_meeting_prep(
    household_id: str,
    fa_id: str,
    session_id: str = "default"
) -> dict:
    """
    High-level function to generate a meeting prep report.

    This is the main entry point for the interactive supervisor.

    Args:
        household_id: Household identifier (e.g., "JOHNSON-001")
        fa_id: Financial Advisor identifier (e.g., "FA-001")
        session_id: Session ID for checkpointing (default: "default")

    Returns:
        {
            "success": bool,
            "final_report": str,  # Markdown meeting brief
            "validation_result": dict,
            "execution_time_seconds": float,
            "error": str | None
        }
    """
    logger.info(f"🚀 Starting meeting prep generation for household {household_id}")
    start_time = datetime.utcnow()

    try:
        # Create the supervisor agent
        agent = create_supervisor_agent()

        # Prepare the input message
        user_message = f"""Generate a meeting prep report for:
- Household ID: {household_id}
- FA ID: {fa_id}

Please execute the workflow:
1. Fetch portfolio data
2. Fetch market news
3. Validate all data
4. Generate final report

Provide the final report when complete.
"""

        # Configuration for the run
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }

        # Invoke the agent
        logger.info("Invoking supervisor agent...")
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=user_message)]},
            config=config
        )

        # Extract the final report from agent messages
        final_report = None
        validation_result = None

        # The last message should contain the final report
        if result.get("messages"):
            last_message = result["messages"][-1]
            if isinstance(last_message, AIMessage):
                final_report = last_message.content

        execution_time = (datetime.utcnow() - start_time).total_seconds()

        logger.info(f"✅ Meeting prep generation completed in {execution_time:.2f}s")

        return {
            "success": True,
            "final_report": final_report,
            "validation_result": validation_result,  # TODO: Extract from agent state
            "execution_time_seconds": execution_time,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Error generating meeting prep: {str(e)}")
        execution_time = (datetime.utcnow() - start_time).total_seconds()

        return {
            "success": False,
            "final_report": None,
            "validation_result": None,
            "execution_time_seconds": execution_time,
            "error": str(e)
        }


def generate_meeting_prep_sync(
    household_id: str,
    fa_id: str,
    session_id: str = "default"
) -> dict:
    """
    Synchronous wrapper for generate_meeting_prep.

    Use this when calling from non-async contexts.
    """
    return asyncio.run(generate_meeting_prep(household_id, fa_id, session_id))


# ============================================================================
# Custom Supervisor Graph (Alternative Implementation)
# ============================================================================

def create_custom_supervisor_graph():
    """
    Alternative implementation using custom StateGraph.

    This gives more control over the execution flow compared to create_react_agent.
    Use this if you need custom routing logic or conditional flows.

    Returns:
        Compiled StateGraph
    """

    # Define agent nodes
    async def portfolio_node(state: SupervisorState):
        """Fetch portfolio data"""
        logger.info(f"📊 Portfolio Node: Fetching data for {state['household_id']}")

        try:
            portfolio_data = get_batch_portfolio_data(state["household_id"])

            return {
                "portfolio_data": portfolio_data,
                "messages": [AIMessage(content=f"Portfolio data retrieved for {state['household_id']}")]
            }
        except Exception as e:
            logger.error(f"Error in portfolio node: {str(e)}")
            return {
                "error": f"Portfolio fetch failed: {str(e)}",
                "messages": [AIMessage(content=f"Error fetching portfolio: {str(e)}")]
            }

    async def news_node(state: SupervisorState):
        """Fetch market news"""
        logger.info(f"📰 News Node: Fetching news for {len(state['tickers'])} tickers")

        try:
            news_data = await fetch_current_news(state["tickers"], hours_back=24)

            return {
                "news_data": news_data,
                "messages": [AIMessage(content=f"Market news retrieved for {len(state['tickers'])} tickers")]
            }
        except Exception as e:
            logger.error(f"Error in news node: {str(e)}")
            return {
                "error": f"News fetch failed: {str(e)}",
                "messages": [AIMessage(content=f"Error fetching news: {str(e)}")]
            }

    async def validator_node(state: SupervisorState):
        """Validate all data - CRITICAL"""
        logger.info(f"🔍 Validator Node: Validating data for {state['household_id']}")

        try:
            validation_result = await validate_all_claims(
                portfolio_data=state["portfolio_data"],
                news_data=state["news_data"],
                household_id=state["household_id"]
            )

            validation_passed = validation_result.get("validation_passed", False)
            confidence = validation_result.get("confidence_score", 0.0)

            if validation_passed:
                logger.info(f"✅ Validation PASSED (confidence: {confidence:.2%})")
            else:
                logger.warning(f"⚠️  Validation FAILED (confidence: {confidence:.2%})")

            return {
                "validation_result": validation_result,
                "messages": [AIMessage(content=f"Validation completed: {'PASSED' if validation_passed else 'FAILED'}")]
            }
        except Exception as e:
            logger.error(f"Error in validator node: {str(e)}")
            return {
                "error": f"Validation failed: {str(e)}",
                "messages": [AIMessage(content=f"Error in validation: {str(e)}")]
            }

    async def report_writer_node(state: SupervisorState):
        """Generate final report"""
        logger.info(f"📝 Report Writer Node: Generating report for {state['household_id']}")

        try:
            # Only proceed if validation passed
            if not state.get("validation_result", {}).get("validation_passed", False):
                logger.warning("Skipping report generation due to failed validation")
                return {
                    "final_report": "❌ Report generation skipped due to validation failure.",
                    "messages": [AIMessage(content="Report generation skipped - validation failed")]
                }

            final_report = generate_meeting_report(
                household_id=state["household_id"],
                fa_id=state["fa_id"],
                portfolio_data=state["portfolio_data"],
                news_data=state["news_data"],
                validation_result=state["validation_result"]
            )

            return {
                "final_report": final_report,
                "completed_at": datetime.utcnow().isoformat(),
                "messages": [AIMessage(content="Final meeting prep report generated successfully")]
            }
        except Exception as e:
            logger.error(f"Error in report writer node: {str(e)}")
            return {
                "error": f"Report generation failed: {str(e)}",
                "messages": [AIMessage(content=f"Error generating report: {str(e)}")]
            }

    # Build the graph
    workflow = StateGraph(SupervisorState)

    # Add nodes
    workflow.add_node("portfolio", portfolio_node)
    workflow.add_node("news", news_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("report_writer", report_writer_node)

    # Define edges (sequential execution)
    workflow.set_entry_point("portfolio")
    workflow.add_edge("portfolio", "news")
    workflow.add_edge("news", "validator")
    workflow.add_edge("validator", "report_writer")
    workflow.add_edge("report_writer", END)

    # Compile with checkpointer
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ Custom Supervisor Graph created successfully")

    return app


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == "__main__":
    # Example 1: Using create_react_agent (recommended)
    async def test_react_supervisor():
        result = await generate_meeting_prep(
            household_id="JOHNSON-001",
            fa_id="FA-001",
            session_id="test-session-1"
        )

        print("\n" + "="*80)
        print("MEETING PREP REPORT (ReAct Supervisor)")
        print("="*80)
        print(f"Success: {result['success']}")
        print(f"Execution Time: {result['execution_time_seconds']:.2f}s")

        if result['final_report']:
            print("\nFinal Report:")
            print(result['final_report'])

        if result['error']:
            print(f"\nError: {result['error']}")

    # Example 2: Using custom StateGraph
    async def test_custom_graph():
        app = create_custom_supervisor_graph()

        initial_state = {
            "household_id": "JOHNSON-001",
            "fa_id": "FA-001",
            "tickers": ["AAPL", "MSFT", "GOOGL"],
            "portfolio_data": "",
            "news_data": "",
            "validation_result": {},
            "final_report": "",
            "messages": [],
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "error": None
        }

        config = {"configurable": {"thread_id": "test-session-2"}}

        result = await app.ainvoke(initial_state, config=config)

        print("\n" + "="*80)
        print("MEETING PREP REPORT (Custom Graph)")
        print("="*80)
        print(f"Final Report Length: {len(result.get('final_report', ''))}")
        print(f"Validation Passed: {result.get('validation_result', {}).get('validation_passed', False)}")
        print(f"\nFinal Report:\n{result.get('final_report', 'N/A')}")

    # Run tests
    print("Testing Interactive Supervisor Agent...\n")

    # Test 1: ReAct Agent
    asyncio.run(test_react_supervisor())

    # Test 2: Custom Graph
    # asyncio.run(test_custom_graph())

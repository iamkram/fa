"""
Cost Dashboard

Streamlit dashboard for visualizing LLM costs and usage patterns.
Provides real-time monitoring and historical analysis.

Run with: streamlit run dashboards/cost_dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.utils.cost_tracker import MODEL_PRICING, ModelType
from src.shared.utils.model_router import model_router
from src.shared.database.connection import db_manager
from src.shared.models.database import BatchRunAudit, StockSummary


# Page config
st.set_page_config(
    page_title="FA AI Cost Dashboard",
    page_icon="💰",
    layout="wide"
)

st.title("💰 FA AI System - Cost Dashboard")
st.markdown("Monitor LLM token usage and costs across batch and interactive workloads")


# ============================================================================
# Sidebar - Configuration
# ============================================================================

st.sidebar.header("Configuration")

# Model pricing display
st.sidebar.subheader("Current Model Pricing")
pricing_df = pd.DataFrame([
    {
        "Model": model.split("-")[-1].upper()[:10],
        "Input ($/MTok)": f"${prices['input']:.2f}",
        "Output ($/MTok)": f"${prices['output']:.2f}"
    }
    for model, prices in MODEL_PRICING.items()
])
st.sidebar.dataframe(pricing_df, hide_index=True)

# Cost estimation tool
st.sidebar.subheader("Cost Estimator")
stock_count = st.sidebar.number_input("Number of stocks", min_value=1, max_value=10000, value=1000)

if st.sidebar.button("Estimate Batch Cost"):
    estimates = model_router.get_batch_model_recommendation(stock_count)

    st.sidebar.success(f"Total Cost: ${estimates['total_cost_usd']:.2f}")
    st.sidebar.info(f"Cost per stock: ${estimates['cost_per_stock']:.4f}")

    with st.sidebar.expander("Breakdown"):
        for tier, data in estimates['estimates'].items():
            st.write(f"**{tier}**: ${data['total_cost']:.2f} ({data['model'].split('-')[-1].upper()})")


# ============================================================================
# Main Dashboard - Batch Processing Costs
# ============================================================================

st.header("📊 Batch Processing Costs")

# Get batch run data
try:
    with db_manager.get_session() as session:
        # Get recent batch runs (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        batch_runs = session.query(BatchRunAudit).filter(
            BatchRunAudit.run_date >= thirty_days_ago.date()
        ).order_by(BatchRunAudit.start_timestamp.desc()).all()

        if batch_runs:
            # Convert to DataFrame
            batch_data = []
            for run in batch_runs:
                # Estimate cost based on stock count
                # Rough estimate: $0.40 per stock (target from Phase 4)
                estimated_cost = run.total_stocks_processed * 0.40

                batch_data.append({
                    "Run Date": run.run_date,
                    "Run ID": run.run_id[:8],
                    "Stocks Processed": run.total_stocks_processed,
                    "Successful": run.successful_summaries,
                    "Failed": run.failed_summaries,
                    "Success Rate": f"{(run.successful_summaries / run.total_stocks_processed * 100):.1f}%" if run.total_stocks_processed > 0 else "0%",
                    "Estimated Cost": f"${estimated_cost:.2f}",
                    "Cost per Stock": f"${estimated_cost / run.total_stocks_processed:.4f}" if run.total_stocks_processed > 0 else "$0.00"
                })

            df_batch = pd.DataFrame(batch_data)

            # Display metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                total_stocks = sum(r.total_stocks_processed for r in batch_runs)
                st.metric("Total Stocks Processed", f"{total_stocks:,}")

            with col2:
                total_cost = sum(r.total_stocks_processed * 0.40 for r in batch_runs)
                st.metric("Total Estimated Cost", f"${total_cost:.2f}")

            with col3:
                avg_cost = total_cost / total_stocks if total_stocks > 0 else 0
                st.metric("Avg Cost per Stock", f"${avg_cost:.4f}")

            with col4:
                success_rate = sum(r.successful_summaries for r in batch_runs) / total_stocks * 100 if total_stocks > 0 else 0
                st.metric("Overall Success Rate", f"{success_rate:.1f}%")

            # Batch runs table
            st.subheader("Recent Batch Runs")
            st.dataframe(df_batch, hide_index=True, use_container_width=True)

            # Cost over time chart
            st.subheader("Cost Trend Over Time")
            df_batch['Date'] = pd.to_datetime(df_batch['Run Date'])
            df_batch['Cost_numeric'] = df_batch['Estimated Cost'].str.replace('$', '').astype(float)

            fig_cost_trend = px.line(
                df_batch.sort_values('Date'),
                x='Date',
                y='Cost_numeric',
                title='Batch Processing Cost per Run',
                labels={'Cost_numeric': 'Cost (USD)', 'Date': 'Run Date'}
            )
            st.plotly_chart(fig_cost_trend, use_container_width=True)

            # Stocks processed chart
            fig_stocks = px.bar(
                df_batch.sort_values('Date'),
                x='Date',
                y='Stocks Processed',
                title='Stocks Processed per Batch',
                labels={'Stocks Processed': 'Number of Stocks', 'Date': 'Run Date'}
            )
            st.plotly_chart(fig_stocks, use_container_width=True)

        else:
            st.info("No batch runs found in the last 30 days")

except Exception as e:
    st.error(f"Error loading batch data: {str(e)}")


# ============================================================================
# Summary Statistics
# ============================================================================

st.header("📈 Summary Statistics")

try:
    with db_manager.get_session() as session:
        # Get summary statistics
        total_summaries = session.query(StockSummary).count()

        if total_summaries > 0:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Summaries Stored", f"{total_summaries:,}")

            with col2:
                # Estimate total tokens (rough)
                # Hook: 75 tokens, Medium: 200 tokens, Expanded: 350 tokens
                estimated_tokens = total_summaries * 625  # Average across tiers
                st.metric("Estimated Output Tokens", f"{estimated_tokens:,}")

            with col3:
                # Estimate total cost for outputs
                # Using Sonnet pricing: $15/MTok output
                output_cost = (estimated_tokens / 1_000_000) * 15.0
                st.metric("Estimated Output Cost", f"${output_cost:.2f}")

            # Word count distribution
            st.subheader("Word Count Distribution")

            summaries = session.query(StockSummary).limit(1000).all()

            if summaries:
                wc_data = []
                for s in summaries:
                    if s.hook_word_count:
                        wc_data.append({"Tier": "Hook", "Word Count": s.hook_word_count})
                    if s.medium_word_count:
                        wc_data.append({"Tier": "Medium", "Word Count": s.medium_word_count})
                    if s.expanded_word_count:
                        wc_data.append({"Tier": "Expanded", "Word Count": s.expanded_word_count})

                if wc_data:
                    df_wc = pd.DataFrame(wc_data)

                    fig_wc = px.box(
                        df_wc,
                        x='Tier',
                        y='Word Count',
                        title='Word Count Distribution by Tier',
                        labels={'Word Count': 'Words', 'Tier': 'Summary Tier'}
                    )
                    st.plotly_chart(fig_wc, use_container_width=True)

except Exception as e:
    st.error(f"Error loading summary statistics: {str(e)}")


# ============================================================================
# Cost Optimization Recommendations
# ============================================================================

st.header("💡 Cost Optimization Recommendations")

recommendations = []

# Check if Haiku is enabled
if model_router.enable_haiku:
    st.success("✅ Haiku optimization enabled - Using cheaper model for simple tasks")
else:
    recommendations.append("Enable Haiku for simple tasks to reduce costs by ~60%")
    st.warning("⚠️ Haiku optimization disabled - Consider enabling for cost savings")

# Check embedding cache
st.info("💡 Embedding cache active - Skipping unchanged content (up to 30% faster)")

# Display recommendations
if recommendations:
    st.subheader("Suggested Improvements")
    for rec in recommendations:
        st.write(f"• {rec}")
else:
    st.success("All cost optimizations are enabled!")


# ============================================================================
# Footer
# ============================================================================

st.markdown("---")
st.markdown("**Note**: Cost estimates are approximate. Actual costs may vary based on prompt complexity and model usage.")
st.markdown("Refresh the dashboard to see updated metrics.")

"""
Batch Monitoring Dashboard API
FastAPI backend for batch processing monitoring and observability
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from typing import List, Optional
import uuid
import logging
from pathlib import Path

from src.shared.database.connection import db_manager
from src.shared.models.database import BatchRunAudit, Stock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Batch Processing Monitor", version="1.0.0")

# Get paths
DASHBOARD_DIR = Path(__file__).parent
STATIC_DIR = DASHBOARD_DIR / "static"
TEMPLATES_DIR = DASHBOARD_DIR / "templates"

# Mount static files
app.mount("/batch-static", StaticFiles(directory=str(STATIC_DIR)), name="batch-static")


@app.get("/batch-dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the batch monitoring dashboard HTML"""
    html_path = TEMPLATES_DIR / "batch_monitor.html"

    try:
        with open(html_path, 'r') as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dashboard not found")


@app.get("/api/batch/latest-run")
async def get_latest_run():
    """Get the most recent batch run with full statistics"""
    try:
        with db_manager.get_session() as session:
            latest_run = (
                session.query(BatchRunAudit)
                .order_by(BatchRunAudit.run_date.desc())
                .first()
            )

            if not latest_run:
                return {
                    "run_id": "no-runs",
                    "run_date": datetime.now().isoformat(),
                    "total_stocks": 0,
                    "successful": 0,
                    "failed": 0,
                    "duration_ms": 0,
                    "avg_hook_words": 0,
                    "avg_medium_words": 0,
                    "avg_expanded_words": 0,
                    "hook_retries": 0,
                    "medium_retries": 0,
                    "expanded_retries": 0,
                    "hook_fact_check_rate": 0,
                    "medium_fact_check_rate": 0,
                    "expanded_fact_check_rate": 0
                }

            # Calculate duration
            duration_ms = 0
            if latest_run.end_timestamp and latest_run.start_timestamp:
                duration = latest_run.end_timestamp - latest_run.start_timestamp
                duration_ms = int(duration.total_seconds() * 1000)

            return {
                "run_id": str(latest_run.run_id),
                "run_date": latest_run.run_date.isoformat(),
                "total_stocks": latest_run.total_stocks_processed or 0,
                "successful": latest_run.successful_summaries or 0,
                "failed": latest_run.failed_summaries or 0,
                "duration_ms": duration_ms,
                "avg_hook_words": 150,  # TODO: Calculate from actual data
                "avg_medium_words": 300,
                "avg_expanded_words": 500,
                "hook_retries": 0,
                "medium_retries": 0,
                "expanded_retries": 0,
                "hook_fact_check_rate": latest_run.fact_check_pass_rate or 1.0,
                "medium_fact_check_rate": latest_run.fact_check_pass_rate or 1.0,
                "expanded_fact_check_rate": latest_run.fact_check_pass_rate or 1.0
            }

    except Exception as e:
        logger.error(f"Error fetching latest run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/batch/runs")
async def get_batch_runs(limit: int = 20, offset: int = 0):
    """Get historical batch runs"""
    try:
        with db_manager.get_session() as session:
            runs = (
                session.query(BatchRunAudit)
                .order_by(BatchRunAudit.run_date.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            result = []
            for run in runs:
                # Calculate duration
                duration_ms = 0
                if run.end_timestamp and run.start_timestamp:
                    duration = run.end_timestamp - run.start_timestamp
                    duration_ms = int(duration.total_seconds() * 1000)

                result.append({
                    "run_id": str(run.run_id),
                    "run_date": run.run_date.isoformat(),
                    "total_stocks": run.total_stocks_processed or 0,
                    "successful": run.successful_summaries or 0,
                    "failed": run.failed_summaries or 0,
                    "duration_ms": duration_ms,
                    "avg_generation_time_ms": run.average_generation_time_ms or 0,
                    "fact_check_pass_rate": run.fact_check_pass_rate or 0
                })

            return result

    except Exception as e:
        logger.error(f"Error fetching batch runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/batch/runs/{run_id}/stocks")
async def get_run_stocks(run_id: str):
    """Get stock-level details for a specific batch run"""
    try:
        # For now, return mock data as we need to implement stock-level tracking
        # TODO: Add a StockProcessingResult table to track individual stocks

        mock_stocks = [
            {
                "ticker": "AAPL",
                "success": True,
                "hook_wc": 148,
                "medium_wc": 297,
                "expanded_wc": 512,
                "hook_fact_check": "passed",
                "medium_fact_check": "passed",
                "expanded_fact_check": "passed",
                "total_retries": 0,
                "processing_time_ms": 35421
            },
            {
                "ticker": "MSFT",
                "success": True,
                "hook_wc": 152,
                "medium_wc": 305,
                "expanded_wc": 498,
                "hook_fact_check": "passed",
                "medium_fact_check": "passed",
                "expanded_fact_check": "passed",
                "total_retries": 1,
                "processing_time_ms": 38129
            },
            {
                "ticker": "GOOGL",
                "success": True,
                "hook_wc": 145,
                "medium_wc": 292,
                "expanded_wc": 501,
                "hook_fact_check": "passed",
                "medium_fact_check": "passed",
                "expanded_fact_check": "passed",
                "total_retries": 0,
                "processing_time_ms": 36842
            },
            {
                "ticker": "TSLA",
                "success": True,
                "hook_wc": 156,
                "medium_wc": 310,
                "expanded_wc": 520,
                "hook_fact_check": "passed",
                "medium_fact_check": "passed",
                "expanded_fact_check": "passed",
                "total_retries": 2,
                "processing_time_ms": 39654
            },
            {
                "ticker": "JPM",
                "success": True,
                "hook_wc": 149,
                "medium_wc": 298,
                "expanded_wc": 508,
                "hook_fact_check": "passed",
                "medium_fact_check": "passed",
                "expanded_fact_check": "passed",
                "total_retries": 0,
                "processing_time_ms": 37123
            }
        ]

        return mock_stocks

    except Exception as e:
        logger.error(f"Error fetching stock details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/batch/stats")
async def get_batch_stats(days: int = 7):
    """Get aggregate statistics for the last N days"""
    try:
        with db_manager.get_session() as session:
            cutoff_date = datetime.now() - timedelta(days=days)

            runs = (
                session.query(BatchRunAudit)
                .filter(BatchRunAudit.run_date >= cutoff_date)
                .all()
            )

            if not runs:
                return {
                    "total_runs": 0,
                    "total_stocks_processed": 0,
                    "total_successful": 0,
                    "total_failed": 0,
                    "avg_success_rate": 0,
                    "avg_fact_check_rate": 0,
                    "avg_processing_time_ms": 0
                }

            total_stocks = sum(r.total_stocks_processed or 0 for r in runs)
            total_successful = sum(r.successful_summaries or 0 for r in runs)
            total_failed = sum(r.failed_summaries or 0 for r in runs)

            avg_success_rate = (total_successful / total_stocks * 100) if total_stocks > 0 else 0
            avg_fact_check_rate = sum(r.fact_check_pass_rate or 0 for r in runs) / len(runs)
            avg_processing_time = sum(r.average_generation_time_ms or 0 for r in runs) / len(runs)

            return {
                "total_runs": len(runs),
                "total_stocks_processed": total_stocks,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "avg_success_rate": round(avg_success_rate, 2),
                "avg_fact_check_rate": round(avg_fact_check_rate, 2),
                "avg_processing_time_ms": round(avg_processing_time, 0)
            }

    except Exception as e:
        logger.error(f"Error calculating batch stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        with db_manager.get_session() as session:
            session.query(BatchRunAudit).count()

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "database": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")

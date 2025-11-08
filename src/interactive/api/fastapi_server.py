"""
FastAPI Server for Interactive Queries

Provides REST API and WebSocket endpoints for real-time FA queries.
"""

import os
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# IMPORTANT: Set LangSmith environment variables BEFORE importing LangChain components
from src.config.settings import settings
os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langsmith_tracing_v2)
os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

# Now import LangChain-dependent modules
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from src.interactive.graphs.interactive_graph import interactive_graph
from src.interactive.state import InteractiveGraphState
from src.shared.utils.redis_client import redis_session_manager
from src.shared.monitoring.guardrail_metrics import guardrail_metrics
from src.interactive.api.middleware import MaintenanceModeMiddleware
from src.shared.utils.system_status import system_status_manager
from src.shared.utils.load_test_orchestrator import (
    load_test_orchestrator,
    LoadTestConfig
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"LangSmith tracing enabled: {settings.langsmith_tracing_v2}")
logger.info(f"LangSmith project: {settings.langsmith_project}")

# Create FastAPI app
app = FastAPI(
    title="FA AI System - Interactive API",
    description="Real-time query system for Financial Advisors",
    version="3.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Maintenance mode middleware (kill switch)
app.add_middleware(MaintenanceModeMiddleware)


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Interactive query request"""
    fa_id: str
    session_id: str
    query_text: str
    query_type: str = "chat"
    context: Dict[str, Any] = {}


class QueryResponse(BaseModel):
    """Interactive query response"""
    query_id: str
    response_text: str
    response_tier: Optional[str] = None
    processing_time_ms: int
    guardrail_status: str
    citations: list = []
    pii_flags: list = []
    run_id: Optional[str] = None  # LangSmith run ID for feedback


class KillSwitchRequest(BaseModel):
    """Kill switch toggle request"""
    enabled: bool
    reason: str
    initiated_by: str = "admin"
    message: Optional[str] = None
    expected_restoration: Optional[str] = None


class LoadTestRequest(BaseModel):
    """Load test execution request"""
    test_name: str
    concurrent_users: int
    total_requests: int
    duration_seconds: Optional[int] = None
    query_type: str = "chat"
    initiated_by: str = "admin"


# ============================================================================
# LangSmith Traced Graph Invocation
# ============================================================================

@traceable(name="Interactive Query Graph", run_type="chain")
async def run_interactive_graph(input_state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> tuple[Dict[str, Any], Optional[str]]:
    """Wrapper to ensure LangSmith tracing for graph execution"""
    # Create config with LangSmith metadata
    if config is None:
        config = {}

    # Add LangSmith run name and tags
    config = {
        **config,
        "run_name": "Interactive Query Graph",
        "tags": ["interactive", "fa-query", input_state.get("fa_id", "unknown")],
        "metadata": {
            "query_text": input_state.get("query_text", "")[:100],
            "query_type": input_state.get("query_type", "chat"),
            "session_id": input_state.get("session_id", ""),
        }
    }

    result = await interactive_graph.ainvoke(input_state, config=config)

    # Capture LangSmith run ID
    langsmith_run_id = None
    try:
        current_run = get_current_run_tree()
        if current_run:
            langsmith_run_id = str(current_run.id)
    except Exception as e:
        logger.warning(f"Could not capture LangSmith run ID: {e}")

    return result, langsmith_run_id


# ============================================================================
# REST Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Health check"""
    return {
        "service": "FA AI System - Interactive API",
        "version": "3.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Metrics API Endpoints
# ============================================================================

@app.get("/metrics/session/{session_id}")
async def get_session_metrics(session_id: str):
    """
    Get guardrail metrics for a specific session

    Returns:
        Session-level metrics including:
        - Total queries processed
        - Input/output guardrail trigger counts
        - Fact verification flags
        - LLM validation usage
        - Average confidence scores
        - Total processing time

    Example:
        GET /metrics/session/test-session-123
    """
    try:
        summary = guardrail_metrics.get_session_summary(session_id)
        return {
            "status": "success",
            "session_id": session_id,
            "metrics": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to retrieve session metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")


@app.get("/metrics/guardrails")
async def get_guardrails_metrics():
    """
    Get aggregated guardrail statistics across all sessions

    Returns:
        System-wide guardrail metrics including:
        - Total sessions tracked
        - Aggregated trigger counts
        - Average performance metrics

    Example:
        GET /metrics/guardrails
    """
    try:
        # Get all session metrics
        all_sessions = list(guardrail_metrics._session_metrics.keys())

        if not all_sessions:
            return {
                "status": "success",
                "message": "No metrics data available",
                "total_sessions": 0,
                "timestamp": datetime.utcnow().isoformat()
            }

        # Aggregate metrics across all sessions
        total_queries = 0
        total_input_blocks = 0
        total_output_flags = 0
        total_fact_flags = 0
        total_llm_validations = 0
        all_confidence_scores = []
        total_processing_time = 0

        for session_id in all_sessions:
            summary = guardrail_metrics.get_session_summary(session_id)
            if summary.get("no_data"):
                continue

            total_queries += summary.get("queries_processed", 0)
            total_input_blocks += summary.get("input_blocks", 0)
            total_output_flags += summary.get("output_flags", 0)
            total_fact_flags += summary.get("fact_verification_flags", 0)
            total_llm_validations += summary.get("llm_validations_total", 0)
            total_processing_time += summary.get("total_processing_time_ms", 0)

            # Collect confidence scores
            session_metrics = guardrail_metrics._session_metrics.get(session_id, {})
            confidence_scores = session_metrics.get("confidence_scores", [])
            all_confidence_scores.extend(confidence_scores)

        avg_confidence = sum(all_confidence_scores) / len(all_confidence_scores) if all_confidence_scores else 0.0
        avg_processing_time = total_processing_time // total_queries if total_queries > 0 else 0

        return {
            "status": "success",
            "total_sessions": len(all_sessions),
            "aggregated_metrics": {
                "total_queries_processed": total_queries,
                "total_input_blocks": total_input_blocks,
                "total_output_flags": total_output_flags,
                "total_fact_verification_flags": total_fact_flags,
                "total_llm_validations": total_llm_validations,
                "average_confidence_score": round(avg_confidence, 3),
                "total_processing_time_ms": total_processing_time,
                "average_processing_time_ms": avg_processing_time
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to retrieve guardrails metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")


# ============================================================================
# Admin API Endpoints (Kill Switch & System Management)
# ============================================================================

@app.get("/admin/status")
async def get_system_status():
    """
    Get current system status

    Returns:
        Current operational status including:
        - System status (active/maintenance/degraded)
        - Enabled flag
        - Reason for current status
        - Maintenance message (if any)
        - Expected restoration time (if set)

    Example:
        GET /admin/status
    """
    try:
        status = system_status_manager.get_status()
        return {
            "status": status.status,
            "enabled": status.enabled,
            "reason": status.reason,
            "initiated_by": status.initiated_by,
            "initiated_at": status.initiated_at.isoformat(),
            "maintenance_message": status.maintenance_message,
            "expected_restoration": status.expected_restoration.isoformat() if status.expected_restoration else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")


@app.post("/admin/kill-switch")
async def toggle_kill_switch(request: KillSwitchRequest):
    """
    Toggle maintenance mode (kill switch)

    Activates or deactivates system-wide maintenance mode. When enabled,
    all non-admin requests will be blocked with a 503 error.

    Args:
        enabled: True to enable maintenance mode, False to reactivate system
        reason: Required explanation for the status change
        initiated_by: User or system initiating the change (default: "admin")
        message: Optional user-facing maintenance message
        expected_restoration: Optional ISO datetime when service will be restored

    Example:
        POST /admin/kill-switch
        {
            "enabled": true,
            "reason": "Emergency database maintenance",
            "initiated_by": "admin@example.com",
            "message": "System will be back online in 30 minutes",
            "expected_restoration": "2025-11-08T17:00:00Z"
        }
    """
    try:
        logger.warning(f"Kill switch toggled: enabled={request.enabled}, reason={request.reason}, by={request.initiated_by}")

        restoration = None
        if request.expected_restoration:
            try:
                # Handle both Z suffix and +00:00 timezone format
                restoration = datetime.fromisoformat(request.expected_restoration.replace('Z', '+00:00'))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid expected_restoration format: {str(e)}")

        status = system_status_manager.set_maintenance_mode(
            enabled=request.enabled,
            reason=request.reason,
            initiated_by=request.initiated_by,
            message=request.message,
            expected_restoration=restoration
        )

        return {
            "success": True,
            "message": "Maintenance mode activated" if request.enabled else "System reactivated",
            "status": {
                "status": status.status,
                "enabled": status.enabled,
                "reason": status.reason,
                "initiated_by": status.initiated_by,
                "initiated_at": status.initiated_at.isoformat(),
                "maintenance_message": status.maintenance_message,
                "expected_restoration": status.expected_restoration.isoformat() if status.expected_restoration else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle kill switch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle kill switch: {str(e)}")


@app.get("/admin/audit-history")
async def get_audit_history(limit: int = 50):
    """
    Get audit history of system status changes

    Args:
        limit: Maximum number of records to return (default: 50, max: 200)

    Returns:
        List of audit records with timestamps and details

    Example:
        GET /admin/audit-history?limit=20
    """
    try:
        if limit > 200:
            limit = 200

        history = system_status_manager.get_audit_history(limit=limit)
        return {
            "success": True,
            "count": len(history),
            "audit_trail": history,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get audit history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit history: {str(e)}")


# ============================================================================
# Load Test Endpoints
# ============================================================================

@app.post("/load-test/start")
async def start_load_test(request: LoadTestRequest):
    """Start a new load test run"""
    try:
        config = LoadTestConfig(
            test_name=request.test_name,
            concurrent_users=request.concurrent_users,
            total_requests=request.total_requests,
            duration_seconds=request.duration_seconds,
            query_type=request.query_type,
            initiated_by=request.initiated_by
        )

        run_id = await load_test_orchestrator.start_load_test(config)

        return {
            "success": True,
            "run_id": run_id,
            "message": f"Load test '{request.test_name}' started",
            "config": {
                "concurrent_users": request.concurrent_users,
                "total_requests": request.total_requests
            }
        }
    except Exception as e:
        logger.error(f"Failed to start load test: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start load test: {str(e)}")


@app.get("/load-test/runs")
async def list_load_test_runs(limit: int = 20):
    """List recent load test runs"""
    try:
        runs = load_test_orchestrator.list_runs(limit=limit)
        return {
            "success": True,
            "count": len(runs),
            "runs": runs
        }
    except Exception as e:
        logger.error(f"Failed to list load test runs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list runs: {str(e)}")


@app.get("/load-test/runs/{run_id}")
async def get_load_test_run(run_id: int):
    """Get detailed status of a specific load test run"""
    try:
        status = load_test_orchestrator.get_run_status(run_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        return {
            "success": True,
            "run": status
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get load test run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get run: {str(e)}")


@app.post("/load-test/runs/{run_id}/stop")
async def stop_load_test_run(run_id: int):
    """Stop a running load test"""
    try:
        await load_test_orchestrator.stop_load_test(run_id)
        return {
            "success": True,
            "message": f"Load test {run_id} stopped"
        }
    except Exception as e:
        logger.error(f"Failed to stop load test {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop run: {str(e)}")


@app.get("/load-test/runs/{run_id}/failures")
async def get_load_test_failures(run_id: int, limit: int = 50):
    """Get failed requests for a load test run with LangSmith trace URLs"""
    try:
        from sqlalchemy import text
        from src.shared.database.connection import db_manager

        with db_manager.get_session() as session:
            results = session.execute(
                text("""
                    SELECT fa_id, query_text, error_message, langsmith_url,
                           response_time_ms, sent_at, status_code
                    FROM load_test_requests
                    WHERE run_id = :run_id AND success = FALSE
                    ORDER BY sent_at DESC
                    LIMIT :limit
                """),
                {"run_id": run_id, "limit": limit}
            ).fetchall()

            failures = [
                {
                    "fa_id": r.fa_id,
                    "query_text": r.query_text,
                    "error_message": r.error_message,
                    "langsmith_url": r.langsmith_url,
                    "response_time_ms": r.response_time_ms,
                    "status_code": r.status_code,
                    "sent_at": r.sent_at.isoformat() if r.sent_at else None
                }
                for r in results
            ]

            # Group by error type
            error_summary = {}
            for failure in failures:
                error_type = failure.get("error_message", "Unknown error")[:100]
                if error_type not in error_summary:
                    error_summary[error_type] = {
                        "count": 0,
                        "example_langsmith_url": failure.get("langsmith_url")
                    }
                error_summary[error_type]["count"] += 1

            return {
                "success": True,
                "run_id": run_id,
                "total_failures": len(failures),
                "failures": failures,
                "error_summary": [
                    {
                        "error_type": k,
                        "count": v["count"],
                        "example_langsmith_url": v["example_langsmith_url"]
                    }
                    for k, v in error_summary.items()
                ]
            }
    except Exception as e:
        logger.error(f"Failed to get failures for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get failures: {str(e)}")


@app.websocket("/load-test/ws/{run_id}")
async def load_test_websocket(websocket: WebSocket, run_id: int):
    """WebSocket endpoint for real-time load test metrics"""
    await websocket.accept()
    logger.info(f"Load test WebSocket connected for run {run_id}")

    try:
        # Register progress callback
        async def send_progress(data: Dict[str, Any]):
            try:
                await websocket.send_json({
                    "type": "progress",
                    "run_id": run_id,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to send progress update: {e}")

        # Add callback to orchestrator
        if run_id not in load_test_orchestrator.progress_callbacks:
            load_test_orchestrator.progress_callbacks[run_id] = []
        load_test_orchestrator.progress_callbacks[run_id].append(send_progress)

        # Send initial status
        status = load_test_orchestrator.get_run_status(run_id)
        if status:
            await websocket.send_json({
                "type": "status",
                "run_id": run_id,
                "data": status,
                "timestamp": datetime.utcnow().isoformat()
            })

        # Keep connection alive
        while True:
            try:
                # Wait for messages (like stop commands)
                data = await websocket.receive_json()
                if data.get("action") == "stop":
                    await load_test_orchestrator.stop_load_test(run_id)
            except Exception:
                break

    except WebSocketDisconnect:
        logger.info(f"Load test WebSocket disconnected for run {run_id}")
    except Exception as e:
        logger.error(f"Load test WebSocket error: {e}")
    finally:
        # Cleanup callback
        if run_id in load_test_orchestrator.progress_callbacks:
            if send_progress in load_test_orchestrator.progress_callbacks[run_id]:
                load_test_orchestrator.progress_callbacks[run_id].remove(send_progress)


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a synchronous query

    Example:
    POST /query
    {
        "fa_id": "FA-001",
        "session_id": "session-123",
        "query_text": "What's the latest on AAPL?",
        "query_type": "chat"
    }
    """
    logger.info(f"Processing query for FA {request.fa_id}: {request.query_text[:50]}...")

    try:
        # Create input state with auto-generated query_id
        input_state = InteractiveGraphState(
            query_id=str(uuid.uuid4()),
            fa_id=request.fa_id,
            session_id=request.session_id,
            query_text=request.query_text,
            query_type=request.query_type,
            context=request.context
        )

        # Run the graph with LangSmith tracing
        result, langsmith_run_id = await run_interactive_graph(input_state.model_dump())

        # Store conversation turn in Redis
        try:
            redis_session_manager.store_conversation_turn(
                session_id=request.session_id,
                role="user",
                content=request.query_text,
                timestamp=datetime.utcnow().isoformat()
            )
            redis_session_manager.store_conversation_turn(
                session_id=request.session_id,
                role="assistant",
                content=result.get("response_text", ""),
                timestamp=datetime.utcnow().isoformat()
            )
        except Exception as e:
            logger.warning(f"Failed to store conversation: {e}")

        # Build response
        return QueryResponse(
            query_id=result.get("query_id", "unknown"),
            response_text=result.get("response_text", "No response generated"),
            response_tier=result.get("response_tier"),
            processing_time_ms=result.get("total_processing_time_ms", 0),
            guardrail_status=result.get("guardrail_status", "unknown"),
            citations=result.get("citations", []),
            pii_flags=result.get("pii_flags", []),
            run_id=langsmith_run_id  # Include LangSmith run ID for feedback
        )

    except Exception as e:
        logger.error(f"Query processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


# ============================================================================
# WebSocket Endpoint (for streaming responses)
# ============================================================================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming responses

    Connect to: ws://localhost:8000/ws/session-123
    Send: {"fa_id": "FA-001", "query_text": "What's happening with AAPL?"}
    Receive: Streaming response chunks
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established: {session_id}")

    try:
        while True:
            # Receive query
            data = await websocket.receive_json()

            fa_id = data.get("fa_id")
            query_text = data.get("query_text")
            query_type = data.get("query_type", "chat")
            context = data.get("context", {})

            logger.info(f"WebSocket query from {fa_id}: {query_text[:50]}...")

            # Send acknowledgment
            await websocket.send_json({
                "type": "status",
                "message": "Processing your query..."
            })

            # Create input state with auto-generated query_id
            input_state = InteractiveGraphState(
                query_id=str(uuid.uuid4()),
                fa_id=fa_id,
                session_id=session_id,
                query_text=query_text,
                query_type=query_type,
                context=context
            )

            # Run the graph with LangSmith tracing
            result, langsmith_run_id = await run_interactive_graph(input_state.model_dump())

            # Send response
            await websocket.send_json({
                "type": "response",
                "query_id": result.get("query_id"),
                "response_text": result.get("response_text"),
                "response_tier": result.get("response_tier"),
                "processing_time_ms": result.get("total_processing_time_ms"),
                "guardrail_status": result.get("guardrail_status"),
                "run_id": langsmith_run_id
            })

            # Store in Redis
            try:
                redis_session_manager.store_conversation_turn(
                    session_id=session_id,
                    role="user",
                    content=query_text,
                    timestamp=datetime.utcnow().isoformat()
                )
                redis_session_manager.store_conversation_turn(
                    session_id=session_id,
                    role="assistant",
                    content=result.get("response_text", ""),
                    timestamp=datetime.utcnow().isoformat()
                )
            except Exception as e:
                logger.warning(f"Failed to store conversation: {e}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": f"Error processing query: {str(e)}"
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

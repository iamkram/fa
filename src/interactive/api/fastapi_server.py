"""
FastAPI Server for Interactive Queries

Provides REST API and WebSocket endpoints for real-time FA queries.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime
import os

from src.config.settings import settings
from src.interactive.graphs.interactive_graph import interactive_graph
from src.interactive.state import InteractiveGraphState
from src.shared.utils.redis_client import redis_session_manager

# Set LangSmith environment variables for tracing
os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langsmith_tracing_v2)
os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

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
        # Create input state
        input_state = InteractiveGraphState(
            query_id="",  # Will be auto-generated
            fa_id=request.fa_id,
            session_id=request.session_id,
            query_text=request.query_text,
            query_type=request.query_type,
            context=request.context
        )

        # Run the graph
        result = await interactive_graph.ainvoke(input_state.model_dump())

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
            pii_flags=result.get("pii_flags", [])
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

            # Create input state
            input_state = InteractiveGraphState(
                query_id="",
                fa_id=fa_id,
                session_id=session_id,
                query_text=query_text,
                query_type=query_type,
                context=context
            )

            # Run the graph
            result = await interactive_graph.ainvoke(input_state.model_dump())

            # Send response
            await websocket.send_json({
                "type": "response",
                "query_id": result.get("query_id"),
                "response_text": result.get("response_text"),
                "response_tier": result.get("response_tier"),
                "processing_time_ms": result.get("total_processing_time_ms"),
                "guardrail_status": result.get("guardrail_status")
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

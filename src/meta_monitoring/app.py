"""FastAPI application for meta-monitoring dashboard and API"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging

from src.meta_monitoring.api.routes import router as api_router
from src.meta_monitoring.dashboard.dashboard_routes import router as dashboard_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FA AI Meta-Monitoring System",
    description="Self-improving AI system with meta-monitoring dashboard",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for dashboard
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")
app.mount("/dashboard-static", StaticFiles(directory=os.path.join(DASHBOARD_DIR, "static")), name="dashboard-static")

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(dashboard_router)


@app.get("/")
async def root():
    """Root endpoint - redirect to dashboard"""
    return {
        "message": "FA AI Meta-Monitoring System",
        "dashboard_url": "/dashboard/",
        "api_docs": "/docs",
        "health": "/api/meta-monitoring/health"
    }


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "meta-monitoring"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

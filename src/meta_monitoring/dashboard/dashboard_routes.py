"""FastAPI routes for serving the meta-monitoring dashboard"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os

# Get the directory of this file
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize templates
templates = Jinja2Templates(directory=os.path.join(DASHBOARD_DIR, "templates"))

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_overview(request: Request):
    """Render the overview dashboard page"""
    return templates.TemplateResponse("overview.html", {"request": request})


@router.get("/alerts", response_class=HTMLResponse)
async def dashboard_alerts(request: Request):
    """Render the alerts page"""
    return templates.TemplateResponse("alerts.html", {"request": request})


@router.get("/proposals", response_class=HTMLResponse)
async def dashboard_proposals(request: Request):
    """Render the proposals page"""
    return templates.TemplateResponse("proposals.html", {"request": request})


@router.get("/metrics", response_class=HTMLResponse)
async def dashboard_metrics(request: Request):
    """Render the metrics & trends page"""
    return templates.TemplateResponse("metrics.html", {"request": request})


@router.get("/controls", response_class=HTMLResponse)
async def dashboard_controls(request: Request):
    """Render the manual controls page"""
    return templates.TemplateResponse("controls.html", {"request": request})

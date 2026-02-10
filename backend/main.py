"""SynTera Test Suite - FastAPI Backend"""
import os
import sys

# Project root (parent of backend/) so "config", "backend", "database" resolve when running python backend/main.py
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Load .env from project root
_env_file = os.path.join(_project_root, ".env")
if os.path.isfile(_env_file):
    from dotenv import load_dotenv
    load_dotenv(_env_file)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging
from contextlib import asynccontextmanager

from config.settings import Settings
from backend.routers import surveys, validation, reports, auth, market_research
from database.connection import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SynTera Test Suite API")
    await init_db()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="SynTera Test Suite API",
    description="Statistical validation framework",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve static assets (CSS, JS)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "static")
INDEX_HTML = os.path.join(os.path.dirname(__file__), "..", "app", "index.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(surveys.router, prefix="/api/surveys", tags=["surveys"])
app.include_router(validation.router, prefix="/api/validation", tags=["validation"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(market_research.router, prefix="/api/market-research", tags=["market-research"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "syntera-test-suite"}


@app.get("/")
async def index():
    """Serve the main HTML dashboard."""
    return FileResponse(INDEX_HTML)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")



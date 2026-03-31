"""
main.py — FastAPI application entry point.
Registers all routers, configures CORS, initialises services on startup.
"""
import logging, os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes.health import router as health_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.query import router as query_router
from app.api.routes.files import router as files_router
from app.api.routes.suggestions import router as suggestions_router
from app.api.routes.analyze import router as analyze_router
from app.api.routes.compliance import router as compliance_router
from app.api.routes.eval_retrieve import router as eval_retrieve_router
from app.rag.embeddings import _get_local_model, _get_service
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown.

    Startup:
        - Ensures the upload directory exists.
        - Logs the active mode (demo / production).

    Shutdown:
        - No-op for the demo stack; swap in cleanup logic for production.
    """
    # --- Startup ---
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Upload directory ready: '%s'", upload_dir.resolve())

    mode = "production" if settings.azure_search_endpoint else "development"
    print(f"Starting Riverty Contract Review — mode: {mode}, env: {settings.app_env}")
    
    if settings.hf_token:
        os.environ["HF_TOKEN"] = settings.hf_token
        logger.info("HF token loaded")
    else:
        logger.warning("HF_TOKEN not set")

    _get_local_model()
    _get_service()

    print("✅ Embedding model preloaded")
    yield
    
    

    # --- Shutdown ---
    logger.info("Riverty Contract Review shutting down.")


app = FastAPI(
    title="Riverty Contract Review API",
    description="RAG-based legal contract search and analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================================
# DEMO MODE: localhost:3000 CORS origin — React dev server
# PRODUCTION SWAP → Azure Static Web Apps (AWS: CloudFront):
#   Replace allow_origins with the production domain, e.g.:
#   allow_origins=["https://contracts.riverty.com"]
#   Never use allow_origins=["*"] with credentialed requests
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Route registration ---
app.include_router(health_router)                         # GET  /health
app.include_router(ingest_router, prefix="/api")          # POST /api/ingest
app.include_router(query_router, prefix="/api")           # POST /api/query
app.include_router(files_router, prefix="/api")           # GET  /api/files/{filename}
app.include_router(suggestions_router, prefix="/api")     # GET  /api/suggested-questions
app.include_router(analyze_router, prefix="/api")         # POST /api/analyze
app.include_router(compliance_router, prefix="/api")      # POST /api/compliance
app.include_router(eval_retrieve_router, prefix="/api")   # POST /api/eval/retrieve

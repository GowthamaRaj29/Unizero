from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

from database.base import (
    Base,
    engine
)

# Import models so SQLAlchemy registers them
import database.models

# Routers
from auth.router import router as auth_router
from users.router import router as users_router
from workflows.router import router as workflows_router
from investigations.router import router as investigations_router
from approvals.router import router as approvals_router
from audit.router import router as audit_router
from reports.router import router as reports_router
from breaks.router import router as breaks_router
from admin.router import router as admin_router
from data_sources.router import router as data_sources_router
from field_mappings.router import router as field_mappings_router
from ingestion.router import router as ingestion_router
from ai_bridge.router import router as ai_bridge_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Unizero Backend",
    description="Financial reconciliation backend",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# REACT FRONTEND CONNECTION
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=settings.frontend_origins,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# DATABASE
# ============================================================

# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    auth_router,
    prefix="/api"
)

app.include_router(
    users_router,
    prefix="/api"
)

app.include_router(
    workflows_router,
    prefix="/api"
)

app.include_router(
    investigations_router,
    prefix="/api"
)

app.include_router(
    approvals_router,
    prefix="/api"
)

app.include_router(
    audit_router,
    prefix="/api"
)

app.include_router(
    reports_router,
    prefix="/api"
)

app.include_router(
    breaks_router,
    prefix="/api"
)

app.include_router(
    admin_router,
    prefix="/api"
)

app.include_router(
    data_sources_router,
    prefix="/api"
)

app.include_router(
    field_mappings_router,
    prefix="/api"
)

app.include_router(
    ingestion_router,
    prefix="/api"
)

app.include_router(
    ai_bridge_router,
    prefix="/api"
)


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
def root():

    return {
        "message": "Unizero Backend",
        "status": "running"
    }


@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "Unizero-backend"
    }



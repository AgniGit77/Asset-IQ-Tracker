"""CAT AssetIQ — FastAPI application entry point."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, async_session
from app.seed import seed_database
from app.routers import equipment, lifecycle, alerts, analytics, timeline, inspection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables and seed data."""
    await init_db()
    async with async_session() as db:
        await seed_database(db)
    print("[OK] CAT AssetIQ backend ready")
    yield


app = FastAPI(
    title="CAT AssetIQ",
    description="Predictive Rental & Fleet Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(equipment.router)
app.include_router(lifecycle.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(timeline.router)
app.include_router(inspection.router)


@app.get("/")
async def root():
    return {"name": "CAT AssetIQ", "version": "1.0.0", "status": "operational"}


@app.get("/api/health")
async def health():
    return {"status": "healthy"}

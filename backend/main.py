"""Smart Rental Tracking System — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import router
from services import database as db
from services.engine import engine
from utils.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    try:
        result = engine.refresh(retrain_forecast=True)
        logger.info("Initial data load: %s", result)
    except Exception:
        logger.exception("Initial data load failed — app will still start")
    yield


app = FastAPI(
    title="Smart Rental Tracking System",
    description=(
        "Caterpillar industrial equipment rental tracking API.\n\n"
        "**Check-In** = equipment leaves the company (rented out).\n"
        "**Check-Out** = equipment returns to the company."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    settings = get_settings()
    logger.exception("Unhandled error on %s", request.url.path)
    detail = str(exc) if settings.debug else "An internal error occurred."
    return JSONResponse(status_code=500, content={"detail": detail})


@app.get("/")
def root():
    return {
        "name": "Smart Rental Tracking System",
        "docs": "/docs",
        "health": "/api/health",
        "terminology": {
            "check_in": "Equipment leaves the company (rented out)",
            "check_out": "Equipment returns to the company",
        },
    }

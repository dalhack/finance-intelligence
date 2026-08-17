from app.api.v1 import (
    calculations,
    comparisons,
    dev_session,
    documents,
    evidence,
    facts,
    health,
    me,
    organizations,
    version,
)
from app.core.config import settings
from app.core.errors import BaseAPIException
from app.middleware.error_handler import (
    custom_api_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.middleware.execution_context import RequestContextMiddleware
from app.routers import analyses
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
)

# Middleware
app.add_middleware(RequestContextMiddleware)

# CORS Policy: Restricted in production
origins = ["*"] if settings.is_development else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Custom Error Handlers
app.add_exception_handler(BaseAPIException, custom_api_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Register Routers
app.include_router(health.router, tags=["Health"])
app.include_router(version.router, prefix="/api/v1", tags=["Version"])
app.include_router(me.router, prefix="/api/v1", tags=["User"])
app.include_router(dev_session.router, prefix="/api/v1", tags=["Development Auth"])
app.include_router(organizations.router, prefix="/api/v1", tags=["Organization"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(facts.router, prefix="/api/v1", tags=["Financial Facts & Candidates"])
app.include_router(calculations.router, prefix="/api/v1/calculations", tags=["Calculations"])
app.include_router(comparisons.router, prefix="/api/v1/comparisons", tags=["Comparisons"])
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["Evidence"])
app.include_router(analyses.router, prefix="/api/v1", tags=["AI Orchestration Analyses"])

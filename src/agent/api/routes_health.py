"""
Routes for health check endpoints.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

from ..infra.config import get_agent_runtime_settings
from ..infra.db import get_connection
from ..infra.logging import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    app: Dict[str, str]
    config: Dict[str, Any]
    db: Dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse: Health status of all components
    """
    app_status = "healthy"
    config_status = "healthy"
    db_status = "healthy"
    config_info = {}
    db_info = {}

    try:
        settings = get_agent_runtime_settings()
        config_info = {
            "rag_settings_path": str(settings.rag_settings_path),
            "db_path": str(settings.db_path),
            "log_level": settings.log_level,
            "default_temperature": settings.default_temperature,
            "default_top_k": settings.default_top_k,
        }
    except Exception as e:
        logger.error(f"Config health check failed: {e}")
        config_status = "unhealthy"
        config_info = {"error": str(e)}

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
        db_info = {"error": str(e)}
    else:
        db_info = {
            "status": "connected",
            "path": str(settings.db_path),
        }

    if app_status == "healthy" and config_status == "healthy" and db_status == "healthy":
        overall_status = "healthy"
    else:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        app={"status": app_status, "version": "1.0.0"},
        config=config_info,
        db=db_info,
    )

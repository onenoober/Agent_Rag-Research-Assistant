"""
Logging module for Agent.

Provides structured logging with trace_id/session_id support.
"""

import logging
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

from .config import get_agent_runtime_settings


trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


class StructuredLogFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        trace_id = trace_id_var.get()
        session_id = session_id_var.get()

        if trace_id:
            log_data["trace_id"] = trace_id
        if session_id:
            log_data["session_id"] = session_id

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data)


class SimpleLogFormatter(logging.Formatter):
    """Simple formatter for console output."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id = trace_id_var.get()
        session_id = session_id_var.get()

        parts = [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            f"[{record.levelname}]",
            f"[{record.name}]",
        ]

        if trace_id:
            parts.append(f"[trace:{trace_id[:8]}...]")
        if session_id:
            parts.append(f"[session:{session_id[:8]}...]")

        parts.append(record.getMessage())

        return " ".join(parts)


def setup_logger(
    name: Optional[str] = None,
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    structured: bool = True
) -> logging.Logger:
    """
    Setup and configure logger.

    Args:
        name: Logger name, if None configures root logger
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
        structured: Use structured JSON logging

    Returns:
        Configured logger instance
    """
    settings = get_agent_runtime_settings()
    log_level = level or settings.log_level
    log_path = log_file or settings.log_file

    logger_name = name or "agent"
    logger = logging.getLogger(logger_name)

    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if structured:
        console_handler.setFormatter(StructuredLogFormatter())
    else:
        console_handler.setFormatter(SimpleLogFormatter())

    logger.addHandler(console_handler)

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        file_handler.setFormatter(StructuredLogFormatter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            setup_logger()
        else:
            for handler in root_logger.handlers:
                logger.addHandler(handler)
    return logger


def set_trace_id(trace_id: str) -> None:
    """Set trace_id for current context."""
    trace_id_var.set(trace_id)


def set_session_id(session_id: str) -> None:
    """Set session_id for current context."""
    session_id_var.set(session_id)


def clear_context() -> None:
    """Clear trace_id and session_id from context."""
    trace_id_var.set(None)
    session_id_var.set(None)

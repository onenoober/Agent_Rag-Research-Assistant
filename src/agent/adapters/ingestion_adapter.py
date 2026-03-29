"""
Ingestion adapter for Agent.

Wraps existing IngestionPipeline functionality.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import traceback

from ..infra.logging import get_logger
from .settings_adapter import get_agent_config


logger = get_logger(__name__)


@dataclass
class IngestResult:
    """Result of file ingestion."""

    success: bool
    doc_id: str = ""
    indexed_chunks: int = 0
    collection_name: str = ""
    status: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "doc_id": self.doc_id,
            "indexed_chunks": self.indexed_chunks,
            "collection_name": self.collection_name,
            "status": self.status,
            "error": self.error,
            "metadata": self.metadata,
        }


class IngestionAdapter:
    """Adapter for document ingestion operations."""

    def __init__(self):
        self._initialized = False
        self._pipeline = None
        self._config = get_agent_config()

    def initialize(self) -> None:
        """Initialize ingestion components."""
        if self._initialized:
            return

        try:
            from src.ingestion.pipeline import IngestionPipeline
            from src.core.settings import load_settings

            settings = load_settings()
            collection = self._config.vector_store_collection
            self._pipeline = IngestionPipeline(settings=settings, collection=collection)

            self._initialized = True
            logger.info("Ingestion adapter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ingestion adapter: {e}")
            logger.debug(traceback.format_exc())
            raise

    def ingest(
        self,
        file_path: str,
        collection_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestResult:
        """
        Ingest a file into the knowledge base.

        Args:
            file_path: Path to file to ingest
            collection_name: Collection name (optional, uses default if not provided)
            metadata: Additional metadata for the document

        Returns:
            IngestResult with indexing status
        """
        if not self._initialized:
            self.initialize()

        if collection_name is None:
            collection_name = self._config.vector_store_collection

        try:
            from src.ingestion.pipeline import IngestionPipeline
            from src.core.settings import load_settings

            settings = load_settings()
            pipeline = IngestionPipeline(
                settings=settings,
                collection=collection_name
            )

            result = pipeline.run(file_path)

            return IngestResult(
                success=result.success,
                doc_id=result.doc_id or "",
                indexed_chunks=result.chunk_count,
                collection_name=collection_name,
                status="completed" if result.success else "failed",
                error=result.error,
                metadata=result.to_dict(),
            )

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            logger.debug(traceback.format_exc())
            return IngestResult(
                success=False,
                collection_name=collection_name,
                status="error",
                error=str(e),
            )

    def health_check(self) -> Dict[str, Any]:
        """Check ingestion adapter health."""
        status = {
            "initialized": self._initialized,
            "config": {
                "vector_store_collection": self._config.vector_store_collection,
            },
        }

        try:
            if self._initialized:
                status["status"] = "healthy"
            else:
                status["status"] = "not_initialized"
        except Exception as e:
            status["status"] = "unhealthy"
            status["error"] = str(e)

        return status


_ingestion_adapter: Optional[IngestionAdapter] = None


def get_ingestion_adapter() -> IngestionAdapter:
    """Get singleton ingestion adapter instance."""
    global _ingestion_adapter
    if _ingestion_adapter is None:
        _ingestion_adapter = IngestionAdapter()
    return _ingestion_adapter

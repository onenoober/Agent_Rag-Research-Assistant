"""File upload tool for Agent."""

import os
from typing import Any, Dict
from pathlib import Path

from .base import BaseTool, ToolInput, ToolOutput
from ..adapters.ingestion_adapter import get_ingestion_adapter
from ..infra.logging import get_logger


logger = get_logger(__name__)


class FileUploadTool(BaseTool):
    """Tool for uploading and indexing files."""

    def __init__(self):
        super().__init__(
            name="file_upload",
            description="Upload and index a file into the knowledge base",
            input_schema={
                "file_path": {"type": "string", "required": True},
                "collection_name": {"type": "string", "required": False},
                "metadata": {"type": "object", "required": False}
            }
        )
        self._ingestion_adapter = get_ingestion_adapter()

    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """Execute file upload and indexing."""
        if not tool_input.file_path:
            return ToolOutput(
                success=False,
                result=None,
                error="file_path is required"
            )

        file_path = tool_input.file_path
        logger.info(f"File upload: {file_path}")

        if not os.path.exists(file_path):
            return ToolOutput(
                success=False,
                result=None,
                error=f"File not found: {file_path}"
            )

        try:
            collection_name = tool_input.collection_name or self._generate_collection_name(file_path)
            metadata = tool_input.metadata or {}

            result = self._ingestion_adapter.ingest(
                file_path=file_path,
                collection_name=collection_name,
                metadata=metadata
            )

            if result.get("status") == "success":
                return ToolOutput(
                    success=True,
                    result={
                        "doc_id": result.get("doc_id"),
                        "indexed_chunks": result.get("indexed_chunks", 0),
                        "collection_name": collection_name,
                        "status": "indexed"
                    }
                )
            else:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=result.get("error", "Unknown error")
                )

        except Exception as e:
            logger.error(f"File upload error: {e}")
            return ToolOutput(
                success=False,
                result=None,
                error=str(e)
            )

    def _generate_collection_name(self, file_path: str) -> str:
        """Generate a unique collection name for the file."""
        filename = Path(file_path).stem
        import uuid
        short_uuid = str(uuid.uuid4())[:8]
        return f"agent_{filename}_{short_uuid}"

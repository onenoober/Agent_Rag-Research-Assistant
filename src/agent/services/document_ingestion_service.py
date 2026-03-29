"""Document ingestion service for structured document processing.

This service orchestrates the complete document ingestion pipeline:
1. Parse document using appropriate parser (PDF, TXT, MD)
2. Build structured chunks with metadata
3. Index chunks using existing ingestion adapter

This service reuses existing ingestion_adapter for indexing while
adding structured metadata support.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agent.schemas.document import ParsedDocument, StructuredChunk
from src.agent.parsers import (
    ChunkBuilder,
    ChunkBuilderConfig,
    create_parser,
)
from src.agent.adapters.ingestion_adapter import IngestionAdapter

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of document ingestion."""
    success: bool
    document_id: str
    chunksIndexed: int
    source_file: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentIngestionService:
    """Service for ingesting documents with structured metadata.
    
    This service:
    1. Parses documents (PDF, TXT, MD) using appropriate parser
    2. Builds structured chunks preserving page/section info
    3. Indexes chunks using existing IngestionAdapter
    4. Returns ingestion result with metadata
    
    Attributes:
        ingestion_adapter: Adapter for indexing chunks
        chunk_builder: Builder for creating chunks
    """
    
    def __init__(
        self,
        ingestion_adapter: Optional[IngestionAdapter] = None,
        chunk_builder: Optional[ChunkBuilder] = None,
        chunk_config: Optional[ChunkBuilderConfig] = None,
    ):
        """Initialize document ingestion service.
        
        Args:
            ingestion_adapter: Adapter for indexing. If None, creates default.
            chunk_builder: Chunk builder. If None, creates with config.
            chunk_config: Configuration for chunk builder if creating new.
        """
        # Use existing ingestion adapter or create default
        self._adapter = ingestion_adapter
        if self._adapter is None:
            self._adapter = self._create_default_adapter()
        
        # Create chunk builder
        if chunk_builder is not None:
            self._chunk_builder = chunk_builder
        else:
            config = chunk_config or ChunkBuilderConfig()
            self._chunk_builder = ChunkBuilder(config=config)
    
    def _create_default_adapter(self) -> IngestionAdapter:
        """Create default ingestion adapter."""
        try:
            return IngestionAdapter()
        except Exception as e:
            logger.warning(f"Failed to create default IngestionAdapter: {e}")
            return None
    
    def ingest(
        self,
        file_path: str | Path,
        collection: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest a document file.
        
        Args:
            file_path: Path to the document file
            collection: Optional collection name for indexing
            metadata: Optional additional metadata
            
        Returns:
            IngestionResult with status and details
        """
        path = Path(file_path)
        
        if not path.exists():
            return IngestionResult(
                success=False,
                document_id="",
                chunksIndexed=0,
                source_file=str(path),
                error=f"File not found: {path}",
            )
        
        try:
            # Step 1: Parse document
            logger.info(f"Parsing document: {path}")
            parser = create_parser(path)
            parsed_doc = parser.parse(path)
            
            # Step 2: Build chunks with structured metadata
            logger.info(f"Building chunks from {len(parsed_doc.sections)} sections")
            chunks = self._chunk_builder.build_chunks(parsed_doc)
            
            if not chunks:
                return IngestionResult(
                    success=False,
                    document_id="",
                    chunksIndexed=0,
                    source_file=str(path),
                    error="No chunks generated from document",
                )
            
            # Step 3: Index chunks using adapter
            indexed_count = 0
            if self._adapter is not None:
                indexed_count = self._index_chunks(chunks, collection, metadata)
            
            # Generate document ID
            doc_id = self._generate_doc_id(path)
            
            # Prepare result metadata
            result_metadata = {
                "total_pages": parsed_doc.total_pages,
                "total_sections": len(parsed_doc.sections),
                "total_chunks": len(chunks),
                "indexed_chunks": indexed_count,
            }
            if metadata:
                result_metadata.update(metadata)
            
            return IngestionResult(
                success=True,
                document_id=doc_id,
                chunksIndexed=indexed_count,
                source_file=str(path),
                metadata=result_metadata,
            )
            
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            return IngestionResult(
                success=False,
                document_id="",
                chunksIndexed=0,
                source_file=str(path),
                error=str(e),
            )
    
    def _index_chunks(
        self,
        chunks: List[StructuredChunk],
        collection: Optional[str],
        additional_metadata: Optional[Dict[str, Any]],
    ) -> int:
        """Index chunks using the ingestion adapter.
        
        Args:
            chunks: List of structured chunks to index
            collection: Optional collection name
            additional_metadata: Additional metadata to add
            
        Returns:
            Number of chunks indexed
        """
        if self._adapter is None:
            logger.warning("No ingestion adapter available")
            return 0
        
        indexed_count = 0
        
        for chunk in chunks:
            try:
                # Prepare chunk metadata - preserve structured metadata
                chunk_metadata = {
                    "source_path": chunk.metadata.source_file,
                    "page_no": chunk.metadata.page_no,
                    "section_title": chunk.metadata.section_title,
                    "chunk_index": chunk.metadata.chunk_index,
                    "char_start": chunk.metadata.char_start,
                    "char_end": chunk.metadata.char_end,
                    "content_type": chunk.metadata.content_type,
                }
                
                # Add additional metadata
                if additional_metadata:
                    chunk_metadata.update(additional_metadata)
                
                # Add collection if specified
                if collection:
                    chunk_metadata["collection"] = collection
                
                # Index using adapter
                # Note: This calls existing adapter which may need adaptation
                self._adapter.ingest(
                    text=chunk.text,
                    metadata=chunk_metadata,
                    collection=collection,
                )
                indexed_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to index chunk: {e}")
                continue
        
        return indexed_count
    
    def _generate_doc_id(self, path: Path) -> str:
        """Generate document ID from file path.
        
        Args:
            path: File path
            
        Returns:
            Document ID string
        """
        import hashlib
        
        file_hash = hashlib.md5(str(path).encode()).hexdigest()[:16]
        return f"doc_{file_hash}"
    
    def ingest_batch(
        self,
        file_paths: List[str | Path],
        collection: Optional[str] = None,
    ) -> List[IngestionResult]:
        """Ingest multiple documents.
        
        Args:
            file_paths: List of file paths to ingest
            collection: Optional collection name
            
        Returns:
            List of ingestion results
        """
        results = []
        
        for file_path in file_paths:
            result = self.ingest(file_path, collection=collection)
            results.append(result)
        
        return results


def create_ingestion_service(
    settings: Optional[Any] = None,
) -> DocumentIngestionService:
    """Factory function to create DocumentIngestionService.
    
    Args:
        settings: Optional application settings
        
    Returns:
        Configured DocumentIngestionService instance
    """
    # Get chunk config from settings if available
    chunk_config = None
    if settings is not None:
        try:
            ingestion = getattr(settings, 'ingestion', None)
            if ingestion:
                chunk_config = ChunkBuilderConfig(
                    chunk_size=getattr(ingestion, 'chunk_size', 500),
                    chunk_overlap=getattr(ingestion, 'chunk_overlap', 50),
                )
        except Exception:
            pass
    
    return DocumentIngestionService(chunk_config=chunk_config)


__all__ = [
    "DocumentIngestionService",
    "IngestionResult",
    "create_ingestion_service",
]

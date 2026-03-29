"""Chunk builder for creating structured chunks from parsed documents.

This module builds structured chunks from ParsedDocument by:
1. Using existing SplitterFactory for text splitting
2. Preserving section and page metadata
3. Supporting overlap between chunks
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from src.agent.schemas.document import (
    ChunkMetadata,
    DocumentSection,
    ParsedDocument,
    StructuredChunk,
)
from src.libs.splitter import SplitterFactory

try:
    from src.core.settings import Settings
except ImportError:
    Settings = None  # type: ignore


@dataclass
class ChunkBuilderConfig:
    """Configuration for chunk building."""
    chunk_size: int = 500
    chunk_overlap: int = 50
    content_types_enabled: List[str] = None  # ["text", "table", "caption"]

    def __post_init__(self):
        if self.content_types_enabled is None:
            self.content_types_enabled = ["text", "table", "caption"]


class ChunkBuilder:
    """Builds structured chunks from parsed documents.
    
    This builder:
    1. Iterates through document sections
    2. Uses SplitterFactory to split text into chunks
    3. Preserves metadata (page_no, section_title, etc.)
    4. Supports chunk overlap
    
    Attributes:
        config: Chunk building configuration
        splitter: Text splitter instance from SplitterFactory
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        config: Optional[ChunkBuilderConfig] = None,
    ):
        """Initialize chunk builder.
        
        Args:
            settings: Application settings for splitter configuration
            config: Chunk builder configuration
        """
        self.config = config or ChunkBuilderConfig()
        
        # Create splitter from existing SplitterFactory
        if settings is not None:
            try:
                self._splitter = SplitterFactory.create(settings)
            except Exception:
                # Fallback to simple splitter
                self._splitter = self._create_simple_splitter()
        else:
            self._splitter = self._create_simple_splitter()
    
    def _create_simple_splitter(self):
        """Create a simple splitter as fallback."""
        
        class SimpleSplitter:
            """Simple splitter that splits by character count."""
            
            def __init__(self, chunk_size: int, chunk_overlap: int):
                self._chunk_size = chunk_size
                self._chunk_overlap = chunk_overlap
            
            def split_text(self, text: str) -> list[str]:
                if not text:
                    return []
                
                chunks = []
                start = 0
                while start < len(text):
                    end = start + self._chunk_size
                    chunks.append(text[start:end])
                    start = end - self._chunk_overlap
                
                return chunks
        
        return SimpleSplitter(self.config.chunk_size, self.config.chunk_overlap)
    
    def build_chunks(
        self,
        document: ParsedDocument,
        source_file: Optional[str] = None,
    ) -> List[StructuredChunk]:
        """Build structured chunks from a parsed document.
        
        Args:
            document: Parsed document to chunk
            source_file: Override source file path (uses document.source_file if None)
            
        Returns:
            List of structured chunks with metadata
        """
        chunks: List[StructuredChunk] = []
        
        source = source_file or document.source_file
        
        # Process each section
        for section in document.sections:
            section_chunks = self._chunk_section(section, source)
            chunks.extend(section_chunks)
        
        # If no sections, process pages directly
        if not chunks and document.pages:
            for page in document.pages:
                page_chunks = self._chunk_page(page, source)
                chunks.extend(page_chunks)
        
        return chunks
    
    def _chunk_section(
        self,
        section: DocumentSection,
        source_file: str,
    ) -> List[StructuredChunk]:
        """Chunk a single section.
        
        Args:
            section: Document section to chunk
            source_file: Source file path
            
        Returns:
            List of structured chunks
        """
        chunks: List[StructuredChunk] = []
        
        if not section.text or not section.text.strip():
            return chunks
        
        # Use splitter to get text chunks
        try:
            text_chunks = self._splitter.split_text(section.text)
        except Exception:
            # Fallback: simple split
            text_chunks = self._simple_split(section.text)
        
        for idx, text in enumerate(text_chunks):
            if not text.strip():
                continue
            
            metadata = ChunkMetadata(
                source_file=source_file,
                page_no=section.page_no,
                section_title=section.title,
                chunk_index=idx,
                char_start=section.char_start,
                char_end=section.char_end,
                content_type="text",
            )
            
            chunk = StructuredChunk(
                text=text.strip(),
                metadata=metadata,
            )
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_page(self, page, source_file: str) -> List[StructuredChunk]:
        """Chunk a single page (fallback when no sections).
        
        Args:
            page: Document page to chunk
            source_file: Source file path
            
        Returns:
            List of structured chunks
        """
        chunks: List[StructuredChunk] = []
        
        if not page.text or not page.text.strip():
            return chunks
        
        # Use splitter
        try:
            text_chunks = self._splitter.split_text(page.text)
        except Exception:
            text_chunks = self._simple_split(page.text)
        
        for idx, text in enumerate(text_chunks):
            if not text.strip():
                continue
            
            metadata = ChunkMetadata(
                source_file=source_file,
                page_no=page.page_no,
                section_title=None,
                chunk_index=idx,
                content_type="text",
            )
            
            chunk = StructuredChunk(
                text=text.strip(),
                metadata=metadata,
            )
            chunks.append(chunk)
        
        return chunks
    
    def _simple_split(self, text: str) -> List[str]:
        """Simple character-based split as fallback.
        
        Args:
            text: Text to split
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        
        return chunks


def create_chunk_builder(
    settings: Optional[Settings] = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> ChunkBuilder:
    """Factory function to create a ChunkBuilder.
    
    Args:
        settings: Application settings
        chunk_size: Override chunk size
        chunk_overlap: Override chunk overlap
        
    Returns:
        Configured ChunkBuilder instance
    """
    config = ChunkBuilderConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return ChunkBuilder(settings=settings, config=config)


__all__ = [
    "ChunkBuilder",
    "ChunkBuilderConfig",
    "create_chunk_builder",
]

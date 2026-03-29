"""Document parsing schemas for structured document processing.

This module defines schemas for document parsing, including:
- DocumentPage: Represents a single page from a document
- DocumentSection: Represents a section within a document
- ParsedDocument: Complete parsed document structure
- StructuredChunk: Chunk with structured metadata
- ChunkMetadata: Metadata for chunks including page, section, content type

These schemas enable:
- Page number retention
- Section title preservation
- Paragraph-level structured splitting
- Table/figure caption metadata
- Precise citation source location
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChunkMetadata:
    """Metadata for structured chunks.
    
    This metadata is stored with each chunk to enable:
    - Source file tracking
    - Page number retention for citation
    - Section title preservation
    - Character-level position for precise citation
    - Content type differentiation (text, table, caption)
    
    Attributes:
        source_file: Path to the source file
        page_no: Page number (1-based), None if not applicable
        section_title: Title of the section containing this chunk
        chunk_index: Index of this chunk within its section/document
        char_start: Starting character position in original document
        char_end: Ending character position in original document
        content_type: Type of content (text, table, caption)
    """
    source_file: str
    page_no: Optional[int] = None
    section_title: Optional[str] = None
    chunk_index: int = 0
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    content_type: str = "text"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_file": self.source_file,
            "page_no": self.page_no,
            "section_title": self.section_title,
            "chunk_index": self.chunk_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "content_type": self.content_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkMetadata":
        """Create from dictionary."""
        return cls(
            source_file=data.get("source_file", ""),
            page_no=data.get("page_no"),
            section_title=data.get("section_title"),
            chunk_index=data.get("chunk_index", 0),
            char_start=data.get("char_start"),
            char_end=data.get("char_end"),
            content_type=data.get("content_type", "text"),
        )


@dataclass
class StructuredChunk:
    """A chunk of text with structured metadata.
    
    This represents a piece of the parsed document that can be indexed
    and retrieved with full source context.
    
    Attributes:
        text: The text content of the chunk
        metadata: Structured metadata about this chunk
    """
    text: str
    metadata: ChunkMetadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredChunk":
        """Create from dictionary."""
        return cls(
            text=data.get("text", ""),
            metadata=ChunkMetadata.from_dict(data.get("metadata", {})),
        )


@dataclass
class DocumentPage:
    """Represents a single page in a document.
    
    Attributes:
        page_no: Page number (1-based)
        text: Raw text content of the page
        sections: List of sections identified on this page
    """
    page_no: int
    text: str
    sections: List["DocumentSection"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_no": self.page_no,
            "text": self.text,
            "sections": [s.to_dict() for s in self.sections],
        }


@dataclass
class DocumentSection:
    """Represents a section within a document.
    
    A section is typically identified by a heading/title and contains
    the content below that heading until the next section.
    
    Attributes:
        title: Section title/heading (None for untitled sections)
        level: Heading level (1 for #, 2 for ##, etc.)
        page_no: Page number where this section starts
        char_start: Character position where section starts
        char_end: Character position where section ends
        text: Section content text
    """
    title: Optional[str]
    level: int = 1
    page_no: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "level": self.level,
            "page_no": self.page_no,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "text": self.text,
        }


@dataclass
class ParsedDocument:
    """Complete parsed document structure.
    
    This is the output of document parsing, containing all pages
    and sections with their metadata.
    
    Attributes:
        source_file: Path to the source document
        total_pages: Total number of pages
        pages: List of parsed pages
        sections: Flat list of all sections across pages
    """
    source_file: str
    total_pages: int
    pages: List[DocumentPage] = field(default_factory=list)
    sections: List[DocumentSection] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_file": self.source_file,
            "total_pages": self.total_pages,
            "pages": [p.to_dict() for p in self.pages],
            "sections": [s.to_dict() for s in self.sections],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParsedDocument":
        """Create from dictionary."""
        return cls(
            source_file=data.get("source_file", ""),
            total_pages=data.get("total_pages", 0),
            pages=[
                DocumentPage(
                    page_no=p.get("page_no", 0),
                    text=p.get("text", ""),
                    sections=[
                        DocumentSection(
                            title=s.get("title"),
                            level=s.get("level", 1),
                            page_no=s.get("page_no"),
                            char_start=s.get("char_start"),
                            char_end=s.get("char_end"),
                            text=s.get("text", ""),
                        )
                        for s in p.get("sections", [])
                    ],
                )
                for p in data.get("pages", [])
            ],
            sections=[
                DocumentSection(
                    title=s.get("title"),
                    level=s.get("level", 1),
                    page_no=s.get("page_no"),
                    char_start=s.get("char_start"),
                    char_end=s.get("char_end"),
                    text=s.get("text", ""),
                )
                for s in data.get("sections", [])
            ],
        )


# Re-export for convenience
__all__ = [
    "ChunkMetadata",
    "StructuredChunk",
    "DocumentPage",
    "DocumentSection",
    "ParsedDocument",
]

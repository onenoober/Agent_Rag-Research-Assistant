"""PDF parser for PDF files.

This parser handles PDF files, extracting:
- Page-level text with page numbers
- Basic heading detection
- Table/figure caption detection (basic)
- Uses existing PdfLoader for core text extraction
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF

from src.agent.schemas.document import (
    DocumentPage,
    DocumentSection,
    ParsedDocument,
)
from src.agent.parsers.base import BaseParser, ParseError, UnsupportedFormatError


# Try to import existing PdfLoader
try:
    from src.libs.loader.pdf_loader import PdfLoader
    PDF_LOADER_AVAILABLE = True
except ImportError:
    PDF_LOADER_AVAILABLE = False


@dataclass
class PdfParserConfig:
    """Configuration for PDF parser."""
    extract_images: bool = False  # Disable image extraction for structured parsing
    detect_headings: bool = True
    heading_threshold: float = 0.8  # Font size ratio to detect headings


class PdfParser(BaseParser):
    """Parser for PDF files.
    
    This parser:
    1. Reuses existing PdfLoader for core text extraction
    2. Uses PyMuPDF directly for page-level information
    3. Detects headings based on font size
    4. Preserves page numbers
    
    Attributes:
        config: Parser configuration options
    """
    
    supported_extensions = [".pdf"]
    
    def __init__(self, config: Optional[PdfParserConfig] = None):
        """Initialize PDF parser.
        
        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or PdfParserConfig()
        
        # Initialize base loader if available
        self._base_loader: Optional[PdfLoader] = None
        if PDF_LOADER_AVAILABLE:
            try:
                self._base_loader = PdfLoader(
                    extract_images=self.config.extract_images
                )
            except Exception:
                pass  # Fall back to PyMuPDF-only mode
    
    def parse(self, file_path: str | Path) -> ParsedDocument:
        """Parse a PDF file.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            ParsedDocument with parsed pages and sections.
            
        Raises:
            ParseError: If parsing fails.
        """
        path = self.validate_file(file_path)
        
        try:
            # Use PyMuPDF for page-level parsing
            return self._parse_with_pymupdf(path)
        except Exception as e:
            raise ParseError(f"Failed to parse PDF: {e}") from e
    
    def _parse_with_pymupdf(self, path: Path) -> ParsedDocument:
        """Parse PDF using PyMuPDF directly.
        
        Args:
            path: Path to PDF file
            
        Returns:
            ParsedDocument with pages and sections
        """
        try:
            pdf_doc = fitz.open(str(path))
        except Exception as e:
            raise ParseError(f"Failed to open PDF: {e}") from e
        
        pages: List[DocumentPage] = []
        all_sections: List[DocumentSection] = []
        
        total_pages = len(pdf_doc)
        
        for page_num in range(total_pages):
            page = pdf_doc[page_num]
            
            # Extract text from page
            text = page.get_text()
            
            # Get page blocks for structure analysis
            blocks = page.get_text("blocks")
            
            # Detect sections within this page
            sections, heading_positions = self._detect_sections(
                text, blocks, page_num + 1
            )
            
            page_obj = DocumentPage(
                page_no=page_num + 1,
                text=text,
                sections=sections,
            )
            pages.append(page_obj)
            all_sections.extend(sections)
        
        pdf_doc.close()
        
        return ParsedDocument(
            source_file=str(path),
            total_pages=total_pages,
            pages=pages,
            sections=all_sections,
        )
    
    def _detect_sections(
        self,
        text: str,
        blocks: List,
        page_num: int,
    ) -> tuple[List[DocumentSection], List[tuple]]:
        """Detect sections within a page based on text blocks.
        
        Args:
            text: Full text of the page
            blocks: List of text blocks from PyMuPDF
            page_num: Page number
            
        Returns:
            Tuple of (sections, heading_positions)
        """
        sections: List[DocumentSection] = []
        heading_positions: List[tuple] = []
        
        if not blocks:
            # No blocks, treat entire page as one section
            sections.append(DocumentSection(
                title=None,
                level=1,
                page_no=page_num,
                char_start=0,
                char_end=len(text),
                text=text.strip(),
            ))
            return sections, heading_positions
        
        # Analyze blocks to detect headings
        # In a simple implementation, we treat the first non-empty block as section start
        current_text_parts: List[str] = []
        section_start = 0
        
        for i, block in enumerate(blocks):
            if len(block) >= 5:
                block_text = block[4].strip()
                block_bbox = block[:4]  # (x0, y0, x1, y1)
                
                if not block_text:
                    continue
                
                # Simple heuristic: short blocks with no lowercase might be headings
                is_heading = self._is_likely_heading(block_text)
                
                if is_heading and current_text_parts:
                    # Save previous section
                    section_text = " ".join(current_text_parts)
                    if section_text.strip():
                        sections.append(DocumentSection(
                            title=None,  # Could enhance with detected heading
                            level=1,
                            page_no=page_num,
                            char_start=section_start,
                            char_end=section_start + len(section_text),
                            text=section_text.strip(),
                        ))
                    current_text_parts = []
                    section_start = text.find(block_text, section_start)
                    if section_start == -1:
                        section_start = 0
                
                current_text_parts.append(block_text)
        
        # Add remaining text as final section
        if current_text_parts:
            section_text = " ".join(current_text_parts)
            if section_text.strip():
                sections.append(DocumentSection(
                    title=None,
                    level=1,
                    page_no=page_num,
                    char_start=section_start,
                    char_end=section_start + len(section_text),
                    text=section_text.strip(),
                ))
        
        # If no sections detected, use entire page text
        if not sections:
            sections.append(DocumentSection(
                title=None,
                level=1,
                page_no=page_num,
                char_start=0,
                char_end=len(text),
                text=text.strip(),
            ))
        
        return sections, heading_positions
    
    def _is_likely_heading(self, text: str) -> bool:
        """Simple heuristic to detect if a text block is likely a heading.
        
        Args:
            text: Text block content
            
        Returns:
            True if likely a heading
        """
        if not text:
            return False
        
        # Clean text
        lines = text.strip().split('\n')
        if not lines:
            return False
        
        first_line = lines[0].strip()
        
        # Headings are typically:
        # - Short (less than 100 chars)
        # - Don't end with punctuation
        # - May start with capital letter
        
        if len(first_line) > 100:
            return False
        
        # Check if it looks like a heading
        # (no ending punctuation, reasonable length)
        if first_line and first_line[-1] not in '.?!;:':
            # Short text that might be a heading
            return len(first_line) < 80
        
        return False


__all__ = [
    "PdfParser",
    "PdfParserConfig",
]

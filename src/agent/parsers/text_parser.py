"""Text parser for .txt and .md files.

This parser handles plain text and Markdown files, extracting:
- Section headings (for .md files)
- Paragraphs (for .txt files)
- Page structure (single page for text files)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from src.agent.schemas.document import (
    DocumentPage,
    DocumentSection,
    ParsedDocument,
)
from src.agent.parsers.base import BaseParser, ParseError


# Markdown heading pattern
HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
# Empty line pattern for paragraph separation
EMPTY_LINE_PATTERN = re.compile(r'\n\s*\n')


@dataclass
class TextParserConfig:
    """Configuration for text parser."""
    max_paragraph_length: int = 1000
    detect_headings: bool = True


class TextParser(BaseParser):
    """Parser for text and Markdown files.
    
    This parser supports:
    - .txt files: Split by empty lines into paragraphs
    - .md files: Split by headings (# headings) into sections
    
    Attributes:
        config: Parser configuration options
    """
    
    supported_extensions = [".txt", ".md"]
    
    def __init__(self, config: Optional[TextParserConfig] = None):
        """Initialize text parser.
        
        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or TextParserConfig()
    
    def parse(self, file_path: str | Path) -> ParsedDocument:
        """Parse a text or Markdown file.
        
        Args:
            file_path: Path to the text file.
            
        Returns:
            ParsedDocument with parsed content.
            
        Raises:
            ParseError: If parsing fails.
        """
        path = self.validate_file(file_path)
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            raise ParseError(f"Failed to read file: {e}") from e
        
        # Determine if it's markdown
        is_markdown = path.suffix.lower() == ".md"
        
        if is_markdown:
            return self._parse_markdown(path, text)
        else:
            return self._parse_plain_text(path, text)
    
    def _parse_markdown(self, path: Path, text: str) -> ParsedDocument:
        """Parse a Markdown file.
        
        Args:
            path: File path
            text: File content
            
        Returns:
            ParsedDocument with sections.
        """
        sections: List[DocumentSection] = []
        
        # Find all headings with their positions
        headings = list(HEADING_PATTERN.finditer(text))
        
        for i, match in enumerate(headings):
            level = len(match.group(1))
            title = match.group(2).strip()
            start_pos = match.start()
            
            # Determine end position (next heading or end of text)
            if i + 1 < len(headings):
                end_pos = headings[i + 1].start()
            else:
                end_pos = len(text)
            
            section_text = text[start_pos:end_pos].strip()
            # Remove heading line from section text
            section_text = section_text[len(match.group(0)):].strip()
            
            section = DocumentSection(
                title=title,
                level=level,
                page_no=1,
                char_start=start_pos,
                char_end=end_pos,
                text=section_text,
            )
            sections.append(section)
        
        # If no headings found, treat entire text as one section
        if not sections:
            sections.append(DocumentSection(
                title=None,
                level=1,
                page_no=1,
                char_start=0,
                char_end=len(text),
                text=text.strip(),
            ))
        
        # Create single page containing all sections
        page = DocumentPage(
            page_no=1,
            text=text,
            sections=sections,
        )
        
        return ParsedDocument(
            source_file=str(path),
            total_pages=1,
            pages=[page],
            sections=sections,
        )
    
    def _parse_plain_text(self, path: Path, text: str) -> ParsedDocument:
        """Parse a plain text file.
        
        Splits by empty lines into paragraphs.
        
        Args:
            path: File path
            text: File content
            
        Returns:
            ParsedDocument with paragraphs as sections.
        """
        sections: List[DocumentSection] = []
        
        # Split by empty lines
        paragraphs = EMPTY_LINE_PATTERN.split(text)
        
        char_pos = 0
        for idx, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue
            
            para_start = text.find(para, char_pos)
            if para_start == -1:
                continue
            
            para_end = para_start + len(para)
            
            section = DocumentSection(
                title=None,  # No heading in plain text
                level=1,
                page_no=1,
                char_start=para_start,
                char_end=para_end,
                text=para,
            )
            sections.append(section)
            char_pos = para_end
        
        # If no paragraphs found (single block), treat as one section
        if not sections:
            sections.append(DocumentSection(
                title=None,
                level=1,
                page_no=1,
                char_start=0,
                char_end=len(text),
                text=text.strip(),
            ))
        
        # Create single page
        page = DocumentPage(
            page_no=1,
            text=text,
            sections=sections,
        )
        
        return ParsedDocument(
            source_file=str(path),
            total_pages=1,
            pages=[page],
            sections=sections,
        )


__all__ = [
    "TextParser",
    "TextParserConfig",
]

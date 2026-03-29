"""Structured Splitter implementation using document parsing structure.

This splitter uses the parsed document structure (sections, pages) from 
DocumentParser to create chunks that respect the original document structure.
It works with any parsed document format (PDF, Word, Excel, Text, etc.).
"""

from __future__ import annotations

from typing import Any, List, Optional

from src.libs.splitter.base_splitter import BaseSplitter


class StructuredSplitter(BaseSplitter):
    """Structured text splitter based on document parsing.
    
    This splitter uses the section information from ParsedDocument to create
    chunks that respect the document's natural structure:
    - For documents with sections: use sections as chunks
    - For documents with pages: use pages as chunks  
    - Falls back to recursive splitting if no structure available
    
    Design Principles Applied:
    - Structure-Aware: Leverages parsed document metadata
    - Configurable: Controls max chunk size and overlap
    - Fallback: Uses recursive splitting when needed
    
    Attributes:
        max_chunk_size: Maximum size of each chunk (default: 1000)
        chunk_overlap: Overlap between chunks (default: 100)
        min_section_length: Minimum section length to keep (default: 50)
        
    Example:
        >>> # Using with DocumentParser output
        >>> parser = DocumentParser()
        >>> doc = parser.parse("document.pdf")
        >>> 
        >>> splitter = StructuredSplitter(settings)
        >>> chunks = splitter.split_text(doc.sections[0].text)
    """
    
    def __init__(
        self,
        settings: Any,
        max_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_section_length: int = 50,
        **kwargs: Any,
    ) -> None:
        """Initialize StructuredSplitter.
        
        Args:
            settings: Application settings containing ingestion configuration.
            max_chunk_size: Maximum chunk size (defaults to settings.ingestion.chunk_size).
            chunk_overlap: Overlap between chunks (defaults to settings.ingestion.chunk_overlap).
            min_section_length: Minimum length for a section to be kept as-is.
            **kwargs: Additional parameters.
        """
        self.settings = settings
        
        # Extract configuration
        try:
            ingestion_config = settings.ingestion
            self.max_chunk_size = max_chunk_size if max_chunk_size is not None else ingestion_config.chunk_size
            self.chunk_overlap = chunk_overlap if chunk_overlap is not None else ingestion_config.chunk_overlap
        except AttributeError as e:
            self.max_chunk_size = max_chunk_size or 1000
            self.chunk_overlap = chunk_overlap or 100
        
        self.min_section_length = min_section_length
        
        # Import recursive splitter as fallback
        try:
            from src.libs.splitter.recursive_splitter import RecursiveSplitter
            self._fallback_splitter = RecursiveSplitter(
                settings=settings,
                chunk_size=self.max_chunk_size,
                chunk_overlap=self.chunk_overlap
            )
        except ImportError:
            self._fallback_splitter = None
    
    def split_text(
        self,
        text: str,
        trace: Optional[Any] = None,
        sections: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Split text using document structure.
        
        This method can use provided sections to create structured chunks,
        or it will analyze the text for structure.
        
        Args:
            text: Input text to split.
            trace: Optional TraceContext for observability.
            sections: Optional list of DocumentSection objects from parsing.
            **kwargs: Additional parameters.
        
        Returns:
            A list of text chunks based on document structure.
        """
        self.validate_text(text)
        
        # If sections are provided, use them
        if sections and len(sections) > 0:
            return self._split_by_sections(sections)
        
        # Otherwise, analyze text structure
        return self._analyze_and_split(text)
    
    def _split_by_sections(self, sections: List[Any]) -> List[str]:
        """Split by pre-parsed document sections.
        
        Args:
            sections: List of DocumentSection objects.
            
        Returns:
            List of text chunks.
        """
        chunks = []
        
        for section in sections:
            section_text = section.text if hasattr(section, 'text') else str(section)
            if not section_text or not section_text.strip():
                continue
            
            # If section is small enough, use as-is
            if len(section_text) <= self.max_chunk_size:
                chunks.append(section_text)
            else:
                # Split large sections using fallback
                if self._fallback_splitter:
                    sub_chunks = self._fallback_splitter.split_text(section_text)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(section_text)
        
        # Validate and return
        if not chunks:
            return [sections[0].text] if sections else []
        
        self.validate_chunks(chunks)
        return chunks
    
    def _analyze_and_split(self, text: str) -> List[str]:
        """Analyze text for structure and split accordingly.
        
        Detects:
        - Markdown headings (# Header)
        - Numbered sections (1.2.3, etc.)
        - Bullet points
        - Table structures
        
        Args:
            text: Input text.
            
        Returns:
            List of structured chunks.
        """
        import re
        
        chunks = []
        
        # Try to detect Markdown headings
        heading_pattern = re.compile(r'^#{1,6}\s+.+$', re.MULTILINE)
        headings = list(heading_pattern.finditer(text))
        
        if headings:
            # Split by Markdown headings
            for i, match in enumerate(headings):
                start = match.start()
                end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
                section_text = text[start:end].strip()
                
                if section_text:
                    chunks.extend(self._handle_chunk(section_text))
            
            if chunks:
                self.validate_chunks(chunks)
                return chunks
        
        # Try to detect numbered sections
        numbered_pattern = re.compile(r'^\d+(\.\d+)*\s+.+$', re.MULTILINE)
        numbered = list(numbered_pattern.finditer(text))
        
        if numbered:
            for i, match in enumerate(numbered):
                start = match.start()
                end = numbered[i + 1].start() if i + 1 < len(numbered) else len(text)
                section_text = text[start:end].strip()
                
                if section_text:
                    chunks.extend(self._handle_chunk(section_text))
            
            if chunks:
                self.validate_chunks(chunks)
                return chunks
        
        # Try to detect table structures (for Excel/CSV)
        if '|' in text or '\t' in text:
            table_chunks = self._split_tables(text)
            if table_chunks:
                self.validate_chunks(table_chunks)
                return table_chunks
        
        # Fallback to recursive splitting
        if self._fallback_splitter:
            return self._fallback_splitter.split_text(text)
        
        # Last resort: single chunk
        return [text]
    
    def _handle_chunk(self, text: str) -> List[str]:
        """Handle a chunk that might need further splitting.
        
        Args:
            text: Text to process.
            
        Returns:
            List of processed chunks.
        """
        if len(text) <= self.max_chunk_size:
            return [text]
        
        # Split large chunks
        if self._fallback_splitter:
            return self._fallback_splitter.split_text(text)
        
        # Manually split if no fallback
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.max_chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap
        
        return chunks
    
    def _split_tables(self, text: str) -> List[str]:
        """Split table-structured text.
        
        Args:
            text: Text containing table data.
            
        Returns:
            List of table rows/chunks.
        """
        chunks = []
        
        # Split by lines first
        lines = text.split('\n')
        
        current_chunk = []
        current_length = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if it's a table row (contains | or \t)
            is_table_row = '|' in line or '\t' in line
            
            if is_table_row:
                current_chunk.append(line)
                current_length += len(line)
                
                if current_length >= self.min_section_length:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
            else:
                # Non-table content
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                current_chunk.append(line)
                current_length += len(line)
                
                if current_length >= self.max_chunk_size:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
        
        # Add remaining
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return [c for c in chunks if c.strip()]


class StructuredSplitterWithParser(StructuredSplitter):
    """Extended structured splitter that works directly with ParsedDocument.
    
    This variant can accept ParsedDocument objects and use their full
    structure (pages, sections) for intelligent chunking.
    
    Example:
        >>> from src.agent.parsers import DocumentParser
        >>> from src.libs.splitter import StructuredSplitterWithParser
        >>> 
        >>> parser = DocumentParser()
        >>> doc = parser.parse("document.docx")
        >>> 
        >>> splitter = StructuredSplitterWithParser(settings)
        >>> chunks = splitter.split_parsed_document(doc)
    """
    
    def split_parsed_document(self, parsed_doc: Any) -> List[str]:
        """Split a ParsedDocument using its structure.
        
        Args:
            parsed_doc: ParsedDocument object from DocumentParser.
            
        Returns:
            List of text chunks.
        """
        chunks = []
        
        # Use sections if available
        if parsed_doc.sections and len(parsed_doc.sections) > 0:
            chunks.extend(self._split_by_sections(parsed_doc.sections))
        # Otherwise use pages
        elif parsed_doc.pages and len(parsed_doc.pages) > 0:
            for page in parsed_doc.pages:
                page_text = page.text if hasattr(page, 'text') else str(page)
                if page_text and page_text.strip():
                    chunks.extend(self._handle_chunk(page_text.strip()))
        
        # Fallback to full text
        if not chunks:
            full_text = "\n\n".join([
                s.text for s in (parsed_doc.sections or [])
            ])
            if not full_text:
                full_text = "\n\n".join([
                    p.text for p in (parsed_doc.pages or [])
                ])
            chunks = [full_text] if full_text else []
        
        # Validate
        if not chunks:
            return [""]
        
        self.validate_chunks(chunks)
        return chunks


__all__ = [
    "StructuredSplitter",
    "StructuredSplitterWithParser",
]

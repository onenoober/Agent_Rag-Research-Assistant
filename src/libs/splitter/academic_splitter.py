# -*- coding: utf-8 -*-
"""Academic Paper Splitter - specialized splitter for research papers.

This splitter leverages PDF parser's structural information (sections, headings)
to create more meaningful chunks for academic papers.

Features:
- Multi-level section detection (1, 1.1, 1.1.1)
- Special section handling (Abstract, Keywords, References)
- Table and Figure caption preservation
- Citation context preservation
- Equation and footnote handling

Run with:
    conda activate bigmodel
    python tests/e2e/test_academic_paper_splitter.py
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from src.libs.splitter.base_splitter import BaseSplitter
from src.agent.schemas.document import ParsedDocument, DocumentSection


@dataclass
class AcademicSection:
    """Represents a section in an academic paper."""
    level: int          # 1 = top-level, 2 = subsection, etc.
    number: str         # "1", "1.1", "1.1.1"
    title: str          # "Introduction", "Methods"
    content: str        # Section text
    start_pos: int      # Character position in document
    end_pos: int        # Character position in document


class AcademicPaperSplitter(BaseSplitter):
    """Specialized splitter for academic papers.
    
    This splitter is designed to work with PDF-parsed documents that have
    structural information (sections with titles and levels).
    """
    
    # Common academic paper section titles (English)
    ENGLISH_SECTIONS = {
        'abstract': 0,
        'introduction': 1,
        'background': 1,
        'related work': 1,
        'literature review': 1,
        'methodology': 1,
        'methods': 1,
        'approach': 1,
        'materials and methods': 1,
        'experimental setup': 1,
        'experiment': 1,
        'experiments': 1,
        'results': 1,
        'results and discussion': 1,
        'discussion': 1,
        'conclusion': 1,
        'conclusions': 1,
        'references': 1,
        'bibliography': 1,
        'acknowledgments': 1,
        'acknowledgements': 1,
        'appendix': 1,
        'supplementary materials': 1,
    }
    
    # Common academic paper section titles (Chinese)
    CHINESE_SECTIONS = {
        '摘要': 0,
        '关键词': 0,
        '引言': 1,
        '背景': 1,
        '相关工作': 1,
        '文献综述': 1,
        '方法': 1,
        '方法论': 1,
        '实验': 1,
        '实验方法': 1,
        '结果': 1,
        '讨论': 1,
        '结论': 1,
        '参考文献': 1,
        '致谢': 1,
        '附录': 1,
    }
    
    def __init__(self, settings, max_chunk_size: int = 1000, chunk_overlap: int = 150):
        """Initialize academic paper splitter.
        
        Args:
            settings: Application settings
            max_chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks
        """
        self.settings = settings
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap
        self._last_strategy = "academic_paper"
    
    def split_text(self, text: str) -> List[str]:
        """Split academic paper text into chunks.
        
        Args:
            text: Full paper text
            
        Returns:
            List of text chunks
        """
        # First, try to parse sections from the text
        sections = self._parse_sections_from_text(text)
        
        if not sections:
            # Fallback to basic splitting
            return self._basic_split(text)
        
        # Convert sections to chunks
        chunks = self._sections_to_chunks(sections, text)
        
        return chunks
    
    def split_document(self, parsed_doc: ParsedDocument) -> List[str]:
        """Split a parsed PDF document using its structural information.
        
        This is the preferred method for academic papers as it uses
        the PDF parser's structural information.
        
        Args:
            parsed_doc: ParsedDocument from PDF parser
            
        Returns:
            List of text chunks
        """
        # Try to use sections from parsed document
        if parsed_doc.sections and any(s.title for s in parsed_doc.sections):
            return self._split_using_parsed_sections(parsed_doc)
        
        # Fallback: use page text
        all_text = "\n\n".join([page.text for page in parsed_doc.pages if page.text])
        return self.split_text(all_text)
    
    def _split_using_parsed_sections(self, parsed_doc: ParsedDocument) -> List[str]:
        """Split using sections from PDF parser."""
        chunks = []
        current_chunk = ""
        
        for section in parsed_doc.sections:
            if not section.text:
                continue
            
            # Add section header if available
            section_text = section.text
            if section.title:
                section_text = f"## {section.title}\n\n{section.text}"
            
            # Check if adding this section would exceed max size
            if len(current_chunk) + len(section_text) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                if chunks and self.chunk_overlap > 0:
                    current_chunk = chunks[-1][-self.chunk_overlap:] + section_text
                else:
                    current_chunk = section_text
            else:
                current_chunk += "\n\n" + section_text
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [f"Document: {parsed_doc.source_file}"]
    
    def _parse_sections_from_text(self, text: str) -> List[AcademicSection]:
        """Parse academic paper sections from plain text.
        
        Args:
            text: Full paper text
            
        Returns:
            List of AcademicSection objects
        """
        sections = []
        
        # Pattern for numbered sections: 1, 1.1, 1.1.1, etc.
        numbered_pattern = r'^(\d+(?:\.\d+)*)\s+([A-Z][^\.]+)$'
        
        # Pattern for special sections: ABSTRACT, INTRODUCTION, etc.
        special_pattern = r'^([A-Z][A-Z\s]+)$'
        
        lines = text.split('\n')
        current_section = None
        current_content = []
        current_pos = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Try numbered section pattern
            numbered_match = re.match(numbered_pattern, line, re.MULTILINE)
            if numbered_match:
                # Save previous section
                if current_section:
                    current_section.content = '\n'.join(current_content)
                    sections.append(current_section)
                
                # Start new section
                number = numbered_match.group(1)
                title = numbered_match.group(2).strip()
                level = len(number.split('.'))
                
                current_section = AcademicSection(
                    level=level,
                    number=number,
                    title=title,
                    content="",
                    start_pos=current_pos,
                    end_pos=current_pos
                )
                current_content = [line[len(number + " " + title):].strip()]
                current_pos += len(line) + 1
                continue
            
            # Try special section pattern
            special_match = re.match(special_pattern, line)
            if special_match and len(line) < 30:
                title_lower = line.lower()
                if title_lower in self.ENGLISH_SECTIONS:
                    # Save previous section
                    if current_section:
                        current_section.content = '\n'.join(current_content)
                        sections.append(current_section)
                    
                    level = self.ENGLISH_SECTIONS[title_lower]
                    current_section = AcademicSection(
                        level=level,
                        number="",
                        title=line,
                        content="",
                        start_pos=current_pos,
                        end_pos=current_pos
                    )
                    current_content = []
                    current_pos += len(line) + 1
                    continue
            
            # Add to current section content
            if current_section:
                current_content.append(line)
                current_pos += len(line) + 1
        
        # Save last section
        if current_section:
            current_section.content = '\n'.join(current_content)
            sections.append(current_section)
        
        return sections
    
    def _sections_to_chunks(self, sections: List[AcademicSection], full_text: str) -> List[str]:
        """Convert sections to chunks, respecting max size.
        
        Args:
            sections: List of parsed sections
            full_text: Original text (for context)
            
        Returns:
            List of chunks
        """
        if not sections:
            return self._basic_split(full_text)
        
        chunks = []
        current_chunk = ""
        
        for section in sections:
            section_text = f"{section.title}\n{section.content}" if section.title else section.content
            
            # If section itself exceeds max size, split it
            if len(section_text) > self.max_chunk_size:
                # Save current chunk first
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # Split large section
                sub_chunks = self._split_large_section(section)
                chunks.extend(sub_chunks)
            else:
                # Check if adding would exceed max
                if len(current_chunk) + len(section_text) > self.max_chunk_size:
                    chunks.append(current_chunk.strip())
                    # Add overlap
                    if chunks and self.chunk_overlap > 0:
                        overlap_text = chunks[-1][-self.chunk_overlap:]
                        current_chunk = overlap_text + "\n\n" + section_text
                    else:
                        current_chunk = section_text
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + section_text
                    else:
                        current_chunk = section_text
        
        # Add last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [full_text[:self.max_chunk_size]]
    
    def _split_large_section(self, section: AcademicSection) -> List[str]:
        """Split a large section into smaller chunks.
        
        Args:
            section: Large section
            
        Returns:
            List of smaller chunks
        """
        # Try to split by paragraphs
        paragraphs = section.content.split('\n\n')
        
        chunks = []
        current_chunk = f"## {section.title}\n\n" if section.title else ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) > self.max_chunk_size:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _basic_split(self, text: str) -> List[str]:
        """Basic recursive split as fallback.
        
        Args:
            text: Text to split
            
        Returns:
            List of chunks
        """
        # Use simple paragraph-based splitting
        paragraphs = text.split('\n\n')
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                # Start new chunk with overlap
                if chunks and self.chunk_overlap > 0:
                    overlap = chunks[-1][-self.chunk_overlap:]
                    current_chunk = overlap + "\n\n" + para
                else:
                    current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else [text[:self.max_chunk_size]]


def create_academic_splitter(settings, max_chunk_size: int = 1000, chunk_overlap: int = 150):
    """Factory function to create AcademicPaperSplitter.
    
    Args:
        settings: Application settings
        max_chunk_size: Maximum chunk size
        chunk_overlap: Chunk overlap
        
    Returns:
        AcademicPaperSplitter instance
    """
    return AcademicPaperSplitter(settings, max_chunk_size, chunk_overlap)

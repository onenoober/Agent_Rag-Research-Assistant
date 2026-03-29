"""Smart Splitter - Intelligent document chunking with automatic strategy detection.

This splitter automatically detects the best chunking strategy based on the 
document's structure:
1. TOC (Table of Contents) - section-based chunking
2. Markdown headings - heading-based chunking  
3. Numbered sections - numbered list chunking
4. Tables - table-aware chunking
5. Fallback - recursive chunking

This provides the best of both worlds: specialized handling for structured
documents while maintaining compatibility with unstructured ones.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional

from src.libs.splitter.base_splitter import BaseSplitter


class SmartSplitter(BaseSplitter):
    """Smart document splitter with automatic strategy detection.

    This splitter analyzes the document structure and automatically selects
    the most appropriate chunking strategy. It is optimized for general-purpose
    documents (not academic papers).

    Priority order:
    1. TOC-based (if available via metadata)
    2. JSON/Config files
    3. Code blocks
    4. Markdown headings (# Header)
    5. Numbered sections (1.2.3, Section 1, etc.)
    6. Table structures
    7. Recursive fallback

    Features:
    - min_chunk_size protection: merges too-small chunks with neighbors
    - Chinese-optimized separators in recursive fallback

    Note: For academic papers, use AcademicPaperSplitter instead for better results.

    Attributes:
        max_chunk_size: Maximum size of each chunk (default: 500)
        min_chunk_size: Minimum size of each chunk (default: 200)
        chunk_overlap: Overlap between chunks (default: 50)
        min_section_length: Minimum section length to keep (default: 50)

    Example:
        >>> from src.libs.splitter import SmartSplitter
        >>> from src.core.settings import load_settings
        >>>
        >>> settings = load_settings("config/settings.yaml")
        >>> splitter = SmartSplitter(settings)
        >>>
        >>> # Smart detection - automatically chooses best strategy
        >>> chunks = splitter.split_text(document_text)
    """

    def __init__(
        self,
        settings: Any,
        max_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_section_length: int = 50,
        **kwargs: Any,
    ) -> None:
        """Initialize SmartSplitter.

        Args:
            settings: Application settings containing ingestion configuration.
            max_chunk_size: Maximum chunk size.
            chunk_overlap: Overlap between chunks.
            min_section_length: Minimum section length for structure detection.
            **kwargs: Additional parameters.
        """
        self.settings = settings

        # Extract configuration
        try:
            ingestion_config = settings.ingestion
            self.max_chunk_size = max_chunk_size if max_chunk_size is not None else ingestion_config.chunk_size
            self.chunk_overlap = chunk_overlap if chunk_overlap is not None else ingestion_config.chunk_overlap
            self.min_chunk_size = getattr(ingestion_config, 'min_chunk_size', 200) if ingestion_config else 200
        except AttributeError:
            self.max_chunk_size = max_chunk_size or 500
            self.chunk_overlap = chunk_overlap or 50
            self.min_chunk_size = 200

        self.min_section_length = min_section_length

        # Initialize fallback splitter
        self._recursive_splitter = self._create_recursive_splitter()

        # Track which strategy was used
        self._last_strategy: Optional[str] = None
    
    def _create_recursive_splitter(self) -> Optional[BaseSplitter]:
        """Create recursive splitter as fallback."""
        try:
            from src.libs.splitter.recursive_splitter import RecursiveSplitter
            return RecursiveSplitter(
                settings=self.settings,
                chunk_size=self.max_chunk_size,
                chunk_overlap=self.chunk_overlap
            )
        except ImportError:
            return None

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """Merge chunks that are smaller than min_chunk_size with neighbors.

        This method ensures that no chunk is smaller than min_chunk_size by:
        1. Finding chunks below the threshold
        2. Merging them with the previous chunk (if exists)
        3. If no previous chunk, merging with the next chunk
        4. If isolated (first and last), keeping as-is

        Args:
            chunks: List of text chunks to process.

        Returns:
            List of chunks with small chunks merged.
        """
        if not chunks or len(chunks) <= 1:
            return chunks

        result = []
        i = 0

        while i < len(chunks):
            chunk = chunks[i]
            chunk_len = len(chunk.strip())

            # If chunk is large enough, keep it
            if chunk_len >= self.min_chunk_size:
                result.append(chunk)
                i += 1
                continue

            # Chunk is too small - try to merge
            merged = chunk

            # Try to merge with previous chunk
            if result:
                prev_chunk = result[-1]
                prev_len = len(prev_chunk.strip())
                combined_len = len((prev_chunk + "\n" + merged).strip())

                # Check if merged chunk would still be reasonable
                if combined_len <= self.max_chunk_size * 1.5:
                    # Replace previous with merged
                    result[-1] = prev_chunk + "\n" + merged
                    i += 1
                    continue
                elif chunk_len < self.min_chunk_size // 2:
                    # Very small chunk: force merge with previous
                    result[-1] = prev_chunk + "\n" + merged
                    i += 1
                    continue

            # Try to merge with next chunk
            if i + 1 < len(chunks):
                next_chunk = chunks[i + 1]
                next_len = len(next_chunk.strip())
                combined_len = len((merged + "\n" + next_chunk).strip())

                # Check if merged chunk would still be reasonable
                if combined_len <= self.max_chunk_size * 1.5:
                    # Skip current, merge next into current
                    result.append(merged + "\n" + next_chunk)
                    i += 2
                    continue
                elif chunk_len < self.min_chunk_size // 2:
                    # Very small chunk: force merge with next
                    result.append(merged + "\n" + next_chunk)
                    i += 2
                    continue

            # Cannot merge (would exceed max), keep as-is
            result.append(chunk)
            i += 1

        return result
    
    def split_text(
        self,
        text: str,
        trace: Optional[Any] = None,
        metadata: Optional[dict] = None,
        toc: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Split text using the most appropriate strategy.
        
        Args:
            text: Input text to split.
            trace: Optional TraceContext for observability.
            metadata: Optional document metadata (may contain toc, title, etc.)
            toc: Optional Table of Contents list from PDF/Word parser.
            **kwargs: Additional parameters.
        
        Returns:
            A list of text chunks based on best strategy detection.
        """
        self.validate_text(text)
        
        # Extract TOC from metadata if not provided directly
        if toc is None and metadata:
            toc = metadata.get("toc")
        
        # Strategy 1: TOC-based (highest priority)
        if toc and len(toc) > 0:
            self._last_strategy = "toc"
            return self._split_by_toc(text, toc, metadata)
        
        # Strategy 2: JSON/Config file (MUST be before code detection)
        if self._is_json_config(text):
            self._last_strategy = "json_config"
            return self._split_json_config(text)
        
        # Strategy 3: Code blocks detection (``` or indented code)
        if self._has_code_blocks(text):
            self._last_strategy = "code"
            return self._split_with_code_blocks(text)
        
        # Strategy 4: Markdown headings
        if self._has_markdown_headings(text):
            self._last_strategy = "markdown"
            return self._split_by_markdown_headings(text)
        
        # Strategy 5: Numbered sections (generic numbered lists)
        if self._has_numbered_sections(text):
            self._last_strategy = "numbered"
            return self._split_by_numbered_sections(text)
        
        # Strategy 6: Table structures
        if self._has_tables(text):
            self._last_strategy = "table"
            return self._split_with_tables(text)
        
        # Fallback: Recursive splitting
        self._last_strategy = "recursive"
        chunks = self._split_recursive(text)

        # Apply min_chunk_size protection: merge small chunks with neighbors
        chunks = self._merge_small_chunks(chunks)
        return chunks
    
    @property
    def strategy_used(self) -> Optional[str]:
        """Get the last used chunking strategy."""
        return self._last_strategy
    
    def detect_document_type(self, text: str) -> str:
        """Detect the document type based on content.
        
        This method analyzes the text and returns the most likely document type,
        which can be used to select appropriate processing strategies.
        
        Args:
            text: Input text to analyze.
            
        Returns:
            Document type: 'toc', 'code', 'json_config', 'markdown', 
                          'numbered', 'academic', 'table', or 'plain'
        """
        # Check in priority order (same as split_text)
        
        # 1. TOC-based
        if re.search(r'^第[一二三四五六七八九十\d]+\s+[章篇部]\s', text, re.MULTILINE):
            return 'toc'
        
        # 2. JSON/Config (must be before code detection)
        if self._is_json_config(text):
            return 'json_config'
        
        # 4. Code blocks
        if self._has_code_blocks(text):
            return 'code'
        
        # 5. Markdown headings
        if self._has_markdown_headings(text):
            return 'markdown'
        
        # 6. Numbered sections (generic numbered lists)
        if self._has_numbered_sections(text):
            return 'numbered'
        
        # 7. Tables
        if self._has_tables(text):
            return 'table'
        
        # Default: plain text
        return 'plain'
    
    def _split_by_toc(
        self, 
        text: str, 
        toc: List[dict],
        metadata: Optional[dict] = None
    ) -> List[str]:
        """Split by Table of Contents.
        
        Args:
            text: Full document text.
            toc: List of TOC entries with title, level, page.
            metadata: Optional metadata.
            
        Returns:
            List of chunks based on TOC sections.
        """
        chunks = []
        
        # Sort TOC by position/page
        sorted_toc = sorted(toc, key=lambda x: x.get("page", x.get("position", 0)))
        
        for i, entry in enumerate(sorted_toc):
            title = entry.get("title", "")
            level = entry.get("level", 1)
            
            # Extract content for this section
            start_pos = entry.get("position", 0)
            end_pos = sorted_toc[i + 1].get("position", len(text)) if i + 1 < len(sorted_toc) else len(text)
            
            section_text = text[start_pos:end_pos].strip()
            
            if len(section_text) > self.max_chunk_size:
                # Split large sections
                sub_chunks = self._split_recursive(section_text)
                for j, sub in enumerate(sub_chunks):
                    chunks.append(self._add_section_context(sub, title, level))
            elif section_text:
                chunks.append(self._add_section_context(section_text, title, level))
        
        # If TOC didn't produce valid chunks, fallback
        if not chunks or not any(c.strip() for c in chunks):
            return self._split_recursive(text)

        self.validate_chunks(chunks)

        # Apply min_chunk_size protection
        chunks = self._merge_small_chunks(chunks)
        return chunks
    
    def _add_section_context(self, text: str, title: str, level: int) -> str:
        """Add section context to chunk.
        
        Args:
            text: Chunk text.
            title: Section title.
            level: Section level.
            
        Returns:
            Text with context prefix.
        """
        if title:
            prefix = f"[{title}] " if level <= 2 else f"[{title}] "
            return prefix + text
        return text
    
    def _split_by_markdown_headings(self, text: str) -> List[str]:
        """Split by Markdown headings (# Header).
        
        Args:
            text: Input text with Markdown headings.
            
        Returns:
            List of chunks by heading sections.
        """
        chunks = []
        
        # Match Markdown headings: # to ######
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        matches = list(heading_pattern.finditer(text))
        
        if not matches:
            return self._split_recursive(text)
        
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            heading_level = len(match.group(1))
            heading_text = match.group(2).strip()
            
            section_text = text[start:end].strip()
            
            if len(section_text) <= self.max_chunk_size:
                chunks.append(section_text)
            else:
                # Split large sections
                sub_chunks = self._split_recursive(section_text)
                for sub in sub_chunks:
                    chunks.append(sub)
        
        if not chunks:
            return self._split_recursive(text)

        self.validate_chunks(chunks)

        # Apply min_chunk_size protection
        chunks = self._merge_small_chunks(chunks)
        return chunks

    def _split_by_numbered_sections(self, text: str) -> List[str]:
        """Split by numbered sections (1., 1.2, Section 1, etc.).
        
        Args:
            text: Input text with numbered sections.
            
        Returns:
            List of chunks by numbered sections.
        """
        chunks = []
        
        # Pattern for numbered sections (order matters - more specific first):
        # 1. Arabic numbers: 1. 1.1 1.1.1 etc.
        # 2. Chinese section headers: 第一章 第二节 第三部分
        # 3. Chinese chapter style: 一、 二、 三、 (no space after 、)
        numbered_pattern = re.compile(
            r'^((\d+\.)+)\s+(.+)$|^(第[一二三四五六七八九十百千]+[章节部分篇])\s*[:：]?\s*(.*)$|^([一二三四五六七八九十百千]+、)\s*(.+)$',
            re.MULTILINE
        )
        
        matches = list(numbered_pattern.finditer(text))
        
        if not matches:
            return self._split_recursive(text)
        
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

            section_text = text[start:end].strip()

            if len(section_text) <= self.max_chunk_size:
                chunks.append(section_text)
            else:
                sub_chunks = self._split_recursive(section_text)
                chunks.extend(sub_chunks)

        if not chunks:
            return self._split_recursive(text)

        self.validate_chunks(chunks)

        # Apply min_chunk_size protection
        chunks = self._merge_small_chunks(chunks)
        return chunks

    def _is_academic_paper(self, text: str) -> bool:
        """Detect if text is an academic paper.
        
        Checks for common academic paper sections (English and Chinese):
        - English: Abstract, Introduction, Methods, Results, Discussion, Conclusion, References
        - Chinese: 摘要, 引言, 方法, 结果, 讨论, 结论, 参考文献
        
        Args:
            text: Input text to check.
            
        Returns:
            True if likely an academic paper.
        """
        # Look for common academic paper keywords (English)
        english_keywords = [
            r'\babstract\b',
            r'\bintroduction\b', 
            r'\bmethods?\b',
            r'\bmethodology\b',
            r'\bresults?\b',
            r'\bdiscussion\b',
            r'\bconclusion\b',
            r'\breferences\b',
            r'\bliterature review\b',
            r'\brelated work\b',
            r'\backnowledgements?\b',
            r'\bbackground\b',
        ]
        
        # Look for Chinese academic paper keywords
        chinese_keywords = [
            r'摘要[:：]',
            r'引言[:：]|引言\b',
            r'方法[:：]|方法论\b',
            r'结果[:：]',
            r'讨论[:：]',
            r'结论[:：]',
            r'参考文献[:：]',
            r'文献综述\b',
            r'相关工作\b',
            r'实验\b',
            r'背景介绍\b',
        ]
        
        matches = 0
        
        # Check English keywords
        for pattern in english_keywords:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
        
        # Check Chinese keywords (higher weight for Chinese academic papers)
        for pattern in chinese_keywords:
            if re.search(pattern, text):
                matches += 2  # Chinese keywords have higher weight
        
        # If 2+ matches (or 1+ Chinese), likely an academic paper
        return matches >= 2
    
    def _split_academic_paper(self, text: str) -> List[str]:
        """Split academic paper by standard sections.
        
        Supports both English and Chinese academic paper structures.
        
        Args:
            text: Academic paper text.
            
        Returns:
            List of chunks by academic sections.
        """
        chunks = []
        
        # Define English academic paper sections with regex patterns
        english_sections = [
            ("abstract", re.compile(r'\babstract\b[:\s]*(.*?)(?=\n\n|\n[introduction]|introduction)', re.IGNORECASE | re.DOTALL)),
            ("introduction", re.compile(r'\bintroduction\b[:\s]*(.*?)(?=\n\n|\n[12345]\.|\nmethod|\nresults|\ndiscussion|\nconclusion)', re.IGNORECASE | re.DOTALL)),
            ("methods", re.compile(r'\b(methods?|methodology)\b[:\s]*(.*?)(?=\n\n|\n[12345]\.|\nresult|\ndiscussion|\nconclusion)', re.IGNORECASE | re.DOTALL)),
            ("results", re.compile(r'\bresults?\b[:\s]*(.*?)(?=\n\n|\n[12345]\.|\ndiscussion|\nconclusion)', re.IGNORECASE | re.DOTALL)),
            ("discussion", re.compile(r'\bdiscussion\b[:\s]*(.*?)(?=\n\n|\n[12345]\.|\nconclusion|\nreferences)', re.IGNORECASE | re.DOTALL)),
            ("conclusion", re.compile(r'\bconclusion\b[:\s]*(.*?)(?=\n\n|\nreferences)', re.IGNORECASE | re.DOTALL)),
            ("references", re.compile(r'\breferences\b[:\s]*(.*)', re.IGNORECASE | re.DOTALL)),
        ]
        
        # Define Chinese academic paper sections with regex patterns
        chinese_sections = [
            ("摘要", re.compile(r'(?:^|\n)摘要[:：]\s*(.*?)(?=\n\n(?:引言|背景|方法|结果|讨论|结论|参考文献)|$)', re.DOTALL)),
            ("引言", re.compile(r'(?:^|\n)引言[:：]\s*(.*?)(?=\n\n(?:背景|方法|实验|结果|讨论|结论|参考文献)|$)', re.DOTALL)),
            ("背景", re.compile(r'(?:^|\n)背景[:：]\s*(.*?)(?=\n\n(?:引言|方法|实验|结果|讨论|结论|参考文献)|$)', re.DOTALL)),
            ("方法", re.compile(r'(?:^|\n)(?:方法|方法论)[:：]\s*(.*?)(?=\n\n(?:背景|引言|实验|结果|讨论|结论|参考文献)|$)', re.DOTALL)),
            ("实验", re.compile(r'(?:^|\n)实验[:：]\s*(.*?)(?=\n\n(?:方法|结果|讨论|结论|参考文献)|$)', re.DOTALL)),
            ("结果", re.compile(r'(?:^|\n)结果[:：]\s*(.*?)(?=\n\n(?:方法|实验|讨论|结论|参考文献)|$)', re.DOTALL)),
            ("讨论", re.compile(r'(?:^|\n)讨论[:：]\s*(.*?)(?=\n\n(?:结果|结论|参考文献)|$)', re.DOTALL)),
            ("结论", re.compile(r'(?:^|\n)结论[:：]\s*(.*?)(?=\n\n(?:参考文献)|$)', re.DOTALL)),
            ("参考文献", re.compile(r'(?:^|\n)参考文献[:：]\s*(.*)', re.DOTALL)),
        ]
        
        # Try English sections first
        for section_name, pattern in english_sections:
            match = pattern.search(text)
            if match:
                section_text = match.group(1).strip() if match.lastindex else match.group(0).strip()
                
                if section_text and len(section_text) >= self.min_section_length:
                    if len(section_text) <= self.max_chunk_size:
                        chunks.append(f"[{section_name.upper()}] {section_text}")
                    else:
                        sub_chunks = self._split_recursive(section_text)
                        for sub in sub_chunks:
                            chunks.append(f"[{section_name.upper()}] {sub}")
        
        # If no English sections found, try Chinese
        if not chunks:
            for section_name, pattern in chinese_sections:
                match = pattern.search(text)
                if match:
                    section_text = match.group(1).strip() if match.lastindex else match.group(0).strip()
                    
                    if section_text and len(section_text) >= self.min_section_length:
                        if len(section_text) <= self.max_chunk_size:
                            chunks.append(f"[{section_name}] {section_text}")
                        else:
                            sub_chunks = self._split_recursive(section_text)
                            for sub in sub_chunks:
                                chunks.append(f"[{section_name}] {sub}")
        
        # If no sections found, fallback
        if not chunks:
            return self._split_recursive(text)
        
        self.validate_chunks(chunks)
        return chunks
    
    def _split_with_tables(self, text: str) -> List[str]:
        """Split text while preserving table structures.
        
        Args:
            text: Text containing tables.
            
        Returns:
            List of chunks preserving tables.
        """
        chunks = []
        
        lines = text.split('\n')
        current_chunk_lines = []
        current_length = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            is_table_row = '|' in line or '\t' in line
            
            if is_table_row:
                # Add table row to current chunk
                current_chunk_lines.append(line)
                current_length += len(line)
                
                # Keep table rows together
                if current_length >= self.min_section_length:
                    chunk = '\n'.join(current_chunk_lines)
                    chunks.append(chunk)
                    current_chunk_lines = []
                    current_length = 0
            else:
                # Non-table content
                if current_chunk_lines:
                    # Flush table chunk
                    chunks.append('\n'.join(current_chunk_lines))
                    current_chunk_lines = []
                    current_length = 0
                
                # Add text line
                current_chunk_lines.append(line)
                current_length += len(line)
                
                if current_length >= self.max_chunk_size:
                    chunk = '\n'.join(current_chunk_lines)
                    chunks.append(chunk)
                    current_chunk_lines = []
                    current_length = 0
        
        # Flush remaining
        if current_chunk_lines:
            chunks.append('\n'.join(current_chunk_lines))
        
        if not chunks:
            return self._split_recursive(text)

        self.validate_chunks(chunks)

        # Apply min_chunk_size protection
        chunks = self._merge_small_chunks(chunks)
        return chunks

    def _split_recursive(self, text: str) -> List[str]:
        """Use recursive splitter as fallback.
        
        Args:
            text: Input text.
            
        Returns:
            List of chunks from recursive splitter.
        """
        if self._recursive_splitter:
            return self._recursive_splitter.split_text(text)
        
        # Manual fallback if no recursive splitter
        return self._manual_split(text)
    
    def _manual_split(self, text: str) -> List[str]:
        """Manual chunking as last resort.
        
        Args:
            text: Input text.
            
        Returns:
            List of manually split chunks.
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.max_chunk_size, len(text))
            
            # Try to break at paragraph boundary
            if end < len(text):
                # Find last paragraph break
                last_break = max(
                    text.rfind('\n\n', start, end),
                    text.rfind('\n', start, end)
                )
                if last_break > start:
                    end = last_break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap if end < len(text) else end
        
        return chunks if chunks else [text]
    
    # ─────────────────────────────────────────────────────────────
    # Detection helpers
    # ─────────────────────────────────────────────────────────────
    
    def _has_code_blocks(self, text: str) -> bool:
        """Check if text contains code blocks (``` or indented code).
        
        Args:
            text: Input text to check.
            
        Returns:
            True if text contains code blocks.
        """
        # Check for fenced code blocks (```)
        fenced_pattern = re.compile(r'^```[\w]*\s*[\s\S]*?^```', re.MULTILINE)
        fenced_matches = len(fenced_pattern.findall(text))
        
        # If fenced code blocks found, definitely code
        if fenced_matches >= 1:
            return True
        
        # Check for indented code (4+ spaces at start of line) - but NOT JSON
        # Skip this for JSON-like content to avoid false positives
        if text.strip().startswith('{') or text.strip().startswith('['):
            return False
            
        indented_lines = 0
        lines = text.split('\n')
        for line in lines:
            if line.startswith('    ') or line.startswith('\t'):
                indented_lines += 1
        
        # If significant code blocks found
        return indented_lines >= 3 and indented_lines / len(lines) > 0.2 if lines else False
    
    def _split_with_code_blocks(self, text: str) -> List[str]:
        """Split text while preserving code blocks as separate chunks.
        
        Args:
            text: Text containing code blocks.
            
        Returns:
            List of chunks with code blocks preserved.
        """
        chunks = []
        
        # Pattern for fenced code blocks
        fenced_pattern = re.compile(r'(^```[\w]*\s*[\s\S]*?^```)', re.MULTILINE)
        
        last_end = 0
        for match in fenced_pattern.finditer(text):
            # Add text before the code block
            if match.start() > last_end:
                pre_text = text[last_end:match.start()].strip()
                if pre_text:
                    chunks.extend(self._split_recursive(pre_text))
            
            # Add the code block as a single chunk
            code_block = match.group(1).strip()
            if code_block:
                chunks.append(code_block)
            
            last_end = match.end()
        
        # Add remaining text after last code block
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining:
                chunks.extend(self._split_recursive(remaining))

        if not chunks:
            return self._split_recursive(text)

        self.validate_chunks(chunks)

        # Apply min_chunk_size protection (skip for code blocks)
        chunks = self._merge_small_chunks(chunks)
        return chunks

    def _is_legal_document(self, text: str) -> bool:
        """Detect if text is a legal document (Chinese law/contract/English legal).
        
        Checks for common legal document patterns:
        - Chinese: 第X条, 第X款, 第X项, 甲方, 乙方
        - English: Article X:, Section X:, Party A, Party B
        
        Args:
            text: Input text to check.
            
        Returns:
            True if likely a legal document.
        """
        # Chinese legal patterns (with higher weight)
        chinese_patterns = [
            r'第[一二三四五六七八九十\d]+条',       # Article X (条)
            r'第[一二三四五六七八九十\d]+款',       # Paragraph X (款)
            r'第[一二三四五六七八九十\d]+项',       # Item X (项)
            r'甲方\s*[:：]',                       # Party A
            r'乙方\s*[:：]',                       # Party B
            r'签订日期[:：]?\s*\d{4}',            # Signing date
            r'协议\s*[:：]',                      # Agreement
            r'出租人\s*[:：]',                    # Lessor
            r'承租人\s*[:：]',                    # Lessee
            r'违约责任\s*[:：]',                   # Default liability
            r'争议解决\s*[:：]',                   # Dispute resolution
        ]
        
        # English legal patterns
        english_patterns = [
            r'Article\s+\d+[:\s]',
            r'Section\s+\d+[:\s]',
            r'Party\s+[A-Z]\s*[:\(]',
            r'Lessor\s*[:\s]',
            r'Lessee\s*[:\s]',
            r'Agreement\s*[:\s]',
            r'Default\s*[:\s]',
            r'Dispute\s+Resolution',
        ]
        
        matches = 0
        
        # Check Chinese patterns (with higher weight)
        for pattern in chinese_patterns:
            if re.search(pattern, text):
                matches += 2
        
        # Check English patterns
        for pattern in english_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
        
        # If 2+ matches, likely a legal document
        return matches >= 2
    
    def _split_legal_document(self, text: str) -> List[str]:
        """Split legal document by articles and paragraphs.
        
        Supports both Chinese (第X条) and English (Article X:) patterns.
        
        Args:
            text: Legal document text.
            
        Returns:
            List of chunks by legal sections.
        """
        chunks = []
        
        # Try Chinese pattern first: 第X条
        chinese_pattern = re.compile(
            r'(第[一二三四五六七八九十\d]+条[^\n]*(?:\n(?!第[一二三四五六七八九十\d]+条)[^\n]*)*)',
            re.MULTILINE
        )
        
        matches = list(chinese_pattern.finditer(text))
        
        # Try English pattern: Article X: or Section X:
        if not matches:
            english_pattern = re.compile(
                r'(Article\s+\d+[:\s][^\n]*(?:\n(?!Article\s+\d+[:\s])[^\n]*)*)',
                re.IGNORECASE | re.MULTILINE
            )
            matches = list(english_pattern.finditer(text))
        
        # Try Section pattern
        if not matches:
            section_pattern = re.compile(
                r'(Section\s+\d+[:\s][^\n]*(?:\n(?!Section\s+\d+[:\s])[^\n]*)*)',
                re.IGNORECASE | re.MULTILINE
            )
            matches = list(section_pattern.finditer(text))
        
        if matches:
            for match in matches:
                section_text = match.group(1).strip()
                
                if len(section_text) <= self.max_chunk_size:
                    chunks.append(section_text)
                else:
                    # Split large sections
                    sub_chunks = self._split_recursive(section_text)
                    chunks.extend(sub_chunks)
        
        if not chunks:
            return self._split_recursive(text)
        
        self.validate_chunks(chunks)
        return chunks
    
    def _is_json_config(self, text: str) -> bool:
        """Detect if text is a JSON or config file.
        
        Args:
            text: Input text to check.
            
        Returns:
            True if likely a JSON/config file.
        """
        text = text.strip()
        
        # Check if starts with { or [
        if not (text.startswith('{') or text.startswith('[')):
            return False
        
        # Try to parse as JSON (the most reliable method)
        try:
            import json
            json.loads(text)
            return True
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Check for common JSON/JSONL patterns (fallback)
        json_indicators = [
            r'"[^"]*"\s*:\s*["\d\[\{]',  # JSON key-value
        ]
        
        matches = 0
        for pattern in json_indicators:
            if re.search(pattern, text):
                matches += 1
        
        # Also check for YAML-like config
        yaml_patterns = [
            r'^[a-z_]+:\s*$',  # key:
            r'^\s+[a-z_]+:\s*[\|"\'<]',  # nested key
        ]
        
        yaml_matches = 0
        for pattern in yaml_patterns:
            yaml_matches += len(re.findall(pattern, text, re.MULTILINE))
        
        return matches >= 2 or yaml_matches >= 3
    
    def _split_json_config(self, text: str) -> List[str]:
        """Split JSON/config file while preserving structure.
        
        Args:
            text: JSON or config file text.
            
        Returns:
            List of chunks preserving config structure.
        """
        # Try to split by top-level keys or array items
        chunks = []
        
        text = text.strip()
        
        # If JSON array (list of objects), try to split by items
        if text.startswith('['):
            # Simple approach: split by },{
            item_pattern = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}')
            items = item_pattern.findall(text)
            
            if items:
                current_chunk = ""
                for item in items:
                    if len(current_chunk) + len(item) + 2 <= self.max_chunk_size:
                        current_chunk += item + ", "
                    else:
                        if current_chunk:
                            chunks.append("[" + current_chunk.rstrip(", ") + "]")
                        current_chunk = item
                
                if current_chunk:
                    chunks.append("[" + current_chunk.rstrip(", ") + "]")
                
                if chunks:
                    self.validate_chunks(chunks)
                    return chunks
        
        # If JSON object, try to split by top-level keys
        if text.startswith('{'):
            # Split by top-level keys (keys at depth 1)
            key_pattern = re.compile(r'^(\s*)"([^"]+)"\s*:', re.MULTILINE)
            matches = list(key_pattern.finditer(text))
            
            if len(matches) >= 2:
                for i, match in enumerate(matches):
                    start = match.start()
                    # Find the value section for this key
                    # Look for next key or end of object
                    if i + 1 < len(matches):
                        end = matches[i + 1].start()
                    else:
                        end = len(text)
                    
                    section = text[start:end].strip().rstrip(',')
                    if section:
                        if len(section) <= self.max_chunk_size:
                            chunks.append(section)
                        else:
                            chunks.extend(self._split_recursive(section))
                
                if chunks:
                    self.validate_chunks(chunks)
                    return chunks
        
        # Fallback: recursive split
        return self._split_recursive(text)
    
    def _has_markdown_headings(self, text: str) -> bool:
        """Check if text has Markdown headings."""
        pattern = re.compile(r'^#{1,6}\s+', re.MULTILINE)
        matches = pattern.findall(text)
        return len(matches) >= 2
    
    def _has_numbered_sections(self, text: str) -> bool:
        """Check if text has numbered sections."""
        # Pattern: 1., 1.1, 1.1.1, etc. (with period and space)
        pattern = re.compile(r'^\d+(\.\d+)*\.\s+', re.MULTILINE)
        matches = pattern.findall(text)
        return len(matches) >= 2
    
    def _has_tables(self, text: str) -> bool:
        """Check if text has table structures."""
        # Count lines with table markers
        table_lines = 0
        lines = text.split('\n')
        
        for line in lines:
            if '|' in line or '\t' in line:
                table_lines += 1
        
        # If > 30% lines have table markers, treat as table document
        return table_lines >= 3 and table_lines / len(lines) > 0.3 if lines else False


class SmartSplitterWithParser(SmartSplitter):
    """Extended SmartSplitter that works with ParsedDocument.
    
    This variant can accept ParsedDocument objects from DocumentParser
    and use their full structure (TOC, sections, pages) for intelligent chunking.
    
    Example:
        >>> from src.agent.parsers import DocumentParser
        >>> from src.libs.splitter import SmartSplitterWithParser
        >>> 
        >>> parser = DocumentParser()
        >>> doc = parser.parse("paper.pdf")
        >>> 
        >>> splitter = SmartSplitterWithParser(settings)
        >>> chunks = splitter.split_parsed_document(doc)
    """
    
    def split_parsed_document(self, parsed_doc: Any) -> List[str]:
        """Split a ParsedDocument using smart detection.
        
        Args:
            parsed_doc: ParsedDocument object from DocumentParser.
            
        Returns:
            List of text chunks.
        """
        # Extract TOC if available
        toc = None
        if hasattr(parsed_doc, 'metadata') and parsed_doc.metadata:
            toc = parsed_doc.metadata.get('toc')
        
        # Use sections if available
        if hasattr(parsed_doc, 'sections') and parsed_doc.sections:
            # Convert sections to TOC format
            if toc is None:
                toc = []
                for section in parsed_doc.sections:
                    toc.append({
                        'title': section.title if hasattr(section, 'title') else None,
                        'level': section.level if hasattr(section, 'level') else 1,
                        'position': section.char_start if hasattr(section, 'char_start') else 0,
                        'page': section.page_no if hasattr(section, 'page_no') else 1,
                    })
        
        # Combine all text
        if hasattr(parsed_doc, 'sections') and parsed_doc.sections:
            full_text = "\n\n".join([
                s.text for s in parsed_doc.sections if hasattr(s, 'text')
            ])
        elif hasattr(parsed_doc, 'pages') and parsed_doc.pages:
            full_text = "\n\n".join([
                p.text for p in parsed_doc.pages if hasattr(p, 'text')
            ])
        else:
            full_text = ""
        
        if not full_text:
            return [""]
        
        # Use smart splitting
        metadata = {}
        if hasattr(parsed_doc, 'metadata'):
            metadata = parsed_doc.metadata or {}
        
        chunks = self.split_text(full_text, metadata=metadata, toc=toc)
        
        # Validate
        if not chunks:
            return [""]
        
        self.validate_chunks(chunks)
        return chunks


__all__ = [
    "SmartSplitter",
    "SmartSplitterWithParser",
]

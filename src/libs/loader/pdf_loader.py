"""PDF Loader implementation using MarkItDown.

This module implements PDF parsing with image extraction support,
converting PDFs to standardized Markdown format with image placeholders.

Features:
- Text extraction and Markdown conversion via MarkItDown
- TOC (Table of Contents) extraction via PyMuPDF
- Image extraction and storage with accurate position insertion
- Image placeholder insertion with metadata tracking
- Graceful degradation if image extraction fails
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from PIL import Image
import io

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader

logger = logging.getLogger(__name__)


class PdfLoader(BaseLoader):
    """PDF Loader using MarkItDown for text extraction and Markdown conversion.
    
    This loader:
    1. Extracts text from PDF and converts to Markdown
    2. Extracts TOC (Table of Contents) via PyMuPDF
    3. Extracts images and saves to data/images/{doc_hash}/
    4. Inserts image placeholders at correct positions (near related text)
    5. Records image and TOC metadata in Document.metadata
    
    Configuration:
        extract_images: Enable/disable image extraction (default: True)
        image_storage_dir: Base directory for image storage (default: data/images)
    
    Graceful Degradation:
        If image extraction fails, logs warning and continues with text-only parsing.
    """
    
    def __init__(
        self,
        extract_images: bool = True,
        image_storage_dir: str | Path = "data/images"
    ):
        """Initialize PDF Loader.
        
        Args:
            extract_images: Whether to extract images from PDFs.
            image_storage_dir: Base directory for storing extracted images.
        """
        if not MARKITDOWN_AVAILABLE:
            raise ImportError(
                "MarkItDown is required for PdfLoader. "
                "Install with: pip install markitdown"
            )
        
        self.extract_images = extract_images
        self.image_storage_dir = Path(image_storage_dir)
        self._markitdown = MarkItDown()
    
    def load(self, file_path: str | Path) -> Document:
        """Load and parse a PDF file.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            Document with Markdown text and metadata.
            
        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            ValueError: If the file is not a valid PDF.
            RuntimeError: If parsing fails critically.
        """
        # Validate file
        path = self._validate_file(file_path)
        if path.suffix.lower() != '.pdf':
            raise ValueError(f"File is not a PDF: {path}")
        
        # Compute document hash for unique ID and image directory
        doc_hash = self._compute_file_hash(path)
        doc_id = f"doc_{doc_hash[:16]}"
        
        # Parse PDF with MarkItDown
        try:
            result = self._markitdown.convert(str(path))
            text_content = result.text_content if hasattr(result, 'text_content') else str(result)
        except Exception as e:
            logger.error(f"Failed to parse PDF {path}: {e}")
            raise RuntimeError(f"PDF parsing failed: {e}") from e
        
        # Initialize metadata
        metadata: Dict[str, Any] = {
            "source_path": str(path),
            "doc_type": "pdf",
            "doc_hash": doc_hash,
        }
        
        # Extract title from first heading if available
        title = self._extract_title(text_content)
        if title:
            metadata["title"] = title
        
        # Extract TOC (Table of Contents) from PDF outline
        toc_metadata = self._extract_toc(path)
        if toc_metadata:
            metadata["toc"] = toc_metadata
            logger.info(f"Extracted TOC with {len(toc_metadata)} entries from {path}")
        
        # Handle image extraction (with graceful degradation)
        if self.extract_images and PYMUPDF_AVAILABLE:
            try:
                text_content, images_metadata = self._extract_and_process_images(
                    path, text_content, doc_hash
                )
                if images_metadata:
                    metadata["images"] = images_metadata
            except Exception as e:
                logger.warning(
                    f"Image extraction failed for {path}, continuing with text-only: {e}"
                )
        
        return Document(
            id=doc_id,
            text=text_content,
            metadata=metadata
        )
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Extract title from first Markdown heading or first non-empty line."""
        lines = text.split('\n')
        
        # First try to find a markdown heading
        for line in lines[:20]:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        
        # Fallback: use first non-empty line as title
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 0:
                return line
        
        return None
    
    def _extract_toc(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Extract Table of Contents from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            List of TOC entries with title, level, page, and position.
        """
        if not PYMUPDF_AVAILABLE:
            logger.debug("PyMuPDF not available, skipping TOC extraction")
            return []
        
        toc_entries = []
        
        try:
            doc = fitz.open(pdf_path)
            
            # Try to get TOC from document outline ( bookmarks )
            toc = doc.get_toc()
            
            if toc:
                for entry in toc:
                    # TOC entry format: [level, title, page, ...]
                    level = entry[0] if len(entry) > 0 else 1
                    title = entry[1] if len(entry) > 1 else ""
                    page = entry[2] if len(entry) > 2 else 1
                    
                    if title and title.strip():
                        toc_entries.append({
                            "title": title.strip(),
                            "level": level,
                            "page": page,
                            "type": "outline"
                        })
                
                logger.debug(f"Extracted {len(toc_entries)} TOC entries from outline")
                doc.close()
                return toc_entries
            
            # Fallback: Try to extract TOC from text content
            doc.close()
            return self._extract_toc_from_text(pdf_path)
            
        except Exception as e:
            logger.warning(f"Failed to extract TOC from outline: {e}")
            # Fallback: Try to extract TOC from text content
            return self._extract_toc_from_text(pdf_path)
    
    def _extract_toc_from_text(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Extract Table of Contents from PDF text content.
        
        This is a fallback method that searches for TOC patterns in the text.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            List of TOC entries with title, level, page, and position.
        """
        toc_entries = []
        
        if not PYMUPDF_AVAILABLE:
            return toc_entries
        
        try:
            doc = fitz.open(pdf_path)
            
            # Patterns for TOC detection (Chinese and English)
            toc_patterns = [
                # Chinese patterns: 第一章, 1.1, 1.1.1
                r'^第[一二三四五六七八九十百千\d]+[章节篇部]\s+(.+)$',
                r'^(\d+\.)+\s+(.+)$',
                # English patterns: Chapter 1, 1.1, Section 1
                r'^(Chapter|Chapter\s+\d+)\s+(.+)$',
                r'^(Section|Article)\s+(\d+[.\d]*)\s+(.+)$',
            ]
            
            # Common TOC header patterns
            header_patterns = [
                r'^目\s*录',
                r'^目\s*录\s*$',
                r'^Table\s+of\s+Contents',
                r'^CONTENTS',
                r'^目录',
            ]
            
            is_in_toc = False
            toc_text = []
            
            for page_num in range(min(5, len(doc))):  # Check first 5 pages for TOC
                page = doc[page_num]
                page_text = page.get_text("text")
                lines = page_text.split('\n')
                
                for i, line in enumerate(lines):
                    line_stripped = line.strip()
                    
                    # Check if we're in TOC section
                    for header_pattern in header_patterns:
                        if re.search(header_pattern, line_stripped, re.IGNORECASE):
                            is_in_toc = True
                            continue
                    
                    if is_in_toc:
                        # Check if we've left TOC (usually before page 1 content)
                        if page_num > 2 and re.search(r'^(第|Chapter)', line_stripped):
                            break
                        
                        # Try to match TOC entries
                        for pattern in toc_patterns:
                            match = re.match(pattern, line_stripped)
                            if match:
                                if len(match.groups()) >= 1:
                                    title = match.group(1).strip()
                                    # Determine level from pattern
                                    if '第' in pattern and '章' in pattern:
                                        level = 1
                                    elif '第' in pattern and '节' in pattern:
                                        level = 2
                                    else:
                                        level = match.lastindex or 1
                                    
                                    if title:
                                        toc_entries.append({
                                            "title": title,
                                            "level": level,
                                            "page": page_num + 1,
                                            "type": "text"
                                        })
                                break
            
            doc.close()
            
            if toc_entries:
                logger.debug(f"Extracted {len(toc_entries)} TOC entries from text")
            
            return toc_entries
            
        except Exception as e:
            logger.warning(f"Failed to extract TOC from text: {e}")
            return []
    
    def _extract_and_process_images(
        self,
        pdf_path: Path,
        text_content: str,
        doc_hash: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract images from PDF and insert placeholders at correct positions.
        
        Uses PyMuPDF to extract images, save them to disk, and insert
        placeholders near the related text content on each page.
        
        Args:
            pdf_path: Path to PDF file.
            text_content: Extracted text content.
            doc_hash: Document hash for image directory.
            
        Returns:
            Tuple of (modified_text, images_metadata_list)
        """
        if not self.extract_images:
            logger.debug(f"Image extraction disabled for {pdf_path}")
            return text_content, []
        
        if not PYMUPDF_AVAILABLE:
            logger.warning(f"PyMuPDF not available, skipping image extraction for {pdf_path}")
            return text_content, []
        
        images_metadata = []
        
        try:
            # Create image storage directory
            image_dir = self.image_storage_dir / doc_hash
            image_dir.mkdir(parents=True, exist_ok=True)
            
            # Open PDF with PyMuPDF
            doc = fitz.open(pdf_path)
            
            # Build page text map to find insertion positions
            page_texts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text")
                page_texts.append({
                    "page_num": page_num + 1,
                    "text": page_text,
                    "length": len(page_text)
                })
            
            # Calculate cumulative text lengths to find insertion positions
            cumulative_lengths = []
            total = 0
            for pt in page_texts:
                cumulative_lengths.append(total)
                total += len(pt["text"])
            
            # Store image insert positions for each page
            page_image_inserts: Dict[int, List[Dict]] = {i + 1: [] for i in range(len(doc))}
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)
                
                for img_index, img_info in enumerate(image_list):
                    try:
                        # Extract image
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Generate image ID and filename
                        image_id = self._generate_image_id(doc_hash, page_num + 1, img_index + 1)
                        image_filename = f"{image_id}.{image_ext}"
                        image_path = image_dir / image_filename
                        
                        # Save image
                        with open(image_path, "wb") as img_file:
                            img_file.write(image_bytes)
                        
                        # Get image dimensions
                        try:
                            img = Image.open(io.BytesIO(image_bytes))
                            width, height = img.size
                        except Exception:
                            width, height = 0, 0
                        
                        # Get image position on page
                        img_rect = None
                        if len(img_info) > 1:
                            img_rect = img_info[1]
                        
                        # Create placeholder with page info
                        placeholder = f"[IMAGE: {image_id}]"
                        
                        # Calculate absolute text position
                        absolute_position = cumulative_lengths[page_num]
                        
                        # Convert path to be relative to project root or absolute
                        try:
                            relative_path = image_path.relative_to(Path.cwd())
                        except ValueError:
                            relative_path = image_path.absolute()
                        
                        # Record metadata
                        image_metadata = {
                            "id": image_id,
                            "path": str(relative_path),
                            "page": page_num + 1,
                            "text_offset": absolute_position,
                            "text_length": len(placeholder),
                            "position": {
                                "width": width,
                                "height": height,
                                "page": page_num + 1,
                                "index": img_index,
                                "x": img_rect.x0 if img_rect else 0,
                                "y": img_rect.y0 if img_rect else 0,
                            }
                        }
                        images_metadata.append(image_metadata)
                        
                        # Store for later insertion
                        page_image_inserts[page_num + 1].append({
                            "placeholder": placeholder,
                            "position": absolute_position,
                            "image_id": image_id,
                        })
                        
                        logger.debug(f"Extracted image {image_id} from page {page_num + 1}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to extract image {img_index} from page {page_num + 1}: {e}")
                        continue
            
            doc.close()
            
            # Insert image placeholders at correct positions in text
            modified_text = self._insert_placeholders_at_positions(
                text_content, page_texts, page_image_inserts
            )
            
            if images_metadata:
                logger.info(f"Extracted {len(images_metadata)} images from {pdf_path}")
            else:
                logger.debug(f"No images found in {pdf_path}")
            
            return modified_text, images_metadata
            
        except Exception as e:
            logger.warning(f"Image extraction failed for {pdf_path}: {e}")
            return text_content, []
    
    def _insert_placeholders_at_positions(
        self,
        text_content: str,
        page_texts: List[Dict],
        page_image_inserts: Dict[int, List[Dict]]
    ) -> str:
        """Insert image placeholders at the correct positions in text.
        
        For each page, finds the end of that page's content and inserts
        the image placeholder there.
        
        Args:
            text_content: Original text content.
            page_texts: List of page text info with lengths.
            page_image_inserts: Dict mapping page_num to list of placeholders to insert.
            
        Returns:
            Modified text with placeholders inserted.
        """
        if not page_image_inserts or all(not v for v in page_image_inserts.values()):
            return text_content
        
        # Build modified text by processing page by page
        result_parts = []
        current_pos = 0
        
        for page_num, page_info in enumerate(page_texts):
            page_text = page_info["text"]
            page_end = current_pos + len(page_text)
            
            # Add page text
            result_parts.append(text_content[current_pos:page_end])
            
            # Insert image placeholders for this page
            if page_num + 1 in page_image_inserts:
                for insert_info in page_image_inserts[page_num + 1]:
                    result_parts.append(f"\n{insert_info['placeholder']}\n")
            
            current_pos = page_end
        
        # Add any remaining text after last processed page
        if current_pos < len(text_content):
            result_parts.append(text_content[current_pos:])
        
        return "".join(result_parts)
    
    @staticmethod
    def _generate_image_id(doc_hash: str, page: int, sequence: int) -> str:
        """Generate unique image ID.
        
        Args:
            doc_hash: Document hash.
            page: Page number (1-based).
            sequence: Image sequence on page (1-based).
            
        Returns:
            Unique image ID string.
        """
        return f"{doc_hash[:8]}_{page}_{sequence}"

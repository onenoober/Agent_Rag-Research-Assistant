"""Universal Document Loader that supports multiple file formats.

This module provides a unified interface for loading various document formats
(PDF, DOCX, TXT, MD) based on file extension detection.

Design Principles:
- Format Detection: Automatically selects appropriate loader based on file extension
- Extensibility: Easy to add new format loaders
- Error Handling: Clear error messages for unsupported formats
- Graceful Degradation: Falls back to text loader for unknown formats
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Type, Optional

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader
from src.libs.loader.pdf_loader import PdfLoader
from src.libs.loader.docx_loader import DocxLoader

logger = logging.getLogger(__name__)


# Registry of file extensions to loader classes
LOADER_REGISTRY: Dict[str, Type[BaseLoader]] = {
    ".pdf": PdfLoader,
    ".docx": DocxLoader,
    ".doc": DocxLoader,
}


class UniversalLoader(BaseLoader):
    """Universal document loader supporting multiple formats.
    
    This loader automatically detects the file format based on extension
    and uses the appropriate specialized loader.
    
    Supported formats:
        - PDF (.pdf): Uses PdfLoader with MarkItDown + TOC extraction + Image extraction
        - Word (.docx, .doc): Uses DocxLoader with python-docx + TOC extraction + Table extraction
        - Text (.txt): Falls back to text-based loading
        - Markdown (.md): Falls back to text-based loading
    
    Features:
        - Automatic TOC (Table of Contents) extraction for PDF and DOCX
        - Image extraction with accurate position tracking
        - Table extraction for Word documents
        - Heading detection and structure preservation
    
    Example:
        >>> loader = UniversalLoader()
        >>> doc = loader.load("document.pdf")
        >>> doc = loader.load("document.docx")
        >>> if doc.metadata.get("toc"):
        ...     print(f"TOC entries: {len(doc.metadata['toc'])}")
    """
    
    def __init__(
        self,
        extract_images: bool = True,
        image_storage_dir: str | Path = "data/images",
        extract_tables: bool = True,
        detect_headings: bool = True,
    ):
        """Initialize UniversalLoader with all format options.
        
        Args:
            extract_images: Whether to extract images from PDFs.
            image_storage_dir: Base directory for storing extracted images.
            extract_tables: Whether to extract tables from Word docs.
            detect_headings: Whether to detect headings in documents.
        """
        self._loaders: Dict[str, BaseLoader] = {}
        self._extract_images = extract_images
        self._image_storage_dir = image_storage_dir
        self._extract_tables = extract_tables
        self._detect_headings = detect_headings
    
    def _get_loader(self, file_path: str | Path) -> BaseLoader:
        """Get or create appropriate loader for file type.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Appropriate loader instance for the file type
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        
        # Return cached loader if available
        if ext in self._loaders:
            return self._loaders[ext]
        
        # Check if format is supported
        if ext not in LOADER_REGISTRY:
            # Fallback to PDF loader for unknown formats
            # It will handle the error appropriately
            logger.warning(f"Unknown file extension '{ext}', attempting PDF loading")
            ext = ".pdf"
        
        # Create loader instance
        loader_class = LOADER_REGISTRY[ext]
        
        if ext == ".pdf":
            loader = loader_class(
                extract_images=self._extract_images,
                image_storage_dir=self._image_storage_dir,
            )
        elif ext in [".docx", ".doc"]:
            loader = loader_class(
                extract_tables=self._extract_tables,
                detect_headings=self._detect_headings,
            )
        else:
            # Fallback for .txt, .md, etc. - use PDF loader's text mode
            loader = loader_class()
        
        # Cache the loader
        self._loaders[ext] = loader
        return loader
    
    def load(self, file_path: str | Path) -> Document:
        """Load and parse a document file of any supported format.
        
        Automatically detects format based on file extension and uses
        the appropriate loader.
        
        Args:
            file_path: Path to the document file to load.
            
        Returns:
            Document object with parsed content and metadata.
            metadata MUST contain at least 'source_path'.
            
        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is invalid or unsupported.
            RuntimeError: If parsing fails critically.
        """
        # Validate file exists
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        # Get appropriate loader
        loader = self._get_loader(path)
        
        # Delegate to specific loader
        return loader.load(path)
    
    @staticmethod
    def get_supported_extensions() -> list[str]:
        """Get list of supported file extensions.
        
        Returns:
            List of supported file extensions (e.g., ['.pdf', '.docx', '.doc'])
        """
        return list(LOADER_REGISTRY.keys())

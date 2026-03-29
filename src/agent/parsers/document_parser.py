"""Document parser facade.

This module provides a unified entry point for document parsing,
supporting multiple file formats (PDF, TXT, MD).
"""

from pathlib import Path
from typing import Optional

from src.agent.parsers.base import BaseParser, create_parser
from src.agent.schemas.document import ParsedDocument


class DocumentParser:
    """Unified document parser that selects the appropriate parser based on file extension."""

    def __init__(self):
        """Initialize the document parser."""
        self._parser: Optional[BaseParser] = None

    def parse(self, file_path: str) -> ParsedDocument:
        """Parse a document and return a structured document.

        Args:
            file_path: Path to the document file.

        Returns:
            ParsedDocument: A structured representation of the document.

        Raises:
            ValueError: If the file format is not supported.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Select appropriate parser based on extension
        parser = create_parser(file_path)
        self._parser = parser

        return parser.parse(file_path)

    def can_parse(self, file_path: str) -> bool:
        """Check if the parser can handle this file.

        Args:
            file_path: Path to the document file.

        Returns:
            bool: True if the file can be parsed, False otherwise.
        """
        try:
            parser = create_parser(file_path)
            return parser.can_parse(file_path)
        except Exception:
            return False

    @property
    def supported_extensions(self) -> list:
        """Get list of supported file extensions.

        Returns:
            list: List of supported file extensions (e.g., ['.pdf', '.txt', '.md', '.docx', '.xlsx', '.xls']).
        """
        return [".pdf", ".txt", ".md", ".docx", ".xlsx", ".xls"]
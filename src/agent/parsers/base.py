"""Base parser for document parsing.

This module defines the base parser interface that all document parsers
must implement. All parsers should inherit from BaseParser and implement
the parse method.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from src.agent.schemas.document import ParsedDocument


class ParserError(Exception):
    """Base exception for parser errors."""
    pass


class ParseError(ParserError):
    """Exception raised when document parsing fails."""
    pass


class UnsupportedFormatError(ParserError):
    """Exception raised when file format is not supported."""
    pass


class BaseParser(ABC):
    """Base class for document parsers.
    
    All document parsers must inherit from this class and implement
    the parse method. The parse method should return a ParsedDocument
    containing all parsed pages and sections.
    
    Attributes:
        supported_extensions: List of supported file extensions
    """
    
    supported_extensions: list[str] = []
    
    @abstractmethod
    def parse(self, file_path: str | Path) -> ParsedDocument:
        """Parse a document file.
        
        Args:
            file_path: Path to the document file to parse.
            
        Returns:
            ParsedDocument containing parsed pages and sections.
            
        Raises:
            ParseError: If parsing fails.
            UnsupportedFormatError: If file format is not supported.
            FileNotFoundError: If the file doesn't exist.
        """
        pass
    
    def can_parse(self, file_path: str | Path) -> bool:
        """Check if this parser can handle the given file.
        
        Args:
            file_path: Path to check.
            
        Returns:
            True if this parser supports the file extension.
        """
        path = Path(file_path)
        return path.suffix.lower() in self.supported_extensions
    
    def validate_file(self, file_path: str | Path) -> Path:
        """Validate that the file exists and is readable.
        
        Args:
            file_path: Path to validate.
            
        Returns:
            Validated Path object.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
            UnsupportedFormatError: If format is not supported.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {path}")
        if not self.can_parse(path):
            raise UnsupportedFormatError(
                f"Unsupported format: {path.suffix}. "
                f"Supported: {', '.join(self.supported_extensions)}"
            )
        return path


def create_parser(file_path: str | Path) -> "BaseParser":
    """Factory function to create the appropriate parser for a file.
    
    Args:
        file_path: Path to the file to parse.
        
    Returns:
        Appropriate parser instance for the file type.
        
    Raises:
        UnsupportedFormatError: If no parser supports the file type.
    """
    from src.agent.parsers.text_parser import TextParser
    from src.agent.parsers.pdf_parser import PdfParser
    from src.agent.parsers.word_parser import WordParser
    from src.agent.parsers.excel_parser import ExcelParser
    
    path = Path(file_path)
    ext = path.suffix.lower()
    
    parsers = [
        (TextParser, [".txt", ".md"]),
        (PdfParser, [".pdf"]),
        (WordParser, [".docx"]),
        (ExcelParser, [".xlsx", ".xls"]),
    ]
    
    for parser_class, extensions in parsers:
        if ext in extensions:
            return parser_class()
    
    raise UnsupportedFormatError(
        f"No parser available for: {ext}"
    )


__all__ = [
    "BaseParser",
    "ParserError",
    "ParseError",
    "UnsupportedFormatError",
    "create_parser",
]

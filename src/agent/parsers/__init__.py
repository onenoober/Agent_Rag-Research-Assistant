"""Document parsers package.

This package contains document parsing modules:
- base: Base parser interface
- text_parser: Parser for .txt and .md files
- pdf_parser: Parser for PDF files
- word_parser: Parser for .docx files
- excel_parser: Parser for .xlsx and .xls files
- chunk_builder: Builds structured chunks from parsed documents
- document_parser: Unified document parser facade
"""

from src.agent.parsers.base import (
    BaseParser,
    ParserError,
    ParseError,
    UnsupportedFormatError,
    create_parser,
)
from src.agent.parsers.text_parser import TextParser, TextParserConfig
from src.agent.parsers.document_parser import DocumentParser

# Lazy import for PDF parser (requires PyMuPDF)
def _get_pdf_parser():
    try:
        from src.agent.parsers.pdf_parser import PdfParser, PdfParserConfig
        return PdfParser, PdfParserConfig
    except ImportError:
        return None, None

# Lazy import for Word parser (requires python-docx)
def _get_word_parser():
    try:
        from src.agent.parsers.word_parser import WordParser, WordParserConfig
        return WordParser, WordParserConfig
    except ImportError:
        return None, None

# Lazy import for Excel parser (requires openpyxl)
def _get_excel_parser():
    try:
        from src.agent.parsers.excel_parser import ExcelParser, ExcelParserConfig
        return ExcelParser, ExcelParserConfig
    except ImportError:
        return None, None

def __getattr__(name):
    if name == "PdfParser" or name == "PdfParserConfig":
        PdfParser, PdfParserConfig = _get_pdf_parser()
        if PdfParser is None:
            raise ImportError(
                "PyMuPDF (fitz) is not installed. Install with: pip install pymupdf"
            )
        return PdfParser if name == "PdfParser" else PdfParserConfig
    if name == "WordParser" or name == "WordParserConfig":
        WordParser, WordParserConfig = _get_word_parser()
        if WordParser is None:
            raise ImportError(
                "python-docx is not installed. Install with: pip install python-docx"
            )
        return WordParser if name == "WordParser" else WordParserConfig
    if name == "ExcelParser" or name == "ExcelParserConfig":
        ExcelParser, ExcelParserConfig = _get_excel_parser()
        if ExcelParser is None:
            raise ImportError(
                "openpyxl is not installed. Install with: pip install openpyxl"
            )
        return ExcelParser if name == "ExcelParser" else ExcelParserConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

from src.agent.parsers.chunk_builder import (
    ChunkBuilder,
    ChunkBuilderConfig,
    create_chunk_builder,
)

__all__ = [
    # Base
    "BaseParser",
    "ParserError",
    "ParseError",
    "UnsupportedFormatError",
    "create_parser",
    # Document parser (unified entry)
    "DocumentParser",
    # Text parser
    "TextParser",
    "TextParserConfig",
    # PDF parser (lazy loaded)
    "PdfParser",
    "PdfParserConfig",
    # Word parser (lazy loaded)
    "WordParser",
    "WordParserConfig",
    # Excel parser (lazy loaded)
    "ExcelParser",
    "ExcelParserConfig",
    # Chunk builder
    "ChunkBuilder",
    "ChunkBuilderConfig",
    "create_chunk_builder",
]

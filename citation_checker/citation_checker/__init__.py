"""Citation Checker - Validate citations, detect fakes, suggest fixes."""

__version__ = "1.0.0"
from .checker import CitationChecker, CitationResult
from .parsers import parse_citations, detect_format
from .report import export_json, export_csv, export_pdf

__all__ = [
    "CitationChecker",
    "CitationResult",
    "parse_citations",
    "detect_format",
    "export_json",
    "export_csv",
    "export_pdf",
    "__version__",
]

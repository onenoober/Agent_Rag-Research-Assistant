"""Test dataset loaders with format abstraction.

This module provides a pluggable dataset system:
- Abstract base class (BaseDataset) for type safety
- Built-in JSON/JSONL support
- Extensible for CSV, Parquet, etc.
- Backwards compatible with existing load_test_set() function

Design Principles Applied:
- Interface Segregation: Lightweight abstract base for core functionality
- Open/Closed: Add new formats without modifying existing code
- Dependency Injection: Dataset format determined at runtime

Example Usage::

    from src.evaluation.datasets import load_dataset, JsonDataset

    # Using the factory function (recommended)
    test_set = load_dataset("tests/fixtures/phoenix_test_set.json")

    # Direct instantiation
    dataset = JsonDataset("tests/fixtures/phoenix_test_set.json")
    for test_case in dataset:
        print(test_case.query)
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Type, Union

logger = logging.getLogger(__name__)


class BaseDataset(ABC):
    """Abstract base class for test dataset loaders.

    All dataset loaders must inherit from this class and implement
    the __iter__ method. This enables polymorphic dataset handling.
    """

    @property
    @abstractmethod
    def path(self) -> str:
        """Return the path to the dataset file."""
        ...

    @property
    @abstractmethod
    def description(self) -> Optional[str]:
        """Return the dataset description if available."""
        ...

    @property
    @abstractmethod
    def version(self) -> Optional[str]:
        """Return the dataset version if available."""
        ...

    @abstractmethod
    def __iter__(self) -> Iterator:
        """Iterate over test cases in the dataset."""
        ...

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of test cases."""
        ...

    @abstractmethod
    def load(self) -> List[Any]:
        """Load all test cases into memory."""
        ...

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the dataset."""
        ...


@dataclass
class GoldenTestCase:
    """A single evaluation test case from the golden test set.

    Attributes:
        query: The test query string.
        expected_chunk_ids: Ground-truth chunk IDs for IR metrics.
        expected_sources: Ground-truth source file names (optional).
        reference_answer: Reference answer text for LLM-as-Judge (optional).
    """

    query: str
    expected_chunk_ids: List[str] = field(default_factory=list)
    expected_sources: List[str] = field(default_factory=list)
    reference_answer: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GoldenTestCase:
        return cls(
            query=data["query"],
            expected_chunk_ids=data.get("expected_chunk_ids", []),
            expected_sources=data.get("expected_sources", []),
            reference_answer=data.get("reference_answer"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "expected_chunk_ids": self.expected_chunk_ids,
            "expected_sources": self.expected_sources,
            "reference_answer": self.reference_answer,
        }


class JsonDataset(BaseDataset):
    """JSON-format test dataset loader.

    Supports the standard golden test set format:
    {
        "description": "...",
        "version": "1.0",
        "test_cases": [
            {
                "query": "...",
                "expected_chunk_ids": [...],
                "expected_sources": [...],
                "reference_answer": "..."
            }
        ]
    }
    Also supports JSONL format (one JSON object per line).
    """

    def __init__(
        self,
        path: Union[str, Path],
        *,
        validate: bool = True,
        strict: bool = False,
    ) -> None:
        """Initialize JsonDataset.

        Args:
            path: Path to the JSON or JSONL file.
            validate: If True, validate each test case.
            strict: If True, raise errors on invalid cases instead of skipping.
        """
        self._path = Path(path)
        self._validate = validate
        self._strict = strict
        self._test_cases: Optional[List[GoldenTestCase]] = None
        self._metadata: Optional[Dict[str, Any]] = None

    @property
    def path(self) -> str:
        return str(self._path)

    @property
    def description(self) -> Optional[str]:
        if self._metadata is None:
            self._load_metadata()
        return self._metadata.get("description") if self._metadata else None

    @property
    def version(self) -> Optional[str]:
        if self._metadata is None:
            self._load_metadata()
        return self._metadata.get("version") if self._metadata else None

    def _load_metadata(self) -> None:
        """Load metadata from the file (without loading all test cases)."""
        if not self._path.exists():
            raise FileNotFoundError(f"Dataset not found: {self._path}")

        try:
            with self._path.open("r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            content = self._path.read_text(encoding="utf-8-sig")

        # Try to parse as JSON
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                self._metadata = {
                    "description": data.get("description"),
                    "version": data.get("version"),
                    "source": str(self._path),
                }
            elif isinstance(data, list):
                self._metadata = {
                    "description": None,
                    "version": None,
                    "source": str(self._path),
                    "count": len(data),
                }
        except json.JSONDecodeError:
            # Try JSONL format
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            self._metadata = {
                "description": None,
                "version": None,
                "source": str(self._path),
                "count": len(lines),
                "format": "jsonl",
            }

    def _parse_json(self, data: Dict[str, Any]) -> List[GoldenTestCase]:
        """Parse JSON data into GoldenTestCase objects."""
        if "test_cases" not in data:
            if self._strict:
                raise ValueError(
                    "Invalid golden test set format: missing 'test_cases' key."
                )
            logger.warning(
                "Invalid format in %s: missing 'test_cases' key. "
                "Treating the data as a list of test cases.",
                self._path,
            )
            test_cases_data = data if isinstance(data, list) else []
        else:
            test_cases_data = data["test_cases"]

        test_cases = []
        for idx, tc_data in enumerate(test_cases_data):
            try:
                tc = GoldenTestCase.from_dict(tc_data)
                test_cases.append(tc)
            except Exception as e:
                msg = f"Test case [{idx}] failed to parse: {e}"
                if self._strict:
                    raise ValueError(msg) from e
                logger.warning(msg)

        return test_cases

    def _parse_jsonl(self, content: str) -> List[GoldenTestCase]:
        """Parse JSONL content into GoldenTestCase objects."""
        test_cases = []
        for idx, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    tc = GoldenTestCase.from_dict(data)
                    test_cases.append(tc)
            except Exception as e:
                msg = f"JSONL line [{idx}] failed to parse: {e}"
                if self._strict:
                    raise ValueError(msg) from e
                logger.warning(msg)

        return test_cases

    def _load_all(self) -> None:
        """Load all test cases into memory."""
        if self._test_cases is not None:
            return

        if not self._path.exists():
            raise FileNotFoundError(f"Dataset not found: {self._path}")

        try:
            content = self._path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = self._path.read_text(encoding="utf-8-sig")

        # Detect format
        trimmed = content.strip()
        if trimmed.startswith("["):
            # JSON array format
            data = json.loads(trimmed)
            self._test_cases = self._parse_json({"test_cases": data})
        elif trimmed.startswith("{"):
            # JSON object with test_cases key
            data = json.loads(trimmed)
            self._test_cases = self._parse_json(data)
        else:
            # Try JSONL format
            self._test_cases = self._parse_jsonl(content)

        logger.info("Loaded %d test cases from %s", len(self._test_cases), self._path)

    def load(self) -> List[GoldenTestCase]:
        """Load all test cases into memory."""
        self._load_all()
        assert self._test_cases is not None
        return self._test_cases

    def __iter__(self) -> Iterator[GoldenTestCase]:
        """Iterate over test cases."""
        self._load_all()
        assert self._test_cases is not None
        return iter(self._test_cases)

    def __len__(self) -> int:
        """Return the number of test cases."""
        self._load_all()
        assert self._test_cases is not None
        return len(self._test_cases)

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the dataset."""
        if self._metadata is None:
            self._load_metadata()
        return {
            **(self._metadata or {}),
            "count": len(self),
            "format": "json" if not self._metadata.get("format") == "jsonl" else "jsonl",
        }


# ── Dataset Factory ─────────────────────────────────────────────────────────────

_DATASET_REGISTRY: Dict[str, Type[BaseDataset]] = {}


def register_dataset_format(
    extension: str,
    dataset_class: Type[BaseDataset],
) -> None:
    """Register a dataset loader for a file extension.

    Args:
        extension: File extension (e.g., "json", "csv", "jsonl").
        dataset_class: BaseDataset subclass for this format.
    """
    _DATASET_REGISTRY[extension.lower().lstrip(".")] = dataset_class


# Register built-in formats
register_dataset_format("json", JsonDataset)
register_dataset_format("jsonl", JsonDataset)


def load_dataset(
    path: Union[str, Path],
    *,
    format_hint: Optional[str] = None,
    **kwargs: Any,
) -> BaseDataset:
    """Load a test dataset from a file.

    This function automatically detects the format based on file extension.

    Args:
        path: Path to the dataset file.
        format_hint: Force a specific format (e.g., "json").
        **kwargs: Additional arguments passed to the dataset loader.

    Returns:
        A BaseDataset instance.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the format is unsupported.

    Example::

        dataset = load_dataset("tests/fixtures/phoenix_test_set.json")
        for test_case in dataset:
            print(test_case.query)
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Dataset not found: {file_path}")

    # Determine format
    if format_hint:
        ext = format_hint.lower().lstrip(".")
    else:
        ext = file_path.suffix.lower().lstrip(".")

    # Look up registered loader
    loader_class = _DATASET_REGISTRY.get(ext)
    if loader_class is None:
        available = ", ".join(sorted(_DATASET_REGISTRY.keys()))
        raise ValueError(
            f"Unsupported dataset format: '{ext}'. "
            f"Available formats: {available}. "
            f"Use register_dataset_format() to add support."
        )

    return loader_class(file_path, **kwargs)


# ── Backwards Compatibility ─────────────────────────────────────────────────────

def load_test_set(path: Union[str, Path]) -> List[GoldenTestCase]:
    """Load golden test set from a JSON file (backwards compatible).

    This function is a convenience wrapper around load_dataset()
    that maintains backwards compatibility with existing code.

    Args:
        path: Path to the golden test set JSON file.

    Returns:
        List of GoldenTestCase instances.
    """
    dataset = load_dataset(path)
    return list(dataset)

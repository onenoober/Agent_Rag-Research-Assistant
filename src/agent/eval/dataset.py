"""Evaluation dataset loader with schema validation.

This module provides functionality to load and validate evaluation test cases
from JSONL format files.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvalTestCase:
    """A single evaluation test case.

    Attributes:
        case_id: Unique identifier for this test case.
        question: The test question/query.
        expected_keywords: Keywords expected in the answer.
        expected_sources: Source files expected to be referenced.
        expected_page_no: Expected page number (optional).
        expected_section_title: Expected section title (optional).
        reference_answer: Reference answer text (optional).
    """

    case_id: str
    question: str
    expected_keywords: List[str] = field(default_factory=list)
    expected_sources: List[str] = field(default_factory=list)
    expected_page_no: Optional[int] = None
    expected_section_title: Optional[str] = None
    reference_answer: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvalTestCase:
        """Create EvalTestCase from dictionary.

        Args:
            data: Dictionary containing test case data.

        Returns:
            EvalTestCase instance.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        if not data.get("case_id"):
            raise ValueError("Missing required field: case_id")
        if not data.get("question"):
            raise ValueError("Missing required field: question")

        return cls(
            case_id=data["case_id"],
            question=data["question"],
            expected_keywords=data.get("expected_keywords", []),
            expected_sources=data.get("expected_sources", []),
            expected_page_no=data.get("expected_page_no"),
            expected_section_title=data.get("expected_section_title"),
            reference_answer=data.get("reference_answer"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        result = {
            "case_id": self.case_id,
            "question": self.question,
            "expected_keywords": self.expected_keywords,
            "expected_sources": self.expected_sources,
        }
        if self.expected_page_no is not None:
            result["expected_page_no"] = self.expected_page_no
        if self.expected_section_title is not None:
            result["expected_section_title"] = self.expected_section_title
        if self.reference_answer is not None:
            result["reference_answer"] = self.reference_answer
        return result


class EvalDatasetLoader:
    """Loads and validates evaluation test cases from JSONL files.

    Example:
        loader = EvalDatasetLoader()
        cases = loader.load("data/eval/smoke_cases.jsonl")
        filtered = loader.filter_by_ids(cases, ["case_001", "case_002"])
    """

    REQUIRED_FIELDS = {"case_id", "question"}
    OPTIONAL_FIELDS = {
        "expected_keywords",
        "expected_sources",
        "expected_page_no",
        "expected_section_title",
        "reference_answer",
    }

    def __init__(self) -> None:
        """Initialize the dataset loader."""
        self._loaded_cases: List[EvalTestCase] = []

    def load(
        self,
        file_path: str | Path,
        validate: bool = True,
    ) -> List[EvalTestCase]:
        """Load evaluation test cases from JSONL file.

        Args:
            file_path: Path to the JSONL file.
            validate: Whether to validate the format. Defaults to True.

        Returns:
            List of EvalTestCase instances.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is invalid or contains illegal cases.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Evaluation dataset not found: {path}")

        cases: List[EvalTestCase] = []
        errors: List[str] = []

        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    if validate:
                        self._validate_case(data, line_num)
                    case = EvalTestCase.from_dict(data)
                    cases.append(case)
                except json.JSONDecodeError as e:
                    errors.append(f"Line {line_num}: Invalid JSON - {e}")
                except ValueError as e:
                    errors.append(f"Line {line_num}: {e}")

        if errors:
            error_msg = "\n".join(errors)
            raise ValueError(f"Evaluation dataset validation failed:\n{error_msg}")

        if not cases:
            raise ValueError(f"Evaluation dataset is empty: {path}")

        logger.info(f"Loaded {len(cases)} test cases from {path}")
        self._loaded_cases = cases
        return cases

    def _validate_case(self, data: Dict[str, Any], line_num: int) -> None:
        """Validate a single test case.

        Args:
            data: Dictionary containing test case data.
            line_num: Line number for error reporting.

        Raises:
            ValueError: If validation fails.
        """
        missing = self.REQUIRED_FIELDS - set(data.keys())
        if missing:
            raise ValueError(
                f"Line {line_num}: Missing required fields: {missing}"
            )

        if not data.get("question"):
            raise ValueError(f"Line {line_num}: Empty question")

        if not isinstance(data.get("expected_keywords", []), list):
            raise ValueError(
                f"Line {line_num}: expected_keywords must be a list"
            )

        if not isinstance(data.get("expected_sources", []), list):
            raise ValueError(
                f"Line {line_num}: expected_sources must be a list"
            )

    def filter_by_ids(
        self,
        cases: List[EvalTestCase],
        case_ids: List[str],
    ) -> List[EvalTestCase]:
        """Filter test cases by case IDs.

        Args:
            cases: List of test cases.
            case_ids: List of case IDs to keep.

        Returns:
            Filtered list of test cases.
        """
        case_id_set = set(case_ids)
        return [c for c in cases if c.case_id in case_id_set]

    def filter_by_sources(
        self,
        cases: List[EvalTestCase],
        sources: List[str],
    ) -> List[EvalTestCase]:
        """Filter test cases that reference specific sources.

        Args:
            cases: List of test cases.
            sources: List of source names to filter by.

        Returns:
            Filtered list of test cases.
        """
        source_set = set(sources)
        return [
            c for c in cases
            if any(s in source_set for s in c.expected_sources)
        ]

    def get_smoke_cases(self, file_path: str | Path) -> List[EvalTestCase]:
        """Load smoke test cases (fast validation set).

        Args:
            file_path: Path to the smoke cases JSONL file.

        Returns:
            List of smoke test cases.
        """
        return self.load(file_path)

    def get_dev_cases(self, file_path: str | Path) -> List[EvalTestCase]:
        """Load development test cases (full validation set).

        Args:
            file_path: Path to the dev cases JSONL file.

        Returns:
            List of dev test cases.
        """
        return self.load(file_path)


def load_smoke_dataset(
    file_path: str | Path = "data/eval/smoke_cases.jsonl",
) -> List[EvalTestCase]:
    """Convenience function to load smoke dataset.

    Args:
        file_path: Path to smoke cases file.

    Returns:
        List of smoke test cases.
    """
    loader = EvalDatasetLoader()
    return loader.get_smoke_cases(file_path)


def load_dev_dataset(
    file_path: str | Path = "data/eval/dev_cases.jsonl",
) -> List[EvalTestCase]:
    """Convenience function to load dev dataset.

    Args:
        file_path: Path to dev cases file.

    Returns:
        List of dev test cases.
    """
    loader = EvalDatasetLoader()
    return loader.get_dev_cases(file_path)

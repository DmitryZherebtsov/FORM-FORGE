"""Domain models representing raw document structure extracted from input files.

Pure Python dataclasses with zero framework or I/O imports.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CheckboxItem:
    """Extracted checkbox or radio option."""

    label: str
    is_checked: bool = False
    context: str | None = None


@dataclass(frozen=True)
class KeyValuePair:
    """Key-value pair discovered in forms (e.g. 'Imię: Jan')."""

    key: str
    value: str
    confidence: float = 1.0


@dataclass(frozen=True)
class TableData:
    """Table extracted from a page or sheet."""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    title: str | None = None


@dataclass(frozen=True)
class ExtractedPage:
    """A single page, sheet, or visual section of a document."""

    page_number: int
    headings: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    key_values: list[KeyValuePair] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    checkboxes: list[CheckboxItem] = field(default_factory=list)
    raw_text: str = ""


@dataclass(frozen=True)
class ExtractedDocument:
    """Unified normalized document structure extracted across all input formats."""

    filename: str
    format: str
    pages: list[ExtractedPage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.raw_text for p in self.pages if p.raw_text)

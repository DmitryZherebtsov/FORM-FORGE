"""Domain port defining the contract for document extractors.

Zero I/O or external library dependencies.
"""

from abc import ABC, abstractmethod

from coi_form_digitization.domain.extracted_document import ExtractedDocument
from coi_form_digitization.domain.form_definition import FormDefinition
from coi_form_digitization.domain.structured_form import StructuredForm


class DocumentExtractorPort(ABC):
    """Abstract port for extracting raw document content into ExtractedDocument."""

    @abstractmethod
    def supports(self, extension: str) -> bool:
        """Return True if this extractor handles the declared file extension."""
        ...

    @abstractmethod
    def extract(self, filename: str, data: bytes) -> ExtractedDocument:
        """Extract structured elements from raw in-memory file bytes.

        Raises:
            DocumentProcessingError: If the document is corrupted or unreadable.
        """
        ...


class FormStructurerPort(ABC):
    """Abstract port for turning extracted content into a structured form."""

    @abstractmethod
    def structure(self, extracted: ExtractedDocument) -> StructuredForm:
        """Build semantic fields and sections from extracted document content."""
        ...


class FormDefinitionMapperPort(ABC):
    """Map extracted and structured forms to COI import-ready definitions."""

    @abstractmethod
    def build_definition(
        self, extracted: ExtractedDocument, structured: StructuredForm
    ) -> FormDefinition:
        """Build a deterministic e-Service FormDefinition."""
        ...

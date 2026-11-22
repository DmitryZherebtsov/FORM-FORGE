"""Extractor for image files (.jpg, .jpeg, .png, .tiff) using rapidocr-onnxruntime."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError
from rapidocr_onnxruntime import RapidOCR

from coi_form_digitization.domain.exceptions import DocumentProcessingError
from coi_form_digitization.domain.extracted_document import (
    CheckboxItem,
    ExtractedDocument,
    ExtractedPage,
    KeyValuePair,
)
from coi_form_digitization.domain.ports import DocumentExtractorPort
from coi_form_digitization.infrastructure.extractors.base import parse_line_elements


class ImageOcrExtractor(DocumentExtractorPort):
    """On-premise OCR extractor using locally bundled models for JPEG, PNG, and TIFF."""

    def __init__(self) -> None:
        self._engine: RapidOCR | None = None

    def _get_engine(self) -> RapidOCR:
        if self._engine is None:
            self._engine = RapidOCR()
        return self._engine

    def supports(self, extension: str) -> bool:
        return extension.lower() in ("jpg", "jpeg", "jpe", "png", "tiff")

    def extract(self, filename: str, data: bytes) -> ExtractedDocument:
        try:
            # Verify and normalize image orientation via EXIF transpose
            with Image.open(io.BytesIO(data)) as img:
                transposed_img = ImageOps.exif_transpose(img)
                transposed_img.load()
                # Re-encode to in-memory bytes for OCR engine
                img_byte_arr = io.BytesIO()
                fmt = img.format if img.format in ("JPEG", "PNG") else "PNG"
                transposed_img.save(img_byte_arr, format=fmt)
                ocr_input_bytes = img_byte_arr.getvalue()
        except (UnidentifiedImageError, Exception) as exc:
            raise DocumentProcessingError(f"Corrupted or invalid image file: {exc}") from exc

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"

        try:
            engine = self._get_engine()
            ocr_results, _ = engine(ocr_input_bytes)
        except Exception as exc:
            raise DocumentProcessingError(f"OCR engine execution failed: {exc}") from exc

        headings: list[str] = []
        paragraphs: list[str] = []
        key_values: list[KeyValuePair] = []
        checkboxes: list[CheckboxItem] = []
        raw_lines: list[str] = []

        if ocr_results:
            # rapidocr returns list of [box, text, score]
            for item in ocr_results:
                text = item[1].strip()
                score = float(item[2])
                if not text or score < 0.2:
                    continue

                raw_lines.append(text)
                cbs, kv = parse_line_elements(text)
                if cbs:
                    checkboxes.extend(cbs)
                elif kv:
                    key_values.append(kv)
                else:
                    if len(text) < 40 and text.isupper():
                        headings.append(text)
                    else:
                        paragraphs.append(text)

        page = ExtractedPage(
            page_number=1,
            headings=headings,
            paragraphs=paragraphs,
            key_values=key_values,
            tables=[],
            checkboxes=checkboxes,
            raw_text="\n".join(raw_lines),
        )

        return ExtractedDocument(
            filename=filename,
            format=ext,
            pages=[page],
            metadata={"ocr_engine": "rapidocr-onnxruntime", "detections_count": len(raw_lines)},
        )

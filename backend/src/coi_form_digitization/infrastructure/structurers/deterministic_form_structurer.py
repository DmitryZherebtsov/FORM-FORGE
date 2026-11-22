"""Self-contained semantic structuring based on deterministic Polish form heuristics."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

from coi_form_digitization.domain.extracted_document import (
    CheckboxItem,
    ExtractedDocument,
    KeyValuePair,
    TableData,
)
from coi_form_digitization.domain.ports import FormStructurerPort
from coi_form_digitization.domain.structured_form import (
    ChoiceGroup,
    ChoiceOption,
    FieldType,
    FormField,
    FormSection,
    StructuredForm,
)

_POLISH_TRANSLITERATION = str.maketrans(
    {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
)
_DATE_PATTERNS = (
    re.compile(r"^\d{2}\.\d{2}\.\d{4}$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{2}-\d{2}-\d{4}$"),
)
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_PATTERN = re.compile(r"^(?:\+48\s?)?(?:\d{3}[\s-]?\d{3}[\s-]?\d{3})$")
_BINARY_POSITIVE = ("tak", "yes")
_BINARY_NEGATIVE = ("nie", "no")


def slugify(value: str) -> str:
    """Transliterate text into a lowercase ASCII snake_case slug."""
    normalized = unicodedata.normalize("NFKD", value.casefold().translate(_POLISH_TRANSLITERATION))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    return slug or "field"


class _Slugger:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def unique(self, value: str, prefix: str) -> str:
        base = slugify(value)
        if base[0].isdigit():
            base = f"{prefix}_{base}"
        count = self._counts.get(base, 0) + 1
        self._counts[base] = count
        return base if count == 1 else f"{base}_{count}"


@dataclass
class _SectionBuilder:
    title: str
    fields: list[FormField] = field(default_factory=list)
    checkboxes: list[CheckboxItem] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)


class DeterministicFormStructurer(FormStructurerPort):
    """Build a validated form model without network or model dependencies."""

    def structure(self, extracted: ExtractedDocument) -> StructuredForm:
        section_builders: list[_SectionBuilder] = []
        sections_by_title: dict[str, _SectionBuilder] = {}
        current_section: _SectionBuilder | None = None

        def get_section(title: str) -> _SectionBuilder:
            key = title.casefold().strip()
            existing = sections_by_title.get(key)
            if existing is not None:
                return existing
            section = _SectionBuilder(title=title)
            sections_by_title[key] = section
            section_builders.append(section)
            return section

        field_slugger = _Slugger()
        for page in extracted.pages:
            page_headings = [heading.strip() for heading in page.headings if heading.strip()]
            for heading in page_headings:
                current_section = get_section(heading)

            if current_section is None and (
                page.key_values or page.checkboxes or page.tables or page.paragraphs
            ):
                current_section = get_section("General")

            if current_section is not None:
                current_section.fields.extend(
                    self._make_field(pair, field_slugger) for pair in page.key_values
                )
                current_section.checkboxes.extend(page.checkboxes)
                current_section.tables.extend(page.tables)

        sections: list[FormSection] = []
        all_fields: list[FormField] = []
        section_slugger = _Slugger()
        choice_slugger = _Slugger()
        for order, builder in enumerate(section_builders, start=1):
            groups = self._make_choice_groups(builder.checkboxes, choice_slugger)
            sections.append(
                FormSection(
                    section_id=section_slugger.unique(builder.title, "section"),
                    title=builder.title,
                    order=order,
                    fields=builder.fields,
                    choice_groups=groups,
                    tables=builder.tables,
                )
            )
            all_fields.extend(builder.fields)

        confidence = (
            sum(item.confidence for item in all_fields) / len(all_fields) if all_fields else 0.0
        )
        headings = [
            heading.strip()
            for page in extracted.pages
            for heading in page.headings
            if heading.strip()
        ]
        return StructuredForm(
            filename=extracted.filename,
            format=extracted.format,
            form_title=headings[0] if headings else None,
            sections=sections,
            total_fields=len(all_fields),
            fields_needing_review=sum(item.needs_review for item in all_fields),
            overall_confidence=confidence,
        )

    def _make_field(self, pair: KeyValuePair, slugger: _Slugger) -> FormField:
        field_type = self._infer_type(pair.key, pair.value)
        is_valid, validation_error = self._validate(field_type, pair.value)
        empty = not pair.value.strip()
        return FormField(
            field_id=slugger.unique(pair.key, "field"),
            label=pair.key,
            field_type=field_type,
            value=pair.value,
            is_valid=is_valid,
            validation_error=validation_error,
            confidence=pair.confidence,
            needs_review=not is_valid or empty or pair.confidence < 0.80,
        )

    @staticmethod
    def _infer_type(key: str, value: str) -> FieldType:
        label = key.casefold()
        value = value.strip()
        if "pesel" in label or re.fullmatch(r"\d{11}", value):
            return FieldType.PESEL
        if "nip" in label:
            return FieldType.NIP
        if "regon" in label:
            return FieldType.REGON
        if any(word in label for word in ("kod pocztowy", "postal")) or re.fullmatch(
            r"\d{2}-\d{3}", value
        ):
            return FieldType.POSTAL_CODE
        if any(word in label for word in ("data", "urodzenia", "date")) or any(
            pattern.fullmatch(value) for pattern in _DATE_PATTERNS
        ):
            return FieldType.DATE
        if any(word in label for word in ("e-mail", "email", "mail")) or _EMAIL_PATTERN.fullmatch(
            value
        ):
            return FieldType.EMAIL
        if any(
            word in label for word in ("telefon", "phone", "komórk", "komork")
        ) or _PHONE_PATTERN.fullmatch(value):
            return FieldType.PHONE
        return FieldType.TEXT

    @staticmethod
    def _validate(field_type: FieldType, value: str) -> tuple[bool, str | None]:
        if field_type is FieldType.PESEL:
            return DeterministicFormStructurer._validate_pesel(value)
        if field_type is FieldType.NIP:
            digits = re.sub(r"[-\s]", "", value)
            valid = bool(re.fullmatch(r"\d{10}", digits))
            if valid:
                weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
                valid = sum(
                    int(digit) * weight for digit, weight in zip(digits[:9], weights, strict=True)
                ) % 11 == int(digits[-1])
            return valid, None if valid else "Nieprawidłowy numer NIP"
        if field_type is FieldType.REGON:
            return DeterministicFormStructurer._validate_regon(value)
        if field_type is FieldType.POSTAL_CODE:
            valid = bool(re.fullmatch(r"\d{2}-\d{3}", value.strip()))
            return valid, None if valid else "Nieprawidłowy kod pocztowy"
        if field_type is FieldType.DATE:
            return DeterministicFormStructurer._validate_date(value)
        if field_type is FieldType.EMAIL:
            valid = bool(_EMAIL_PATTERN.fullmatch(value.strip()))
            return valid, None if valid else "Nieprawidłowy adres e-mail"
        if field_type is FieldType.PHONE:
            valid = bool(_PHONE_PATTERN.fullmatch(value.strip()))
            return valid, None if valid else "Nieprawidłowy numer telefonu"
        return True, None

    @staticmethod
    def _validate_pesel(value: str) -> tuple[bool, str | None]:
        digits = value.strip()
        if not re.fullmatch(r"\d{11}", digits):
            return False, "Numer PESEL musi zawierać 11 cyfr"
        weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
        checksum = (
            10
            - sum(int(digit) * weight for digit, weight in zip(digits[:10], weights, strict=True))
            % 10
        ) % 10
        if checksum != int(digits[10]):
            return False, "Nieprawidłowa suma kontrolna numeru PESEL"
        month_code = int(digits[2:4])
        century_offsets = ((1, 12, 0), (21, 32, 20), (41, 52, 40), (61, 72, 60), (81, 92, 80))
        for minimum, maximum, offset in century_offsets:
            if minimum <= month_code <= maximum:
                month = month_code - offset
                year = int(digits[:2]) + (1900 + offset)
                try:
                    date(year, month, int(digits[4:6]))
                except ValueError:
                    return False, "Nieprawidłowa data urodzenia w numerze PESEL"
                return True, None
        return False, "Nieprawidłowa data urodzenia w numerze PESEL"

    @staticmethod
    def _validate_regon(value: str) -> tuple[bool, str | None]:
        digits = re.sub(r"[-\s]", "", value)
        if not re.fullmatch(r"(?:\d{9}|\d{14})", digits):
            return False, "Numer REGON musi zawierać 9 lub 14 cyfr"
        weights9 = (8, 9, 2, 3, 4, 5, 6, 7)
        check9 = (
            sum(int(digit) * weight for digit, weight in zip(digits[:8], weights9, strict=True))
            % 11
            % 10
        )
        if check9 != int(digits[8]):
            return False, "Nieprawidłowa suma kontrolna numeru REGON"
        if len(digits) == 14:
            weights14 = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)
            check14 = (
                sum(
                    int(digit) * weight
                    for digit, weight in zip(digits[:13], weights14, strict=True)
                )
                % 11
                % 10
            )
            if check14 != int(digits[13]):
                return False, "Nieprawidłowa suma kontrolna 14-cyfrowego numeru REGON"
        return True, None

    @staticmethod
    def _validate_date(value: str) -> tuple[bool, str | None]:
        value = value.strip()
        formats = ("%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y")
        for pattern, date_format in zip(_DATE_PATTERNS, formats, strict=True):
            if pattern.fullmatch(value):
                try:
                    datetime.strptime(value, date_format)
                except ValueError:
                    return False, "Nieprawidłowa data"
                return True, None
        return False, "Data musi mieć format DD.MM.RRRR, RRRR-MM-DD lub DD-MM-RRRR"

    @staticmethod
    def _make_choice_groups(checkboxes: list[CheckboxItem], slugger: _Slugger) -> list[ChoiceGroup]:
        groups: list[ChoiceGroup] = []
        index = 0
        while index < len(checkboxes):
            current = checkboxes[index]
            if index + 1 < len(checkboxes) and DeterministicFormStructurer._is_binary_pair(
                current.label, checkboxes[index + 1].label
            ):
                pair = checkboxes[index : index + 2]
                selected_count = sum(item.is_checked for item in pair)
                groups.append(
                    ChoiceGroup(
                        group_id=slugger.unique(current.label, "choice"),
                        label=None,
                        selection_type="single",
                        options=[ChoiceOption(item.label, item.is_checked) for item in pair],
                        needs_review=selected_count != 1,
                    )
                )
                index += 2
                continue

            remaining = [current]
            index += 1
            while index < len(checkboxes) and not (
                index + 1 < len(checkboxes)
                and DeterministicFormStructurer._is_binary_pair(
                    checkboxes[index].label, checkboxes[index + 1].label
                )
            ):
                remaining.append(checkboxes[index])
                index += 1
            groups.append(
                ChoiceGroup(
                    group_id=slugger.unique(remaining[0].label, "choice"),
                    label=None,
                    selection_type="multiple",
                    options=[ChoiceOption(item.label, item.is_checked) for item in remaining],
                    needs_review=False,
                )
            )
        return groups

    @staticmethod
    def _is_binary_pair(first: str, second: str) -> bool:
        def matches(label: str, tokens: tuple[str, ...]) -> bool:
            normalized = re.sub(r"[^a-z ]", " ", label.casefold()).strip()
            return any(normalized == token or normalized.startswith(f"{token} ") for token in tokens)

        return (matches(first, _BINARY_POSITIVE) and matches(second, _BINARY_NEGATIVE)) or (
            matches(first, _BINARY_NEGATIVE) and matches(second, _BINARY_POSITIVE)
        )

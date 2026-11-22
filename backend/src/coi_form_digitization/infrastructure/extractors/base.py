"""Base class and common helpers for document extractors."""

import re
import unicodedata

from coi_form_digitization.domain.extracted_document import CheckboxItem, KeyValuePair

# Regular expressions for identifying checkboxes and key-value pairs
# Matches checkbox markers: [ ], [x], [X], [v], [V], ( ), (x), (X), or unicode box characters
_CHECKBOX_MARK_PATTERN = re.compile(
    r"(?:\[([ xXvV])\]|[\u2610\u2611\u2612\u25a1\u25a0]|\(([\s xX])\))"
)
# Matches key-value pairs requiring at least one non-whitespace character in the value
_KV_PATTERN = re.compile(r"^([^:\n]{2,60}):\s*(\S.*)$")
_BLANK_FIELD_PATTERN = re.compile(r"[.\u2026\u00b7_‐‑‒–—-]+")
_FIELD_PROMPT_CUE_PATTERN = re.compile(
    r"\b(?:imie|nazwisk\w*|nazwa|nip|pesel|regon|adres|miejscow\w*|ulic\w*|nr|numer|"
    r"kod\s+pocztowy|data|wysokosc|kwot\w*|oplat\w*|organ\w*|rachun\w*|podpis\w*|"
    r"wlasciciel\w*|uzasadnien\w*|telefon\w*|poczty\s+elektronicznej|e[\s-]?mail)\b"
)
_EMBEDDED_FIELD_PROMPT_PATTERN = re.compile(
    r"^(?:uzasadnien\w*|opis\w*|uwag\w*|wyjasnien\w*|adres|data|nazwa|numer|nr|"
    r"imie|nazwisk\w*|pesel|nip|regon|kwot\w*|wysokosc|kod\s+pocztowy)\b"
)
_FIELD_PROMPT_INSTRUCTION_PATTERN = re.compile(
    r"\b(?:wypeln\w*|oznacz\w*|zaznacz\w*|postaw\w*|wybierz\w*|wpis\w*|opisz\w*|"
    r"podaj\w*|uzupeln\w*|nalezy|jesli|jezeli|w\s+przypadku|ponizej)\b"
)
_FIELD_PROMPT_NONFIELD_PATTERN = re.compile(
    r"^(?:urzad|wniosek|instrukcja|informacje\s+dotyczace|zalaczniki|podstawa\s+prawna|"
    r"strona|gotowka|przelewem|osobiscie|elektronicznie|dokument\s+stwierdzajacy|"
    r"dowod\s+uiszczenia|art)\b"
)
_FIELD_PROMPT_SENTENCE_PATTERN = re.compile(
    r"\b(?:ktory|ktora|ktore|ktorym|ktorej|ktorego|jest|sa|byl\w*|bed\w*|zaplacon\w*)\b"
)
_POLISH_DIACRITICS = str.maketrans({"ł": "l", "Ł": "L"})


def parse_checkboxes(line: str) -> list[CheckboxItem]:
    """Parse all checkboxes occurring in a single line, with their respective labels."""
    matches = list(_CHECKBOX_MARK_PATTERN.finditer(line))
    if not matches:
        return []

    checkboxes: list[CheckboxItem] = []
    for i, match in enumerate(matches):
        mark = match.group(1) or match.group(2)
        matched_str = match.group(0)
        is_checked = (
            mark.strip().lower() in ("x", "v")
            if mark is not None
            else (matched_str in ("\u2611", "\u2612", "\u25a0"))
        )

        label_start = match.end()
        label_end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
        label = line[label_start:label_end].strip()

        if label:
            checkboxes.append(CheckboxItem(label=label, is_checked=is_checked))

    return checkboxes


def parse_line_elements(
    line: str,
) -> tuple[list[CheckboxItem], KeyValuePair | None]:
    """Inspect a line for checkbox options or key-value structures.

    Returns:
        (checkboxes_list, key_value_or_none)
    """
    cleaned = line.strip()
    if not cleaned:
        return [], None

    checkboxes = parse_checkboxes(cleaned)
    if checkboxes:
        return checkboxes, None

    kv_match = _KV_PATTERN.match(cleaned)
    if kv_match:
        key = kv_match.group(1).strip()
        val = kv_match.group(2).strip()
        if key[-1:].isdigit() and val[:1].isdigit():
            return [], None
        if _BLANK_FIELD_PATTERN.fullmatch(val):
            val = ""
        # Avoid false positive headings like "Uwaga:" with no key semantic or URLs
        if len(key) >= 2 and not key.lower().startswith(("http", "https")):
            return [], KeyValuePair(key=key, value=val)

    return [], None


def parse_standalone_field_prompt(line: str) -> KeyValuePair | None:
    """Recognize a short textbox label without treating headings or instructions as fields."""
    text = line.strip()
    if not text:
        return None

    parenthetical = re.fullmatch(r"\(\s*([^()]+?)\s*\)", text)
    embedded = re.fullmatch(r"\s*\d+(?:\.\d+)*\.?\s+([^()]+?)\s*\(([^()]*)\)?\s*", text)
    if parenthetical:
        label = parenthetical.group(1).strip()
    elif embedded:
        label = embedded.group(1).strip()
        if not _EMBEDDED_FIELD_PROMPT_PATTERN.search(_normalize_prompt_text(label)):
            return None
    else:
        label = text
        if re.match(r"^\s*\d+(?:\.\d+)*\.?\s+", label):
            return None
        if not label[:1].isupper():
            return None

    label = label.rstrip(" ,;:").strip()
    if not 2 <= len(label) <= 80 or len(label.split()) > 10:
        return None
    if re.search(r"[.!?;:]$", label):
        return None

    normalized = _normalize_prompt_text(label)
    if (
        _FIELD_PROMPT_INSTRUCTION_PATTERN.search(normalized)
        or _FIELD_PROMPT_NONFIELD_PATTERN.search(normalized)
        or _FIELD_PROMPT_SENTENCE_PATTERN.search(normalized)
        or not _FIELD_PROMPT_CUE_PATTERN.search(normalized)
    ):
        return None

    return KeyValuePair(key=label, value="")


def _normalize_prompt_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.translate(_POLISH_DIACRITICS).casefold())
    return normalized.encode("ascii", "ignore").decode("ascii")


def parse_table_row_key_value(cells: list[str]) -> KeyValuePair | None:
    """Recognize a two-cell form row, including an empty right-hand entry cell."""
    candidate_cells = cells if len(cells) == 2 else [cell for cell in cells if cell]
    if len(candidate_cells) != 2:
        return None

    key, value = (cell.strip() for cell in candidate_cells)
    if not key or len(key) >= 60 or parse_checkboxes(key) or parse_checkboxes(value):
        return None
    if value and _BLANK_FIELD_PATTERN.fullmatch(value):
        value = ""
    return KeyValuePair(key=key, value=value)

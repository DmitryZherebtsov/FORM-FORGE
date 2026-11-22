"""Deterministic mapping from structured forms to COI import JSON models."""

import html
import re
import unicodedata
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from coi_form_digitization.domain.extracted_document import ExtractedDocument
from coi_form_digitization.domain.form_definition import (
    ComponentType,
    ConsentItem,
    ConsentSectionConfig,
    FieldState,
    FlowLink,
    FormDefinition,
    FormFlow,
    FormOption,
    FormQuestion,
    FormQuestionField,
    FormTab,
    TabType,
)
from coi_form_digitization.domain.ports import FormDefinitionMapperPort
from coi_form_digitization.domain.structured_form import (
    ChoiceGroup,
    FieldType,
    FormField,
    FormSection,
    StructuredForm,
)

_EMPTY_HTML = "<html><head></head><body></body></html>"
_FINISH_NOTICE = "Zanim wyślesz wniosek, sprawdź uzupełnione dane na podglądzie."
_ROMAN_FORM_PATTERN = re.compile(r"^\s*(I|II|III|IV|V|VI|VII|VIII|IX|X)\.\s*(.+?)\s*$", re.IGNORECASE)
_ROMAN_ONLY_PATTERN = re.compile(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\.$", re.IGNORECASE)
_OPTIONAL_TERMS = ("opcjonalnie", "nieobowiązkowe", "nieobowiazkowe")
_ATTACHMENT_TERMS = ("zalacznik", "pelnomocnictwo", "dowod oplaty", "plik", "skan")
_TEXTAREA_TERMS = ("uzasadnienie", "opis", "uwagi", "wyjasnienie")
_NUMBER_TERMS = ("kwota", "powierzchnia", "liczba", "ilosc", "wysokosc", "stawka")
_DICTIONARY_TERMS = (
    ("numer kierunkowy", "Numery kierunkowe"),
    ("wojewodztwo", "Województwo"),
    ("miejscowosc", "Miejscowość"),
    ("powiat", "Powiat"),
    ("gmina", "Gmina"),
    ("kraj", "Kraje"),
)
_YES_CONDITION_PATTERN = re.compile(
    r"(?:w przypadku zaznaczenia|jeżeli|jezeli|jeśli|jesli|gdy).{0,100}\btak\b",
    re.IGNORECASE,
)
_REPEATABLE_TERMS = (
    "pies",
    "zajecie pasa",
    "podopieczn",
    "uczestnik",
    "dziecko",
    "dzieci",
    "pozycja",
)


@dataclass(frozen=True)
class _ApplicationPart:
    roman: str
    option_name: str


@dataclass(frozen=True)
class _RadioSelector:
    tab_title: str
    section_tech_name: str
    tech_name: str
    options: tuple[str, ...]
    section_index: int


class DeterministicFormDefinitionMapper(FormDefinitionMapperPort):
    """Build stable COI tabs, fields, validators, and flow links without external services."""

    def build_definition(
        self, extracted: ExtractedDocument, structured: StructuredForm
    ) -> FormDefinition:
        title = (structured.form_title or "").strip() or extracted.filename
        title = title[:255]
        seed = f"{extracted.filename}|{title}"
        sections = structured.sections or [
            FormSection(
                section_id="dane_wniosku",
                title="Dane wniosku",
                order=1,
                fields=[],
                choice_groups=[],
                tables=[],
            )
        ]
        parts = _find_application_parts(sections)
        if len(parts) >= 2:
            tabs = self._build_multi_application_tabs(sections, parts, seed, extracted)
        else:
            tabs = self._build_main_tabs(sections, seed, extracted)

        consent_items = _find_consent_items(extracted)
        if consent_items:
            _append_consent_tab(tabs, consent_items, seed)

        tabs.append(_finish_tab(seed))
        links = [
            FlowLink(
                id=_stable_id(seed, "flow", str(index)),
                source=tabs[index].id,
                target=tabs[index + 1].id,
            )
            for index in range(len(tabs) - 1)
        ]
        return FormDefinition(title=title, tabs=tabs, flow=FormFlow(links=links))

    def _build_multi_application_tabs(
        self,
        sections: list[FormSection],
        parts: list[_ApplicationPart],
        seed: str,
        extracted: ExtractedDocument,
    ) -> list[FormTab]:
        selector_title = "Rodzaj wniosku"
        selector_question = _application_selector_question(parts, seed)
        section_parts = _assign_application_parts(sections, parts)
        tab_questions: list[FormQuestion] = [selector_question]
        tabs = [
            FormTab(
                id=_stable_id(seed, "tab", "selector"),
                title=selector_title,
                type=TabType.MAIN,
                questions=tab_questions,
            )
        ]

        initial = [
            index
            for index, roman in enumerate(section_parts)
            if roman is None and not _ROMAN_ONLY_PATTERN.fullmatch(sections[index].title.strip())
        ]
        if initial:
            for index in initial:
                tab_questions.append(
                    _section_question(
                        sections[index],
                        seed,
                        selector_title,
                        index,
                        y=len(tab_questions),
                        extra_states=[],
                        prior_selectors=[],
                        extracted=extracted,
                    )
                )

        for part_index, part in enumerate(parts):
            section_indexes = [
                index for index, roman in enumerate(section_parts) if roman == part.roman
            ]
            if not section_indexes:
                continue
            part_tab_title = part.option_name
            part_questions: list[FormQuestion] = []
            prior_selectors: list[_RadioSelector] = []
            for index in section_indexes:
                state = _application_show_state(part.option_name, selector_title)
                part_questions.append(
                    _section_question(
                        sections[index],
                        seed,
                        part_tab_title,
                        index,
                        y=len(part_questions),
                        extra_states=[state],
                        prior_selectors=prior_selectors,
                        extracted=extracted,
                    )
                )
                prior_selectors.extend(
                    _selectors_for_section(sections[index], part_tab_title, index)
                )
            tabs.append(
                FormTab(
                    id=_stable_id(seed, "tab", f"application:{part_index}:{part.roman}"),
                    title=part_tab_title,
                    type=TabType.MAIN,
                    questions=part_questions,
                )
            )
        return tabs

    def _build_main_tabs(
        self, sections: list[FormSection], seed: str, extracted: ExtractedDocument
    ) -> list[FormTab]:
        groups = _group_sections_into_tabs(sections)
        tabs: list[FormTab] = []
        prior_selectors: list[_RadioSelector] = []
        for group_index, (tab_title, indexed_sections) in enumerate(groups):
            questions: list[FormQuestion] = []
            for index, section in indexed_sections:
                questions.append(
                    _section_question(
                        section,
                        seed,
                        tab_title,
                        index,
                        y=len(questions),
                        extra_states=[],
                        prior_selectors=prior_selectors,
                        extracted=extracted,
                    )
                )
                prior_selectors.extend(_selectors_for_section(section, tab_title, index))
            tabs.append(
                FormTab(
                    id=_stable_id(seed, "tab", f"main:{group_index}:{tab_title}"),
                    title=tab_title,
                    type=TabType.MAIN,
                    questions=questions,
                )
            )
        return tabs


def _section_question(
    section: FormSection,
    seed: str,
    tab_title: str,
    section_index: int,
    y: int,
    extra_states: list[FieldState],
    prior_selectors: list[_RadioSelector],
    extracted: ExtractedDocument,
) -> FormQuestion:
    section_tech_name = _section_tech_name(section)
    own_selectors = _selectors_for_section(section, tab_title, section_index)
    selectors = [*prior_selectors, *own_selectors]
    child_questions: list[FormQuestion] = []
    child_y = 0
    field_index = 0

    while field_index < len(section.fields):
        current = section.fields[field_index]
        if (
            field_index + 1 < len(section.fields)
            and _should_pair_fields(current.label, section.fields[field_index + 1].label)
        ):
            next_field = section.fields[field_index + 1]
            for x, item in enumerate((current, next_field)):
                child_questions.append(
                    _field_question(
                        item,
                        seed,
                        f"{section.section_id}:field:{field_index + x}",
                        section,
                        child_y,
                        x,
                        1,
                        field_index + x,
                        selectors,
                        section_index,
                        extracted,
                    )
                )
            child_y += 1
            field_index += 2
            continue

        child_questions.append(
            _field_question(
                current,
                seed,
                f"{section.section_id}:field:{field_index}",
                section,
                child_y,
                0,
                3,
                field_index,
                selectors,
                section_index,
                extracted,
            )
        )
        child_y += 1
        field_index += 1

    for group_index, group in enumerate(section.choice_groups):
        child_questions.append(
            _choice_question(
                group,
                seed,
                f"{section.section_id}:choice:{group_index}",
                child_y,
                len(section.fields) + group_index,
            )
        )
        child_y += 1

    for table_index, table in enumerate(section.tables):
        child_questions.append(
            _table_question(
                table.headers,
                table.title or section.title,
                seed,
                f"{section.section_id}:table:{table_index}",
                child_y,
                len(section.fields) + len(section.choice_groups) + table_index,
            )
        )
        child_y += 1

    if any(term in _normalize(section.title) for term in _REPEATABLE_TERMS) and child_questions:
        repeat_field = FormQuestionField(
            id=_stable_id(seed, f"{section.section_id}:repeat"),
            type=ComponentType.REPEATING_SECTION,
            tech_name=f"{section_tech_name}_items",
            title=section.title,
            description=_EMPTY_HTML,
            repeating_section_grid=child_questions,
            question_order=0,
        )
        child_questions = [FormQuestion(x=0, y=0, rows=1, cols=3, field=repeat_field)]

    parent_states = [*extra_states]
    parent_states.extend(
        _states_for_target(
            section.title,
            prior_selectors,
            section_index,
            _has_yes_condition(extracted),
        )
    )
    parent = FormQuestionField(
        id=_stable_id(seed, f"{section.section_id}:section"),
        type=ComponentType.SECTION,
        tech_name=section_tech_name,
        title=section.title,
        description=_EMPTY_HTML,
        repeating_section_grid=child_questions,
        states=_unique_states(parent_states),
        question_order=section.order,
    )
    return FormQuestion(x=0, y=y, rows=1, cols=3, field=parent)


def _field_question(
    item: FormField,
    seed: str,
    path: str,
    section: FormSection,
    y: int,
    x: int,
    cols: int,
    order: int,
    selectors: list[_RadioSelector],
    section_index: int,
    extracted: ExtractedDocument,
) -> FormQuestion:
    component, dictionary = _component_for_field(item)
    validation = _field_validations(item)
    default_value: str | list[str] | None = item.value if item.value else None
    default_value_type: str | None = None
    read_only = False
    external = _external_default(item.label) if _is_applicant_section(section.title) else None
    if external:
        default_value = external
        default_value_type = "EXTERNAL_SYSTEM"
        read_only = True
    elif dictionary == "Kraje":
        default_value = ["Polska"]
    elif dictionary:
        default_value = []

    states = _states_for_target(
        item.label, selectors, section_index, _has_yes_condition(extracted)
    )
    field = FormQuestionField(
        id=_stable_id(seed, path),
        type=component,
        tech_name=_slug(item.field_id),
        title=item.label,
        description="",
        validation=validation,
        dictionary_name=dictionary,
        read_only=read_only,
        default_value=default_value,
        default_value_type=default_value_type,
        states=_unique_states(states),
        question_order=order,
        multi_level_tree=True if dictionary else None,
        search_enabled=True if dictionary else None,
    )
    return FormQuestion(x=x, y=y, rows=1, cols=cols, field=field)


def _choice_question(
    group: ChoiceGroup, seed: str, path: str, y: int, order: int
) -> FormQuestion:
    options = [
        FormOption(id=option.label, name=option.label, tech_name=_slug(option.label))
        for option in group.options
    ]
    field = FormQuestionField(
        id=_stable_id(seed, path),
        type=ComponentType.RADIO if group.selection_type == "single" else ComponentType.CHECKBOX,
        tech_name=_group_tech_name(group),
        title=group.label or "Wybierz opcję",
        options=options,
        validation=_required_validation(group.label or ""),
        question_order=order,
    )
    return FormQuestion(x=0, y=y, rows=1, cols=3, field=field)


def _table_question(
    headers: list[str], title: str, seed: str, path: str, y: int, order: int
) -> FormQuestion:
    child_questions: list[FormQuestion] = []
    for index, header in enumerate(headers):
        component, dictionary = _component_for_label(header)
        field = FormQuestionField(
            id=_stable_id(seed, f"{path}:column:{index}"),
            type=component,
            tech_name=f"{_slug(header)}_{index + 1}",
            title=header,
            validation=_required_validation(header),
            dictionary_name=dictionary,
            question_order=index,
            multi_level_tree=True if dictionary else None,
            search_enabled=True if dictionary else None,
        )
        child_questions.append(
            FormQuestion(x=index % 3, y=index // 3, rows=1, cols=1, field=field)
        )

    field = FormQuestionField(
        id=_stable_id(seed, path),
        type=ComponentType.REPEATING_SECTION,
        tech_name=_slug(title),
        title=title,
        description=_EMPTY_HTML,
        repeating_section_grid=child_questions,
        question_order=order,
    )
    return FormQuestion(x=0, y=y, rows=1, cols=3, field=field)


def _application_selector_question(parts: list[_ApplicationPart], seed: str) -> FormQuestion:
    options = [
        FormOption(id=part.option_name, name=part.option_name, tech_name=_slug(part.option_name))
        for part in parts
    ]
    field = FormQuestionField(
        id=_stable_id(seed, "selector:application"),
        type=ComponentType.RADIO,
        tech_name="rodzaj_wniosku",
        title="Rodzaj wniosku",
        options=options,
        validation=["REQUIRED"],
        question_order=0,
    )
    return FormQuestion(x=0, y=0, rows=1, cols=3, field=field)


def _application_show_state(option_name: str, selector_tab_title: str) -> FieldState:
    query = _show_query(option_name, selector_tab_title, "rodzaj_wniosku")
    return FieldState(type="SHOW", query=query)


def _show_query(
    option_name: str,
    tab_title: str,
    selector_tech_name: str,
    selector_section_tech_name: str | None = None,
) -> str:
    escaped_tab = tab_title.replace("'", "\\'")
    answer = (
        f"tabs['{escaped_tab}' in title].questions['{selector_tech_name}' in field.techName].field.__userAnswer"
    )
    if selector_section_tech_name:
        answer = (
            f"tabs['{escaped_tab}' in title].questions['{selector_section_tech_name}' in field.techName]"
            f".field.repeatingSectionGrid['{selector_tech_name}' in field.techName].field.__userAnswer"
        )
    return f"({_jsonata_string(option_name)} in {answer})"


def _selectors_for_section(
    section: FormSection, tab_title: str, section_index: int
) -> list[_RadioSelector]:
    section_tech_name = _section_tech_name(section)
    selectors = []
    for group in section.choice_groups:
        if group.selection_type != "single":
            continue
        selectors.append(
            _RadioSelector(
                tab_title=tab_title,
                section_tech_name=section_tech_name,
                tech_name=_group_tech_name(group),
                options=tuple(option.label for option in group.options),
                section_index=section_index,
            )
        )
    return selectors


def _states_for_target(
    target: str,
    selectors: list[_RadioSelector],
    target_section_index: int,
    has_yes_condition: bool,
) -> list[FieldState]:
    normalized_target = _normalize(target)
    states = []
    for selector in selectors:
        if selector.section_index > target_section_index:
            continue
        for option in selector.options:
            normalized_option = _normalize(option)
            matches = False
            if normalized_option in {"inny", "inna", "inne", "innych"}:
                matches = bool(re.search(r"\binny\w*\b|\binna\w*\b|\binne\w*\b", normalized_target))
            elif normalized_option == "pelnomocnik":
                matches = "pelnomocnik" in normalized_target
            elif normalized_option == "tak":
                matches = (
                    has_yes_condition
                    and target_section_index == selector.section_index + 1
                )
            if matches:
                states.append(
                    FieldState(
                        type="SHOW",
                        query=_show_query(
                            option,
                            selector.tab_title,
                            selector.tech_name,
                            selector.section_tech_name,
                        ),
                    )
                )
    return states


def _group_sections_into_tabs(
    sections: list[FormSection],
) -> list[tuple[str, list[tuple[int, FormSection]]]]:
    if len(sections) <= 3:
        return [("Dane", list(enumerate(sections)))]

    groups: dict[str, list[tuple[int, FormSection]]] = {
        "Dane wnioskodawcy": [],
        "Szczegóły wniosku": [],
        "Kontakt i załączniki": [],
    }
    for index, section in enumerate(sections):
        text = _normalize(
            " ".join(
                [section.title, *(item.label for item in section.fields)]
            )
        )
        if any(term in text for term in ("kontakt", "telefon", "email", "e-mail", "zalacz", "zgod")):
            group_title = "Kontakt i załączniki"
        elif any(term in text for term in ("wnioskodawc", "pesel", "nazwisko", "adres zamieszkania")):
            group_title = "Dane wnioskodawcy"
        else:
            group_title = "Szczegóły wniosku"
        groups[group_title].append((index, section))
    return [(title, rows) for title, rows in groups.items() if rows]


def _find_application_parts(sections: list[FormSection]) -> list[_ApplicationPart]:
    parts: list[_ApplicationPart] = []
    seen: set[str] = set()
    for section in sections:
        match = _ROMAN_FORM_PATTERN.match(section.title)
        if not match:
            continue
        roman = match.group(1).upper()
        suffix = match.group(2).strip()
        normalized = _normalize(suffix)
        if not any(term in normalized for term in ("wniosek", "stypendium", "nagrod", "wyrozn")):
            continue
        if roman not in seen:
            parts.append(_ApplicationPart(roman=roman, option_name=suffix))
            seen.add(roman)
    return parts


def _assign_application_parts(
    sections: list[FormSection], parts: list[_ApplicationPart]
) -> list[str | None]:
    allowed = {part.roman for part in parts}
    assigned: list[str | None] = []
    current: str | None = None
    for section in sections:
        match = _ROMAN_FORM_PATTERN.match(section.title)
        if match and match.group(1).upper() in allowed:
            current = match.group(1).upper()
        assigned.append(current)
    return assigned


def _component_for_field(item: FormField) -> tuple[ComponentType, str | None]:
    return _component_for_label(item.label, item.field_type)


def _component_for_label(
    label: str, field_type: FieldType | None = None
) -> tuple[ComponentType, str | None]:
    normalized = _normalize(label)
    dictionary = next(
        (name for term, name in _DICTIONARY_TERMS if term in normalized), None
    )
    if dictionary:
        return ComponentType.SELECT, dictionary
    if any(term in normalized for term in _ATTACHMENT_TERMS):
        return ComponentType.FILE_UPLOADER, None
    if field_type is FieldType.DATE or "data" in normalized or "urodzeni" in normalized:
        return ComponentType.DATEPICKER, None
    if any(term in normalized for term in _NUMBER_TERMS):
        return ComponentType.NUMBER, None
    if any(term in normalized for term in _TEXTAREA_TERMS):
        return ComponentType.TEXTAREA, None
    if field_type is FieldType.CHECKBOX:
        return ComponentType.CHECKBOX, None
    return ComponentType.TEXT_FIELD, None


def _field_validations(item: FormField) -> list[str]:
    label = _normalize(item.label)
    validation = []
    if item.field_type is FieldType.PESEL or "pesel" in label:
        validation.append("PESEL")
    elif item.field_type is FieldType.NIP or "nip" in label:
        validation.append("NIP")
    elif item.field_type is FieldType.REGON or "regon" in label:
        validation.append("REGON")
    elif item.field_type is FieldType.POSTAL_CODE or "kod pocztowy" in label:
        validation.append("ZIP_CODE")
    elif item.field_type is FieldType.EMAIL or "email" in label or "e-mail" in label:
        validation.append("EMAIL")
    validation.extend(_required_validation(item.label))
    return validation


def _required_validation(label: str) -> list[str]:
    normalized = _normalize(label)
    return [] if any(term in normalized for term in _OPTIONAL_TERMS) else ["REQUIRED"]


def _external_default(label: str) -> str | None:
    normalized = _normalize(label).strip()
    if re.search(r"\bimie\b", normalized):
        return "PESEL.name"
    if "nazwisk" in normalized:
        return "PESEL.surname"
    if "pesel" in normalized:
        return "PESEL.pesel"
    return None


def _is_applicant_section(title: str) -> bool:
    normalized = _normalize(title)
    return "wnioskodawc" in normalized or "applicant" in normalized


def _should_pair_fields(first: str, second: str) -> bool:
    first_label, second_label = _normalize(first), _normalize(second)
    if "imie" in first_label and "nazwisk" in second_label:
        return True
    if "kod pocztowy" in first_label and "miejscowosc" in second_label:
        return True
    return ("telefon" in first_label and ("email" in second_label or "e-mail" in second_label))


def _section_tech_name(section: FormSection) -> str:
    return _slug(section.section_id or section.title)


def _group_tech_name(group: ChoiceGroup) -> str:
    return _slug(group.label or group.group_id)


def _append_consent_tab(
    tabs: list[FormTab], items: list[ConsentItem], seed: str
) -> None:
    tab_title = "Kontakt i załączniki"
    consent_field = FormQuestionField(
        id=_stable_id(seed, "consent"),
        type=ComponentType.CONSENT_SECTION,
        tech_name="zgoda",
        title="",
        consent_section_config=ConsentSectionConfig(consents=items, files=[]),
        validation=["REQUIRED"],
    )
    questions = [FormQuestion(x=0, y=0, rows=1, cols=3, field=consent_field)]
    existing = next(
        (tab for tab in tabs if tab.type is TabType.MAIN and tab.title == tab_title), None
    )
    if existing:
        index = tabs.index(existing)
        questions = [*existing.questions, FormQuestion(x=0, y=len(existing.questions), rows=1, cols=3, field=consent_field)]
        tabs[index] = FormTab(id=existing.id, title=existing.title, type=existing.type, questions=questions)
    else:
        tabs.append(
            FormTab(
                id=_stable_id(seed, "tab", "consent"),
                title=tab_title,
                type=TabType.MAIN,
                questions=questions,
            )
        )


def _find_consent_items(extracted: ExtractedDocument) -> list[ConsentItem]:
    items: list[ConsentItem] = []
    seen: set[str] = set()
    keywords = ("wyrazam zgode", "klauzula informacyjna", "przetwarzanie danych", "rodo")
    for page in extracted.pages:
        texts = [*page.paragraphs, *page.raw_text.splitlines()]
        for text in texts:
            cleaned = " ".join(text.split())
            if not cleaned or not any(term in _normalize(cleaned) for term in keywords):
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            items.append(
                ConsentItem(
                    description=f"<html><head></head><body><p>{html.escape(cleaned)}</p></body></html>",
                    required=True,
                )
            )
            seen.add(key)
    return items


def _finish_tab(seed: str) -> FormTab:
    field = FormQuestionField(
        id=_stable_id(seed, "finish:preview"),
        type=ComponentType.TEXT_BLOCK,
        tech_name="podglad_przed_wyslaniem",
        title="",
        description=f"<html><head></head><body><p>{html.escape(_FINISH_NOTICE)}</p></body></html>",
        question_order=0,
    )
    return FormTab(
        id=_stable_id(seed, "tab", "finish"),
        title="Strona końcowa",
        type=TabType.FINISH,
        questions=[FormQuestion(x=0, y=0, rows=1, cols=3, field=field)],
    )


def _has_yes_condition(extracted: ExtractedDocument) -> bool:
    text = "\n".join(
        "\n".join([*page.headings, *page.paragraphs, page.raw_text]) for page in extracted.pages
    )
    return bool(_YES_CONDITION_PATTERN.search(text))


def _unique_states(states: list[FieldState]) -> list[FieldState]:
    return list(dict.fromkeys(states))


def _jsonata_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _stable_id(seed: str, *parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "coi-form-definition:" + seed + ":" + ":".join(parts)))


def _slug(value: str) -> str:
    normalized = _normalize(value)
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "field"


def _normalize(value: str) -> str:
    lowered = value.casefold().replace("ł", "l")
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", lowered)
        if not unicodedata.combining(char)
    )

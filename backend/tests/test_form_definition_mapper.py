"""COI FormDefinition mapping and camelCase serialization tests."""

from coi_form_digitization.application.dtos import FormDefinitionDTO
from coi_form_digitization.domain.extracted_document import (
    ExtractedDocument,
    ExtractedPage,
    TableData,
)
from coi_form_digitization.domain.form_definition import ComponentType
from coi_form_digitization.domain.structured_form import (
    ChoiceGroup,
    ChoiceOption,
    FieldType,
    FormField,
    FormSection,
    StructuredForm,
)
from coi_form_digitization.infrastructure.structurers.coi_form_definition_mapper import (
    DeterministicFormDefinitionMapper,
)


def test_mapper_serializes_camel_case_grid_tabs_and_repeatable_tables() -> None:
    extracted = _extracted("Wniosek o dofinansowanie")
    section = _section(
        "dane_wnioskodawcy",
        "Dane wnioskodawcy",
        [
            _field("imie", "Imię"),
            _field("nazwisko", "Nazwisko"),
            _field("kod_pocztowy", "Kod pocztowy", FieldType.POSTAL_CODE),
            _field("miejscowosc", "Miejscowość"),
        ],
        tables=[TableData(headers=["Nazwa psa", "Rasa"], rows=[["Burek", "kundel"]], title="Psy")],
    )
    structured = _structured("Wniosek o dofinansowanie", [section])

    definition = DeterministicFormDefinitionMapper().build_definition(extracted, structured)
    payload = FormDefinitionDTO.model_validate(definition).model_dump(
        by_alias=True, exclude_none=True
    )

    assert payload["title"] == "Wniosek o dofinansowanie"
    assert [tab["type"] for tab in payload["tabs"]] == ["MAIN", "FINISH"]
    assert len(payload["flow"]["links"]) == 1
    assert payload["flow"]["links"][0]["source"] == payload["tabs"][0]["id"]
    assert payload["flow"]["links"][0]["target"] == payload["tabs"][1]["id"]

    section_field = payload["tabs"][0]["questions"][0]["field"]
    assert section_field["type"] == "SECTION"
    assert "repeatingSectionGrid" in section_field
    assert "repeating_section_grid" not in section_field
    child_questions = section_field["repeatingSectionGrid"]
    assert [(item["x"], item["y"], item["cols"]) for item in child_questions[:4]] == [
        (0, 0, 1),
        (1, 0, 1),
        (0, 1, 1),
        (1, 1, 1),
    ]
    assert child_questions[0]["field"]["techName"] == "imie"
    assert child_questions[0]["field"]["questionOrder"] == 0
    assert child_questions[0]["field"]["tooltipMessage"] == ""
    repeating = child_questions[-1]["field"]
    assert repeating["type"] == "REPEATING_SECTION"
    assert [column["field"]["title"] for column in repeating["repeatingSectionGrid"]] == [
        "Nazwa psa",
        "Rasa",
    ]

    finish = payload["tabs"][-1]
    finish_fields = [question["field"] for question in finish["questions"]]
    assert finish["title"] == "Strona końcowa"
    assert len(finish_fields) == 1
    assert finish_fields[0]["type"] == "TEXT_BLOCK"
    assert "Zanim wyślesz wniosek" in finish_fields[0]["description"]


def test_mapper_adds_validators_dictionaries_identity_defaults_and_consent() -> None:
    extracted = _extracted(
        "Formularz",
        paragraphs=["Wyrażam zgodę na przetwarzanie danych osobowych zgodnie z klauzulą informacyjną."],
    )
    section = _section(
        "dane_wnioskodawcy",
        "Dane wnioskodawcy",
        [
            _field("imie", "Imię"),
            _field("nazwisko", "Nazwisko"),
            _field("pesel", "Numer PESEL", FieldType.PESEL),
            _field("nip", "NIP", FieldType.NIP),
            _field("regon", "REGON", FieldType.REGON),
            _field("kod", "Kod pocztowy", FieldType.POSTAL_CODE),
            _field("email", "Adres e-mail", FieldType.EMAIL),
            _field("phone", "Telefon (opcjonalnie)", FieldType.PHONE),
            _field("kraj", "Kraj"),
            _field("wojewodztwo", "Województwo"),
            _field("powiat", "Powiat"),
            _field("gmina", "Gmina"),
            _field("miejscowosc", "Miejscowość"),
            _field("kierunkowy", "Numer kierunkowy"),
            _field("data", "Data wniosku", FieldType.DATE),
            _field("kwota", "Kwota zwrotu"),
            _field("uzasadnienie", "Uzasadnienie"),
            _field("pelnomocnictwo", "Pełnomocnictwo"),
        ],
    )
    definition = DeterministicFormDefinitionMapper().build_definition(
        extracted, _structured("Formularz", [section])
    )
    main = definition.tabs[0]
    children = main.questions[0].field.repeating_section_grid
    fields = {question.field.title: question.field for question in children}

    assert fields["Imię"].default_value == "PESEL.name"
    assert fields["Nazwisko"].default_value == "PESEL.surname"
    assert fields["Numer PESEL"].default_value == "PESEL.pesel"
    assert all(
        fields[label].default_value_type == "EXTERNAL_SYSTEM" and fields[label].read_only
        for label in ("Imię", "Nazwisko", "Numer PESEL")
    )
    assert fields["Numer PESEL"].validation == ["PESEL", "REQUIRED"]
    assert fields["NIP"].validation == ["NIP", "REQUIRED"]
    assert fields["REGON"].validation == ["REGON", "REQUIRED"]
    assert fields["Kod pocztowy"].validation == ["ZIP_CODE", "REQUIRED"]
    assert fields["Adres e-mail"].validation == ["EMAIL", "REQUIRED"]
    assert fields["Telefon (opcjonalnie)"].validation == []
    assert fields["Kraj"].type is ComponentType.SELECT
    assert fields["Kraj"].dictionary_name == "Kraje"
    assert fields["Kraj"].default_value == ["Polska"]
    assert fields["Województwo"].dictionary_name == "Województwo"
    assert fields["Powiat"].dictionary_name == "Powiat"
    assert fields["Gmina"].dictionary_name == "Gmina"
    assert fields["Miejscowość"].dictionary_name == "Miejscowość"
    assert fields["Numer kierunkowy"].dictionary_name == "Numery kierunkowe"
    assert fields["Data wniosku"].type is ComponentType.DATEPICKER
    assert fields["Kwota zwrotu"].type is ComponentType.NUMBER
    assert fields["Uzasadnienie"].type is ComponentType.TEXTAREA
    assert fields["Pełnomocnictwo"].type is ComponentType.FILE_UPLOADER

    consent_tab = next(tab for tab in definition.tabs if tab.title == "Kontakt i załączniki")
    consent = next(
        question.field
        for question in consent_tab.questions
        if question.field.type is ComponentType.CONSENT_SECTION
    )
    assert consent.consent_section_config is not None
    assert len(consent.consent_section_config.consents) == 1
    assert consent.consent_section_config.consents[0].required is True
    assert "przetwarzanie danych" in consent.consent_section_config.consents[0].description


def test_mapper_adds_multi_application_selector_and_jsonata_show_states() -> None:
    sections = [
        _section("application_i", "I. Wniosek o stypendium", [_field("imie", "Imię")]),
        _section("application_ii", "II. Wniosek o nagrodę", [_field("nazwisko", "Nazwisko")]),
        _section("application_iii", "III. Wniosek o wyróżnienie", [_field("cel", "Cel")]),
    ]
    definition = DeterministicFormDefinitionMapper().build_definition(
        _extracted("Połączenie wniosków"), _structured("Połączenie wniosków", sections)
    )

    selector = definition.tabs[0].questions[0].field
    assert selector.title == "Rodzaj wniosku"
    assert selector.type is ComponentType.RADIO
    assert [option.name for option in selector.options] == [
        "Wniosek o stypendium",
        "Wniosek o nagrodę",
        "Wniosek o wyróżnienie",
    ]
    assert [tab.title for tab in definition.tabs[:-1]] == [
        "Rodzaj wniosku",
        "Wniosek o stypendium",
        "Wniosek o nagrodę",
        "Wniosek o wyróżnienie",
    ]
    for tab, option in zip(definition.tabs[1:-1], selector.options, strict=True):
        state = tab.questions[0].field.states[0]
        assert state.type == "SHOW"
        assert f'"{option.name}" in tabs[\'Rodzaj wniosku\' in title]' in state.query
        assert "questions['rodzaj_wniosku' in field.techName].field.__userAnswer" in state.query


def test_mapper_adds_conditional_state_for_preceding_yes_radio() -> None:
    choice = ChoiceGroup(
        group_id="czy_wystapila_zmiana",
        label="Czy wystąpiła zmiana?",
        selection_type="single",
        options=[ChoiceOption(label="Tak", is_selected=False), ChoiceOption(label="Nie", is_selected=False)],
        needs_review=True,
    )
    sections = [
        _section("pytanie", "Pytanie", [], choice_groups=[choice]),
        _section("szczegoly", "Dodatkowe dane", [_field("opis", "Opis zmiany")]),
    ]
    extracted = _extracted(
        "Formularz", paragraphs=["W przypadku zaznaczenia TAK należy podać opis zmiany."]
    )
    definition = DeterministicFormDefinitionMapper().build_definition(
        extracted, _structured("Formularz", sections)
    )

    state = definition.tabs[0].questions[1].field.states[0]
    assert state.type == "SHOW"
    assert '"Tak" in tabs[\'Dane\' in title]' in state.query
    assert "czy_wystapila_zmiana" in state.query


def _field(
    field_id: str, label: str, field_type: FieldType = FieldType.TEXT, value: str = ""
) -> FormField:
    return FormField(
        field_id=field_id,
        label=label,
        field_type=field_type,
        value=value,
        is_valid=True,
        validation_error=None,
        confidence=1.0,
        needs_review=not value,
    )


def _section(
    section_id: str,
    title: str,
    fields: list[FormField],
    choice_groups: list[ChoiceGroup] | None = None,
    tables: list[TableData] | None = None,
) -> FormSection:
    return FormSection(
        section_id=section_id,
        title=title,
        order=1,
        fields=fields,
        choice_groups=choice_groups or [],
        tables=tables or [],
    )


def _structured(title: str, sections: list[FormSection]) -> StructuredForm:
    return StructuredForm(
        filename="form.pdf",
        format="pdf",
        form_title=title,
        sections=sections,
        total_fields=sum(len(section.fields) for section in sections),
        fields_needing_review=0,
        overall_confidence=1.0,
    )


def _extracted(title: str, paragraphs: list[str] | None = None) -> ExtractedDocument:
    page = ExtractedPage(page_number=1, headings=[title], paragraphs=paragraphs or [])
    return ExtractedDocument(filename="form.pdf", format="pdf", pages=[page])

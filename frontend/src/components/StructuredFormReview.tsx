import React from 'react';
import { updateStructuredChoice, updateStructuredField } from '../viewmodels/structuredFormViewModel';
import type { FormFieldDTO, FormSectionDTO, StructuredFormDTO } from '../types/digitize';

interface StructuredFormReviewProps {
  form: StructuredFormDTO;
  onUpdate: (form: StructuredFormDTO) => void;
}

export const StructuredFormReview: React.FC<StructuredFormReviewProps> = ({ form, onUpdate }) => {
  const updateField = (sectionId: string, fieldId: string, value: string) => {
    onUpdate(updateStructuredField(form, sectionId, fieldId, value));
  };

  const updateChoice = (
    sectionId: string,
    groupId: string,
    optionIndex: number,
    isSelected: boolean
  ) => {
    onUpdate(updateStructuredChoice(form, sectionId, groupId, optionIndex, isSelected));
  };

  const sections = [...form.sections].sort((first, second) => first.order - second.order);
  const confidence = Math.round(form.overall_confidence * 100);

  return (
    <div className="structured-review">
      <header className="structured-summary">
        <div>
          <span className="structured-eyebrow">Wynik cyfryzacji</span>
          <h2 className="structured-title">{form.form_title || 'Formularz strukturalny'}</h2>
        </div>
        <div className="structured-metrics" aria-label="Podsumowanie formularza">
          <span className="structured-metric">
            <strong>{form.total_fields}</strong> pól
          </span>
          <span
            className={`review-counter ${form.fields_needing_review > 0 ? 'review-counter-active' : ''}`}
            role="status"
          >
            Do weryfikacji: {form.fields_needing_review}
          </span>
          <span className="confidence-tag">Pewność {confidence}%</span>
        </div>
      </header>

      {sections.length === 0 ? (
        <div className="empty-state-notice">Nie wykryto sekcji formularza.</div>
      ) : (
        sections.map((section) => (
          <StructuredSection
            key={section.section_id}
            section={section}
            onFieldChange={updateField}
            onChoiceChange={updateChoice}
          />
        ))
      )}
    </div>
  );
};

interface StructuredSectionProps {
  section: FormSectionDTO;
  onFieldChange: (sectionId: string, fieldId: string, value: string) => void;
  onChoiceChange: (
    sectionId: string,
    groupId: string,
    optionIndex: number,
    isSelected: boolean
  ) => void;
}

const StructuredSection: React.FC<StructuredSectionProps> = ({
  section,
  onFieldChange,
  onChoiceChange,
}) => (
  <section className="structured-section" aria-labelledby={`section-${section.section_id}`}>
    <h3 id={`section-${section.section_id}`} className="structured-section-title">
      <span className="structured-section-order">{section.order}</span>
      {section.title}
    </h3>

    {section.fields.length > 0 && (
      <div className="structured-field-list">
        {section.fields.map((field) => (
          <StructuredField
            key={field.field_id}
            field={field}
            onChange={(value) => onFieldChange(section.section_id, field.field_id, value)}
          />
        ))}
      </div>
    )}

    {section.choice_groups.map((group) => (
      <fieldset
        key={group.group_id}
        className={`structured-choice-group ${group.needs_review ? 'needs-review' : ''}`}
      >
        <legend>{group.label || 'Wybierz odpowiedź'}</legend>
        <div className="structured-choice-options">
          {group.options.map((option, index) => (
            <label key={`${group.group_id}-${index}`} className="structured-choice-option">
              <input
                type={group.selection_type === 'single' ? 'radio' : 'checkbox'}
                name={`${section.section_id}-${group.group_id}`}
                checked={option.is_selected}
                onChange={(event) =>
                  onChoiceChange(
                    section.section_id,
                    group.group_id,
                    index,
                    event.currentTarget.checked
                  )
                }
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
        {group.needs_review && <span className="review-message">Sprawdź zaznaczenie.</span>}
      </fieldset>
    ))}

    {section.tables.map((table, tableIndex) => (
      <div className="table-card" key={`${section.section_id}-table-${tableIndex}`}>
        {table.title && <div className="table-title">{table.title}</div>}
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                {table.headers.map((header, index) => (
                  <th key={index}>{header || `Kolumna ${index + 1}`}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    ))}
  </section>
);

interface StructuredFieldProps {
  field: FormFieldDTO;
  onChange: (value: string) => void;
}

const StructuredField: React.FC<StructuredFieldProps> = ({ field, onChange }) => (
  <div className={`structured-field-card ${field.needs_review ? 'needs-review' : ''}`}>
    <div className="structured-field-heading">
      <label htmlFor={`structured-${field.field_id}`} className="structured-field-label">
        {field.label}
      </label>
      <div className="structured-field-badges">
        <span className="field-type-badge">{field.field_type}</span>
        <span className="confidence-tag">{Math.round(field.confidence * 100)}%</span>
      </div>
    </div>
    <input
      id={`structured-${field.field_id}`}
      className="kv-input"
      type="text"
      value={field.value}
      aria-invalid={!field.is_valid}
      onChange={(event) => onChange(event.currentTarget.value)}
    />
    {!field.is_valid && field.validation_error && (
      <p className="review-message" role="alert">
        {field.validation_error}
      </p>
    )}
  </div>
);

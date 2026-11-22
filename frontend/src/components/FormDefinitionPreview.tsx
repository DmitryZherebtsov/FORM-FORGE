import React, { useEffect, useMemo, useState } from 'react';
import type {
  FormDefinitionDTO,
  FormQuestionDTO,
  FormQuestionFieldDTO,
  FormTabDTO,
} from '../types/digitize';
import {
  areCoiStatesVisible,
  downloadCoiFormDefinition,
  type CoiUserAnswer,
  type CoiUserAnswers,
} from '../utils/coiFormPreview';

interface FormDefinitionPreviewProps {
  formDefinition: FormDefinitionDTO;
}

interface SummaryRow {
  key: string;
  label: string;
  value: string;
}

export const FormDefinitionPreview: React.FC<FormDefinitionPreviewProps> = ({
  formDefinition,
}) => {
  const [answers, setAnswers] = useState<CoiUserAnswers>({});
  const defaultAnswers = useMemo(
    () => getDefaultAnswers(formDefinition.tabs),
    [formDefinition],
  );
  const currentAnswers = useMemo(
    () => ({ ...defaultAnswers, ...answers }),
    [answers, defaultAnswers],
  );
  const visibleTabs = useMemo(
    () => {
      const mainTabs = formDefinition.tabs.filter((tab) =>
        tab.type === 'MAIN' && tab.questions.some((question) => isQuestionVisible(question, currentAnswers)),
      );
      const finishTab = [...formDefinition.tabs].reverse().find((tab) => tab.type === 'FINISH');
      const orderedTabs = orderTabsByFlow(mainTabs, formDefinition.flow.links);
      return finishTab ? [...orderedTabs, finishTab] : orderedTabs;
    },
    [currentAnswers, formDefinition.flow.links, formDefinition.tabs],
  );
  const firstTabId = visibleTabs[0]?.id ?? formDefinition.tabs[0]?.id ?? '';
  const [activeTabId, setActiveTabId] = useState(firstTabId);
  const activeTab = visibleTabs.find((tab) => tab.id === activeTabId) ?? visibleTabs[0];
  const activeIndex = activeTab ? visibleTabs.findIndex((tab) => tab.id === activeTab.id) : -1;
  const summaryRows = useMemo(
    () => getSummaryRows(formDefinition.tabs, currentAnswers),
    [currentAnswers, formDefinition.tabs],
  );

  useEffect(() => {
    if (!visibleTabs.some((tab) => tab.id === activeTabId)) {
      setActiveTabId(visibleTabs[0]?.id ?? '');
    }
  }, [activeTabId, visibleTabs]);

  useEffect(() => {
    setAnswers({});
    setActiveTabId(firstTabId);
  }, [formDefinition]);

  const updateAnswer = (techName: string, value: CoiUserAnswer) => {
    setAnswers((current) => ({ ...current, [techName]: value }));
  };

  return (
    <section className="coi-preview" aria-label={`Podgląd formularza ${formDefinition.title}`}>
      <header className="coi-preview-header">
        <div>
          <span className="coi-preview-eyebrow">Interaktywny podgląd</span>
          <h2>{formDefinition.title}</h2>
        </div>
        <button
          type="button"
          className="btn btn-primary coi-download-button"
          onClick={() => downloadCoiFormDefinition(formDefinition)}
        >
          Pobierz konfigurację COI (.json)
        </button>
      </header>

      <nav className="coi-tab-navigation" aria-label="Etapy formularza" role="tablist">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            id={`coi-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={tab.id === activeTab?.id}
            aria-controls={`coi-panel-${tab.id}`}
            className={`coi-step-tab ${tab.id === activeTab?.id ? 'coi-step-tab-active' : ''}`}
            onClick={() => setActiveTabId(tab.id)}
          >
            {tab.title}
          </button>
        ))}
      </nav>

      {activeTab && (
        <div
          id={`coi-panel-${activeTab.id}`}
          role="tabpanel"
          aria-labelledby={`coi-tab-${activeTab.id}`}
          className="coi-tab-panel"
        >
          {activeTab.type === 'FINISH' ? (
            <SummaryTable rows={summaryRows} />
          ) : (
            <div className="coi-question-grid">
              {activeTab.questions.map((question) => renderQuestion(
                question,
                currentAnswers,
                updateAnswer,
                `question-${activeTab.id}-${question.field.id}`,
              ))}
            </div>
          )}
        </div>
      )}

      <footer className="coi-flow-controls">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setActiveTabId(visibleTabs[activeIndex - 1]?.id ?? activeTabId)}
          disabled={activeIndex <= 0}
        >
          Wstecz
        </button>
        <span className="coi-step-count" aria-live="polite">
          {activeIndex >= 0 ? `Krok ${activeIndex + 1} z ${visibleTabs.length}` : ''}
        </span>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setActiveTabId(visibleTabs[activeIndex + 1]?.id ?? activeTabId)}
          disabled={activeIndex < 0 || activeIndex >= visibleTabs.length - 1}
        >
          Dalej
        </button>
      </footer>
    </section>
  );
};

function isQuestionVisible(question: FormQuestionDTO, answers: CoiUserAnswers): boolean {
  const { field } = question;
  return areCoiStatesVisible(field.states, answers);
}

function orderTabsByFlow(
  tabs: FormTabDTO[],
  links: FormDefinitionDTO['flow']['links'],
): FormTabDTO[] {
  const ordered: FormTabDTO[] = [];
  const included = new Set<string>();
  let current: FormTabDTO | undefined = tabs[0];

  while (current) {
    ordered.push(current);
    included.add(current.id);
    current = links
      .filter((link) => link.source === current?.id)
      .map((link) => tabs.find((tab) => tab.id === link.target))
      .find((tab): tab is FormTabDTO => Boolean(tab && !included.has(tab.id)))
      ?? tabs.find((tab) => !included.has(tab.id));
  }

  return ordered;
}

function getDefaultAnswers(tabs: FormTabDTO[]): CoiUserAnswers {
  const defaults: CoiUserAnswers = {};
  for (const tab of tabs) {
    for (const question of tab.questions) {
      collectDefaultAnswers(question, defaults);
    }
  }
  return defaults;
}

function collectDefaultAnswers(question: FormQuestionDTO, defaults: CoiUserAnswers): void {
  const { field } = question;
  if (field.defaultValue !== null && field.defaultValue !== undefined) {
    defaults[field.techName] = field.defaultValue;
  }
  for (const nested of field.repeatingSectionGrid) collectDefaultAnswers(nested, defaults);
}

function renderQuestion(
  question: FormQuestionDTO,
  answers: CoiUserAnswers,
  updateAnswer: (techName: string, value: CoiUserAnswer) => void,
  key: string,
): React.ReactNode {
  const { field } = question;
  if (!isQuestionVisible(question, answers)) return null;

  const placement: React.CSSProperties = {
    gridColumn: `${question.x + 1} / span ${Math.max(1, question.cols)}`,
    gridRow: `${question.y + 1} / span ${Math.max(1, question.rows)}`,
  };
  const value = answers[field.techName] ?? field.defaultValue ?? '';
  const locked = field.readOnly || field.defaultValueType === 'EXTERNAL_SYSTEM';
  const description = toSafeText(field.description);

  if (field.type === 'SECTION' || field.type === 'REPEATING_SECTION') {
    return (
      <section key={key} className="coi-section-card" style={placement}>
        <header className="coi-section-heading">
          <h3>{toSafeText(field.title)}</h3>
          {field.type === 'REPEATING_SECTION' && (
            <span className="coi-component-badge">Sekcja powtarzalna</span>
          )}
        </header>
        {description && <p className="coi-field-description">{description}</p>}
        <div className="coi-question-grid coi-nested-grid">
          {field.repeatingSectionGrid.map((nested) => renderQuestion(
            nested,
            answers,
            updateAnswer,
            `${key}-${nested.field.id}`,
          ))}
        </div>
      </section>
    );
  }

  if (field.type === 'TEXT_BLOCK' || field.type === 'INFO_SECTION') {
    return (
      <aside key={key} className={`coi-info-card ${field.type === 'INFO_SECTION' ? 'coi-info-card-highlight' : ''}`} style={placement}>
        {field.title && <h3>{toSafeText(field.title)}</h3>}
        {description && <p>{description}</p>}
      </aside>
    );
  }

  if (field.type === 'CONSENT_SECTION') {
    return (
      <fieldset key={key} className="coi-field-card coi-consent-card" style={placement}>
        <legend>{toSafeText(field.title || 'Zgody')}</legend>
        {description && <p className="coi-field-description">{description}</p>}
        {(field.consentSectionConfig?.consents ?? []).map((consent, index) => {
          const consentKey = `${field.techName}__consent_${index}`;
          const checked = answers[consentKey] === 'true';
          return (
            <label className="coi-option-row" key={consentKey}>
              <input
                type="checkbox"
                checked={checked}
                required={consent.required}
                onChange={(event) => updateAnswer(consentKey, String(event.currentTarget.checked))}
              />
              <span>{toSafeText(consent.description)}</span>
              {consent.required && <span className="coi-required-label">Wymagane</span>}
            </label>
          );
        })}
        {(field.consentSectionConfig?.files ?? []).map((file) => (
          <span className="coi-consent-file" key={file}>{toSafeText(file)}</span>
        ))}
      </fieldset>
    );
  }

  return (
    <div key={key} className="coi-field-card" style={placement}>
      <div className="coi-field-title-row">
        <label className="coi-field-label" htmlFor={`coi-input-${field.id}`}>
          {toSafeText(field.title || field.techName)}
        </label>
        {locked && <span className="coi-lock-badge" aria-label="Pole tylko do odczytu">🔒 Tylko do odczytu</span>}
      </div>
      {description && <p className="coi-field-description">{description}</p>}
      {field.tooltipMessage && <p className="coi-tooltip-text">{toSafeText(field.tooltipMessage)}</p>}
      <div className="coi-field-badges">
        {field.validation.map((validation) => (
          <span className="coi-validator-pill" key={validation}>{validation}</span>
        ))}
        {field.dictionaryName && <span className="coi-dictionary-pill">{field.dictionaryName}</span>}
      </div>
      {renderControl(field, value, locked, updateAnswer)}
    </div>
  );
}

function renderControl(
  field: FormQuestionFieldDTO,
  value: CoiUserAnswer,
  locked: boolean,
  updateAnswer: (techName: string, value: CoiUserAnswer) => void,
): React.ReactNode {
  const inputId = `coi-input-${field.id}`;
  const stringValue = Array.isArray(value) ? value.join(', ') : value;

  switch (field.type) {
    case 'TEXT_FIELD':
    case 'NUMBER':
    case 'DATEPICKER':
      return (
        <input
          id={inputId}
          className="coi-input"
          type={field.type === 'NUMBER' ? 'number' : field.type === 'DATEPICKER' ? 'date' : 'text'}
          value={stringValue}
          readOnly={locked}
          onChange={(event) => updateAnswer(field.techName, event.currentTarget.value)}
        />
      );
    case 'TEXTAREA':
      return (
        <textarea
          id={inputId}
          className="coi-input coi-textarea"
          value={stringValue}
          readOnly={locked}
          onChange={(event) => updateAnswer(field.techName, event.currentTarget.value)}
        />
      );
    case 'RADIO':
      return (
        <fieldset className="coi-choice-list">
          <legend className="coi-visually-hidden">{toSafeText(field.title)}</legend>
          {field.options.map((option, index) => (
            <label className="coi-option-row" key={option.id}>
              <input
                id={index === 0 ? inputId : `${inputId}-${option.id}`}
                type="radio"
                name={`coi-radio-${field.id}`}
                value={option.name}
                checked={stringValue === option.name}
                disabled={locked}
                onChange={() => updateAnswer(field.techName, option.name)}
              />
              <span>{toSafeText(option.name)}</span>
            </label>
          ))}
        </fieldset>
      );
    case 'CHECKBOX': {
      const selected = Array.isArray(value) ? value : value ? [value] : [];
      return (
        <fieldset className="coi-choice-list">
          <legend className="coi-visually-hidden">{toSafeText(field.title)}</legend>
          {field.options.map((option, index) => (
            <label className="coi-option-row" key={option.id}>
              <input
                id={index === 0 ? inputId : `${inputId}-${option.id}`}
                type="checkbox"
                checked={selected.includes(option.name)}
                disabled={locked}
                onChange={(event) => {
                  const next = event.currentTarget.checked
                    ? [...selected, option.name]
                    : selected.filter((item) => item !== option.name);
                  updateAnswer(field.techName, next);
                }}
              />
              <span>{toSafeText(option.name)}</span>
            </label>
          ))}
        </fieldset>
      );
    }
    case 'SELECT': {
      const options = [...field.options];
      if (stringValue && !options.some((option) => option.name === stringValue)) {
        options.unshift({ id: `default-${field.id}`, name: stringValue, techName: field.techName });
      }
      return (
        <select
          id={inputId}
          className="coi-input coi-select"
          value={stringValue}
          disabled={locked}
          onChange={(event) => updateAnswer(field.techName, event.currentTarget.value)}
        >
          <option value="">Wybierz wartość</option>
          {options.map((option) => <option key={option.id} value={option.name}>{option.name}</option>)}
        </select>
      );
    }
    case 'FILE_UPLOADER':
      return (
        <div className="coi-file-picker">
          <input
            id={inputId}
            type="file"
            disabled={locked}
            onChange={(event) => updateAnswer(field.techName, event.currentTarget.files?.[0]?.name ?? '')}
          />
          {stringValue && <span className="coi-file-name">Załącznik: {stringValue}</span>}
          <span className="coi-file-note">Podgląd symulowany — plik nie jest wysyłany.</span>
        </div>
      );
    default:
      return <p className="coi-unsupported-component">Podgląd komponentu {field.type}.</p>;
  }
}

function getSummaryRows(tabs: FormTabDTO[], answers: CoiUserAnswers): SummaryRow[] {
  const rows: SummaryRow[] = [];
  for (const tab of tabs) {
    if (tab.type === 'FINISH') continue;
    for (const question of tab.questions) collectSummaryRows(question, answers, rows);
  }
  return rows;
}

function collectSummaryRows(
  question: FormQuestionDTO,
  answers: CoiUserAnswers,
  rows: SummaryRow[],
): void {
  const { field } = question;
  if (!isQuestionVisible(question, answers)) return;
  if (field.type === 'SECTION' || field.type === 'REPEATING_SECTION') {
    for (const nested of field.repeatingSectionGrid) collectSummaryRows(nested, answers, rows);
    return;
  }
  if (field.type === 'CONSENT_SECTION') {
    (field.consentSectionConfig?.consents ?? []).forEach((consent, index) => {
      const answer = answers[`${field.techName}__consent_${index}`];
      if (answer !== undefined) {
        rows.push({
          key: `${field.techName}-${index}`,
          label: toSafeText(consent.description),
          value: answer === 'true' ? 'Tak' : 'Nie',
        });
      }
    });
    return;
  }
  const answer = answers[field.techName];
  if (answer === undefined || answer === '') return;
  const value = Array.isArray(answer) ? answer.join(', ') : answer;
  rows.push({ key: field.techName, label: toSafeText(field.title || field.techName), value });
}

const SummaryTable: React.FC<{ rows: SummaryRow[] }> = ({ rows }) => (
  <div className="coi-summary-card">
    <h3>Podsumowanie odpowiedzi</h3>
    {rows.length === 0 ? (
      <p className="coi-empty-summary">Nie wprowadzono jeszcze odpowiedzi.</p>
    ) : (
      <div className="coi-summary-table-wrap">
        <table className="coi-summary-table">
          <thead><tr><th scope="col">Pole</th><th scope="col">Odpowiedź</th></tr></thead>
          <tbody>
            {rows.map((row) => <tr key={row.key}><th scope="row">{row.label}</th><td>{row.value}</td></tr>)}
          </tbody>
        </table>
      </div>
    )}
  </div>
);

function toSafeText(value: string): string {
  return value
    .replace(/<\s*br\s*\/?>/gi, '\n')
    .replace(/<\s*\/\s*(p|div|li|h[1-6])\s*>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .trim();
}

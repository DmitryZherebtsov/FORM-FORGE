import React, { useEffect, useState } from 'react';
import { FormDefinitionPreview } from './FormDefinitionPreview';
import { StructuredFormReview } from './StructuredFormReview';
import { downloadCoiFormDefinition } from '../utils/coiFormPreview';
import type {
  DigitizeResponseDTO,
  ExtractedDocument,
  KeyValuePair,
  CheckboxItem,
  StructuredFormDTO,
  TableData,
} from '../types/digitize';

interface ExtractedDataWorkspaceProps {
  extracted: ExtractedDocument;
  onUpdateExtracted: (updated: ExtractedDocument) => void;
  structuredForm?: StructuredFormDTO | null;
  onUpdateStructuredForm: (updated: StructuredFormDTO) => void;
  rawResponseJson: DigitizeResponseDTO;
}

type TabType = 'coi_preview' | 'structured' | 'fields' | 'tables' | 'raw_text' | 'json';

export const ExtractedDataWorkspace: React.FC<ExtractedDataWorkspaceProps> = ({
  extracted,
  onUpdateExtracted,
  structuredForm,
  onUpdateStructuredForm,
  rawResponseJson,
}) => {
  const [selectedPageIndex, setSelectedPageIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<TabType>(() =>
    rawResponseJson.form_definition ? 'coi_preview' : structuredForm ? 'structured' : 'fields'
  );
  const [copyFeedback, setCopyFeedback] = useState(false);

  useEffect(() => {
    if (rawResponseJson.form_definition) setActiveTab('coi_preview');
    else if (structuredForm) setActiveTab('structured');
  }, [rawResponseJson.form_definition, structuredForm?.filename]);

  const totalPages = extracted.pages.length || 1;
  const currentPage = extracted.pages[selectedPageIndex] || {
    page_number: 1,
    headings: [],
    paragraphs: [],
    key_values: [],
    tables: [],
    checkboxes: [],
    raw_text: '',
  };

  const handleUpdateKeyValue = (index: number, updatedKv: KeyValuePair) => {
    const updatedPages = [...extracted.pages];
    const pageToUpdate = { ...updatedPages[selectedPageIndex] };
    const newKvs = [...pageToUpdate.key_values];
    newKvs[index] = updatedKv;
    pageToUpdate.key_values = newKvs;
    updatedPages[selectedPageIndex] = pageToUpdate;

    onUpdateExtracted({
      ...extracted,
      pages: updatedPages,
    });
  };

  const handleToggleCheckbox = (index: number) => {
    const updatedPages = [...extracted.pages];
    const pageToUpdate = { ...updatedPages[selectedPageIndex] };
    const newCbs = [...pageToUpdate.checkboxes];
    newCbs[index] = {
      ...newCbs[index],
      is_checked: !newCbs[index].is_checked,
    };
    pageToUpdate.checkboxes = newCbs;
    updatedPages[selectedPageIndex] = pageToUpdate;

    onUpdateExtracted({
      ...extracted,
      pages: updatedPages,
    });
  };

  const handleCopyJson = () => {
    const dataStr = JSON.stringify(rawResponseJson, null, 2);
    navigator.clipboard.writeText(dataStr);
    setCopyFeedback(true);
    setTimeout(() => setCopyFeedback(false), 2000);
  };

  const handleDownloadJson = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(JSON.stringify(rawResponseJson, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute(
      'download',
      `${extracted.filename.replace(/\.[^/.]+$/, '')}_digitized.json`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="workspace-container">
      {/* Workspace Header */}
      <div className="pane-header workspace-header">
        <div className="workspace-tabs" role="tablist" aria-label="Widoki wyniku cyfryzacji">
          {rawResponseJson.form_definition && (
            <button
              type="button"
              id="workspace-tab-coi_preview"
              role="tab"
              aria-selected={activeTab === 'coi_preview'}
              aria-controls="workspace-tab-content"
              className={`tab-btn ${activeTab === 'coi_preview' ? 'tab-btn-active' : ''}`}
              onClick={() => setActiveTab('coi_preview')}
            >
              Podgląd e-Formularza (COI)
            </button>
          )}
          {structuredForm && (
            <button
              type="button"
              id="workspace-tab-structured"
              role="tab"
              aria-selected={activeTab === 'structured'}
              aria-controls="workspace-tab-content"
              className={`tab-btn ${activeTab === 'structured' ? 'tab-btn-active' : ''}`}
              onClick={() => setActiveTab('structured')}
            >
              Formularz strukturalny
            </button>
          )}
          <button
            type="button"
            id="workspace-tab-fields"
            role="tab"
            aria-selected={activeTab === 'fields'}
            aria-controls="workspace-tab-content"
            className={`tab-btn ${activeTab === 'fields' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('fields')}
          >
            Pola formularza ({currentPage.key_values.length + currentPage.checkboxes.length})
          </button>
          <button
            type="button"
            id="workspace-tab-tables"
            role="tab"
            aria-selected={activeTab === 'tables'}
            aria-controls="workspace-tab-content"
            className={`tab-btn ${activeTab === 'tables' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('tables')}
          >
            Tabele ({currentPage.tables.length})
          </button>
          <button
            type="button"
            id="workspace-tab-raw_text"
            role="tab"
            aria-selected={activeTab === 'raw_text'}
            aria-controls="workspace-tab-content"
            className={`tab-btn ${activeTab === 'raw_text' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('raw_text')}
          >
            Tekst źródłowy
          </button>
          <button
            type="button"
            id="workspace-tab-json"
            role="tab"
            aria-selected={activeTab === 'json'}
            aria-controls="workspace-tab-content"
            className={`tab-btn ${activeTab === 'json' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('json')}
          >
            Surowy JSON
          </button>
        </div>

        <div className="workspace-toolbar">
          <span
            className={`structuring-mode-badge ${rawResponseJson.structuring_mode === 'llm' ? 'structuring-mode-llm' : ''}`}
            title={rawResponseJson.structuring_mode === 'heuristic_fallback' ? 'LLM był niedostępny; użyto bezpiecznego fallbacku.' : undefined}
          >
            {rawResponseJson.structuring_mode === 'llm'
              ? 'Silnik: AI Powered'
              : 'Silnik: Deterministyczny'}
          </span>
          <div className="workspace-export-actions">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleCopyJson}
              title="Kopiuj JSON do schowka"
            >
              {copyFeedback ? '✓ Skopiowano' : 'Kopiuj JSON'}
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleDownloadJson}
              title="Pobierz plik wynikowy JSON"
            >
              Pobierz JSON
            </button>
            {rawResponseJson.form_definition && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => downloadCoiFormDefinition(rawResponseJson.form_definition!)}
                title="Pobierz samą konfigurację COI"
              >
                Pobierz COI JSON
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Page Selector (if multiple pages exist) */}
      {totalPages > 1 && (
        <div className="page-pagination">
          <span className="pagination-label">Strona / Arkusz:</span>
          <div className="pagination-buttons">
            {extracted.pages.map((p, idx) => (
              <button
                key={p.page_number}
                type="button"
                className={`page-pill-btn ${selectedPageIndex === idx ? 'page-pill-active' : ''}`}
                onClick={() => setSelectedPageIndex(idx)}
              >
                {p.page_number}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Tab Contents */}
      <div
        id="workspace-tab-content"
        className="workspace-content"
        role="tabpanel"
        aria-labelledby={`workspace-tab-${activeTab}`}
      >
        {activeTab === 'coi_preview' && rawResponseJson.form_definition && (
          <FormDefinitionPreview formDefinition={rawResponseJson.form_definition} />
        )}

        {activeTab === 'structured' && structuredForm && (
          <StructuredFormReview
            form={structuredForm}
            onUpdate={onUpdateStructuredForm}
          />
        )}

        {activeTab === 'fields' && (
          <div className="fields-panel">
            {/* Headings */}
            {currentPage.headings.length > 0 && (
              <div className="headings-section">
                <div className="section-subtitle">Wykryte nagłówki sekcji</div>
                <div className="headings-list">
                  {currentPage.headings.map((h, i) => (
                    <div key={i} className="heading-badge">
                      {h}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Key-Value Inputs */}
            <div className="section-subtitle">
              Pola klucz-wartość ({currentPage.key_values.length})
            </div>
            {currentPage.key_values.length === 0 ? (
              <div className="empty-state-notice">Brak wykrytych par klucz-wartość na tej stronie.</div>
            ) : (
              <div className="kv-grid">
                {currentPage.key_values.map((kv, i) => (
                  <div key={i} className="kv-field-card">
                    <div className="kv-label-row">
                      <label className="kv-key-label">{kv.key}</label>
                      {kv.confidence !== undefined && (
                        <span className="confidence-tag">
                          {Math.round(kv.confidence * 100)}%
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      className="kv-input"
                      value={kv.value}
                      onChange={(e) =>
                        handleUpdateKeyValue(i, { ...kv, value: e.target.value })
                      }
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Checkboxes */}
            <div className="section-subtitle" style={{ marginTop: '24px' }}>
              Pola wyboru (Checkbox / Radio) ({currentPage.checkboxes.length})
            </div>
            {currentPage.checkboxes.length === 0 ? (
              <div className="empty-state-notice">Brak pól wyboru na tej stronie.</div>
            ) : (
              <div className="checkboxes-list">
                {currentPage.checkboxes.map((cb: CheckboxItem, i: number) => (
                  <label key={i} className="checkbox-item-row">
                    <input
                      type="checkbox"
                      checked={cb.is_checked}
                      onChange={() => handleToggleCheckbox(i)}
                      className="checkbox-input"
                    />
                    <span className="checkbox-label">{cb.label}</span>
                    <span
                      className={`checkbox-status-pill ${
                        cb.is_checked ? 'status-checked' : 'status-unchecked'
                      }`}
                    >
                      {cb.is_checked ? 'Zaznaczone' : 'Niezaznaczone'}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'tables' && (
          <div className="tables-panel">
            {currentPage.tables.length === 0 ? (
              <div className="empty-state-notice">Brak tabel wykrytych na tej stronie.</div>
            ) : (
              currentPage.tables.map((table: TableData, tIdx: number) => (
                <div key={tIdx} className="table-card">
                  {table.title && <div className="table-title">{table.title}</div>}
                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          {table.headers.map((h: string, hIdx: number) => (
                            <th key={hIdx} className={getTableColumnClass(h)}>
                              {h || `Kolumna ${hIdx + 1}`}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {table.rows.map((row: string[], rIdx: number) => (
                          <tr key={rIdx}>
                            {row.map((cell: string, cIdx: number) => (
                              <td key={cIdx} className={getTableColumnClass(table.headers[cIdx] ?? '')}>
                                {cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'raw_text' && (
          <div className="raw-text-panel">
            <textarea
              readOnly
              className="raw-text-area"
              wrap="soft"
              value={currentPage.raw_text || 'Brak tekstu źródłowego.'}
            />
          </div>
        )}

        {activeTab === 'json' && (
          <div className="json-panel">
            <pre className="json-code-block">
              {JSON.stringify(rawResponseJson, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

function getTableColumnClass(header: string): string | undefined {
  const normalizedHeader = header.trim().toLocaleLowerCase('pl-PL');
  if (normalizedHeader === 'lp.' || normalizedHeader === 'lp') return 'data-table-serial-column';
  if (normalizedHeader === 'strona') return 'data-table-page-column';
  return undefined;
}

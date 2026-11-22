import React, { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { getHealth, digitizeForm, ApiError } from './api/formsApi';
import { DocumentPreview } from './components/DocumentPreview';
import { ExtractedDataWorkspace } from './components/ExtractedDataWorkspace';
import { FileUploadZone } from './components/FileUploadZone';
import { TopBar } from './components/TopBar';
import type {
  DigitizeResponseDTO,
  ExtractedDocument,
  HealthResponseDTO,
  StructuredFormDTO,
} from './types/digitize';

const readInitialToken = (): string => {
  const configuredToken = import.meta.env.VITE_DEV_TOKEN;
  const tokenPrefix = '#token=';
  const fragment = window.location.hash;
  if (!fragment.startsWith(tokenPrefix)) {
    return configuredToken || '';
  }

  let fragmentToken = fragment.slice(tokenPrefix.length);
  try {
    fragmentToken = decodeURIComponent(fragmentToken);
  } catch {
    // Preserve the raw token if the fragment contains malformed percent escapes.
  }
  return configuredToken || fragmentToken;
};

export const App: React.FC = () => {
  // Authentication & Health state (RAM only)
  const [token, setToken] = useState<string>(readInitialToken);
  const [health, setHealth] = useState<HealthResponseDTO | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  // Upload & Extraction state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [digitizeResponse, setDigitizeResponse] = useState<DigitizeResponseDTO | null>(null);

  // Poll/fetch health status
  const fetchHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const res = await getHealth();
      setHealth(
        res.llm_enabled && res.llm_status === 'configured'
          ? { ...res, llm_status: 'ready' }
          : res,
      );
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  useLayoutEffect(() => {
    if (window.location.hash.startsWith('#token=')) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  }, []);

  // Handle document submission
  const handleFileSelect = async (file: File) => {
    setSelectedFile(file);
    setDigitizeResponse(null);
    setApiError(null);
    setIsLoading(true);

    try {
      const res = await digitizeForm(file, token);
      setDigitizeResponse(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(`[Błąd ${err.status}] ${err.detail}`);
      } else {
        setApiError('Nieoczekiwany błąd podczas cyfryzacji dokumentu.');
      }
      setDigitizeResponse(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setSelectedFile(null);
    setDigitizeResponse(null);
    setApiError(null);
  };

  const handleUpdateExtracted = (updatedExtracted: ExtractedDocument) => {
    if (digitizeResponse) {
      setDigitizeResponse({
        ...digitizeResponse,
        extracted: updatedExtracted,
      });
    }
  };

  const handleUpdateStructuredForm = (updatedForm: StructuredFormDTO) => {
    if (digitizeResponse) {
      setDigitizeResponse({
        ...digitizeResponse,
        structured_form: updatedForm,
      });
    }
  };

  return (
    <div className="app-layout">
      <TopBar
        health={health}
        healthLoading={healthLoading}
        onRefreshHealth={fetchHealth}
        token={token}
        onTokenChange={setToken}
      />

      <main className="app-main">
        {/* Error Alert Banner */}
        {apiError && (
          <div className="error-banner">
            <div className="error-banner-content">
              <span className="error-banner-icon">⛔</span>
              <div className="error-banner-text">
                <strong>Błąd przetwarzania:</strong> {apiError}
              </div>
            </div>
            <button
              type="button"
              className="error-banner-close"
              onClick={() => setApiError(null)}
            >
              ✕
            </button>
          </div>
        )}

        {/* Upload Zone */}
        <FileUploadZone
          onFileSelect={handleFileSelect}
          isLoading={isLoading}
          selectedFile={selectedFile}
          onClear={handleClear}
        />

        {/* Vertically stacked document workspace */}
        {selectedFile && digitizeResponse && digitizeResponse.extracted && (
          <div className="split-workspace">
            <div className="split-pane split-pane-left">
              <DocumentPreview file={selectedFile} />
            </div>
            <div className="split-pane split-pane-right">
              <ExtractedDataWorkspace
                extracted={digitizeResponse.extracted}
                onUpdateExtracted={handleUpdateExtracted}
                structuredForm={digitizeResponse.structured_form}
                onUpdateStructuredForm={handleUpdateStructuredForm}
                rawResponseJson={digitizeResponse}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
export default App;

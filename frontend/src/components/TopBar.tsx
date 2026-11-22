import React, { useEffect, useRef, useState } from 'react';
import type { HealthResponseDTO } from '../types/digitize';

interface TopBarProps {
  health: HealthResponseDTO | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
  token: string;
  onTokenChange: (token: string) => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  health,
  healthLoading,
  onRefreshHealth,
  token,
  onTokenChange,
}) => {
  const isOnline = health !== null && health.status === 'ok';
  const [tokenCopied, setTokenCopied] = useState(false);
  const copyFeedbackTimer = useRef<number | undefined>(undefined);

  useEffect(
    () => () => {
      if (copyFeedbackTimer.current !== undefined) {
        window.clearTimeout(copyFeedbackTimer.current);
      }
    },
    [],
  );

  const copyToken = async () => {
    try {
      await navigator.clipboard.writeText(token);
      setTokenCopied(true);
      if (copyFeedbackTimer.current !== undefined) {
        window.clearTimeout(copyFeedbackTimer.current);
      }
      copyFeedbackTimer.current = window.setTimeout(() => setTokenCopied(false), 1400);
    } catch {
      setTokenCopied(false);
    }
  };

  return (
    <header className="top-bar">
      <div className="top-bar-inner">
        <div className="top-bar-brand">
          <div className="top-bar-logo">COI</div>
          <div className="top-bar-titles">
            <span className="top-bar-title">Cyfryzacja Formularzy</span>
            <span className="top-bar-subtitle">HackNation 2026 • Workbench</span>
          </div>
        </div>

        <div className="top-bar-controls">
          <div className="status-badge-container" role="group" aria-label="Stan usługi i tryb pracy">
            <button
              type="button"
              className="status-refresh-btn"
              onClick={onRefreshHealth}
              title="Sprawdź stan usługi"
              disabled={healthLoading}
            >
              <span
                className={`status-indicator ${
                  healthLoading ? 'status-checking' : isOnline ? 'status-online' : 'status-offline'
                }`}
                aria-hidden="true"
              />
              <span className="status-label">{isOnline ? 'Usługa aktywna' : 'Usługa niedostępna'}</span>
            </button>
            {health?.llm_enabled && health.llm_status === 'ready' ? (
              <span
                className="llm-status-pill llm-status-ready"
                role="status"
                title={`Model: ${health.ai_model}`}
              >
                <span className="status-indicator status-online" aria-hidden="true" />
                AI Powered
              </span>
            ) : (
              <span className="llm-status-pill llm-status-autonomous" role="status">
                <span className="status-indicator status-autonomous" aria-hidden="true" />
                Tryb autonomiczny
              </span>
            )}
          </div>

          <div className="token-input-wrapper">
            <label className="token-prefix" htmlFor="auth-token">
              Twój token
            </label>
            <input
              id="auth-token"
              type="password"
              className="token-input"
              placeholder="Wpisz swój token"
              value={token}
              onChange={(e) => {
                onTokenChange(e.target.value);
                setTokenCopied(false);
              }}
              autoComplete="off"
              spellCheck="false"
            />
            {token.length > 0 && (
              <button
                type="button"
                className="token-copy-btn"
                onClick={copyToken}
                aria-label="Kopiuj token"
                title="Kopiuj token"
              >
                <span aria-hidden="true">{tokenCopied ? '✓' : '⧉'}</span>
                {tokenCopied && (
                  <span className="token-copy-feedback" aria-live="polite">
                    Skopiowano
                  </span>
                )}
              </button>
            )}
            {token.length > 0 && (
              <button
                type="button"
                className="token-clear-btn"
                onClick={() => onTokenChange('')}
                aria-label="Wyczyść token"
                title="Wyczyść token z pamięci"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

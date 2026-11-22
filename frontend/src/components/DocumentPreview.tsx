import React, { useEffect, useState } from 'react';

interface DocumentPreviewProps {
  file: File;
}

export const DocumentPreview: React.FC<DocumentPreviewProps> = ({ file }) => {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  const ext = file.name.split('.').pop()?.toLowerCase() || '';
  const isPdf = ext === 'pdf';
  const isImage = ['png', 'jpg', 'jpeg', 'jpe', 'tiff'].includes(ext);

  useEffect(() => {
    // Generate ephemeral object URL for in-memory preview
    const url = URL.createObjectURL(file);
    setBlobUrl(url);

    // Explicit cleanup on unmount or file change
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  return (
    <div className={`preview-container ${!isPdf && !isImage ? 'preview-container-summary' : ''}`}>
      <div className="pane-header">
        <h3 className="pane-title">Podgląd dokumentu źródłowego</h3>
        <span className="badge badge-info">{file.name}</span>
      </div>

      <div className="preview-content">
        {isPdf && blobUrl && (
          <iframe
            src={`${blobUrl}#toolbar=0`}
            className="preview-frame"
            title="Podgląd PDF"
          />
        )}

        {isImage && blobUrl && (
          <div className="preview-image-wrapper">
            <img src={blobUrl} alt="Podgląd formularza" className="preview-image" />
          </div>
        )}

        {!isPdf && !isImage && (
          <div className="preview-summary-card">
            <div className="summary-card-icon">📑</div>
            <h4 className="summary-card-title">Dokument pakietu biurowego</h4>
            <p className="summary-card-desc">
              Plik <strong>{file.name}</strong> ({ext.toUpperCase()}) został pomyślnie
              przeanalizowany w pamięci RAM.
            </p>
            <div className="summary-attributes">
              <div className="summary-row">
                <span className="summary-label">Format:</span>
                <span className="summary-value">{ext.toUpperCase()}</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Rozmiar pliku:</span>
                <span className="summary-value">{(file.size / 1024).toFixed(1)} KB</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Typ MIME:</span>
                <span className="summary-value">{file.type || 'application/octet-stream'}</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Przetwarzanie:</span>
                <span className="summary-value">100% lokalnie / RAM</span>
              </div>
            </div>
            <div className="summary-note">
              Podgląd strukturalny pól, tabel i pól wyboru znajduje się w prawym panelu.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

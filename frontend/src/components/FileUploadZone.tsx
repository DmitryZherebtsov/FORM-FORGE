import React, { useRef, useState } from 'react';

const ALLOWED_EXTENSIONS = [
  'pdf',
  'docx',
  'doc',
  'xlsx',
  'ods',
  'png',
  'jpg',
  'jpeg',
  'jpe',
  'tiff',
];
const MAX_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

interface FileUploadZoneProps {
  onFileSelect: (file: File) => void;
  isLoading: boolean;
  selectedFile: File | null;
  onClear: () => void;
}

export const FileUploadZone: React.FC<FileUploadZoneProps> = ({
  onFileSelect,
  isLoading,
  selectedFile,
  onClear,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndSelect = (file: File) => {
    setClientError(null);
    const ext = file.name.split('.').pop()?.toLowerCase() || '';

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setClientError(
        `Niedozwolone rozszerzenie pliku: .${ext}. Dozwolone: ${ALLOWED_EXTENSIONS.map(
          (e) => `.${e}`
        ).join(', ')}`
      );
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      setClientError(
        `Plik przekracza limit 20 MB (${sizeMB} MB). Wybierz mniejszy plik.`
      );
      return;
    }

    onFileSelect(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isLoading) setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (isLoading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSelect(e.target.files[0]);
    }
    // reset input value so re-selecting same file works
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="upload-section">
      <div
        className={`drop-zone ${isDragOver ? 'drop-zone-dragover' : ''} ${
          isLoading ? 'drop-zone-loading' : ''
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isLoading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: 'none' }}
          accept=".pdf,.docx,.doc,.xlsx,.ods,.png,.jpg,.jpeg,.jpe,.tiff"
          onChange={handleFileChange}
          disabled={isLoading}
        />

        {isLoading ? (
          <div className="upload-loading-state">
            <div className="spinner" />
            <div className="upload-loading-text">
              Trwa cyfryzacja i przetwarzanie dokumentu w pamięci RAM...
            </div>
          </div>
        ) : selectedFile ? (
          <div className="upload-file-info" onClick={(e) => e.stopPropagation()}>
            <div className="file-badge">
              <span className="file-icon">📄</span>
              <div className="file-details">
                <span className="file-name">{selectedFile.name}</span>
                <span className="file-meta">
                  {(selectedFile.size / 1024).toFixed(1)} KB • {selectedFile.type || 'format wykryty'}
                </span>
              </div>
            </div>
            <div className="upload-actions">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => fileInputRef.current?.click()}
              >
                Zmień plik
              </button>
              <button
                type="button"
                className="btn btn-outline-danger btn-sm"
                onClick={onClear}
              >
                Usuń
              </button>
            </div>
          </div>
        ) : (
          <div className="upload-prompt">
            <div className="upload-icon">📁</div>
            <div className="upload-title">
              Przeciągnij i upuść formularz tutaj lub <span>kliknij, aby przeglądać</span>
            </div>
            <div className="upload-formats">
              Obsługiwane formaty: PDF, DOCX, DOC, XLSX, ODS, PNG, JPG, JPE, TIFF (maks. 20 MB)
            </div>
          </div>
        )}
      </div>

      {clientError && (
        <div className="error-alert-inline">
          <span className="alert-icon">⚠️</span>
          <span>{clientError}</span>
        </div>
      )}
    </div>
  );
};

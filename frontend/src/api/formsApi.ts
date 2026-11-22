import type {
  DigitizeResponseDTO,
  HealthResponseDTO,
  LlmWarmupResponseDTO,
} from '../types/digitize';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail || `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Check backend readiness and status via GET /api/v1/health.
 */
export async function getHealth(): Promise<HealthResponseDTO> {
  const url = '/api/v1/health';
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new ApiError(response.status, `Health check returned ${response.status}`);
    }
    return (await response.json()) as HealthResponseDTO;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(0, 'Backend is offline or unreachable');
  }
}

export async function warmupLlm(token: string): Promise<LlmWarmupResponseDTO> {
  let response: Response;
  try {
    response = await fetch('/api/v1/llm/warmup', {
      method: 'POST',
      headers: token.trim() ? { Authorization: `Bearer ${token.trim()}` } : {},
    });
  } catch {
    throw new ApiError(0, 'Nie można połączyć się z usługą rozgrzewania LLM.');
  }

  if (!response.ok) {
    const errorBody = await response.text();
    let detail = errorBody;
    try {
      const error = JSON.parse(errorBody);
      detail = error.detail || error.message || '';
    } catch {}
    throw new ApiError(response.status, detail || `Błąd rozgrzewania LLM (${response.status}).`);
  }

  return (await response.json()) as LlmWarmupResponseDTO;
}

/**
 * Upload document file to POST /api/v1/forms/digitize.
 */
export async function digitizeForm(
  file: File,
  token?: string
): Promise<DigitizeResponseDTO> {
  const formData = new FormData();
  formData.append('file', file);

  const headers: HeadersInit = {};
  if (token && token.trim()) {
    headers['Authorization'] = `Bearer ${token.trim()}`;
  }

  const url = '/api/v1/forms/digitize';
  let response: Response;

  try {
    response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    });
  } catch {
    throw new ApiError(0, 'Failed to connect to backend server. Please verify backend is running.');
  }

  if (!response.ok) {
    let errorDetail = '';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || '';
    } catch {
      errorDetail = await response.text();
    }

    switch (response.status) {
      case 400:
        throw new ApiError(400, errorDetail || 'Nieprawidłowa nazwa pliku lub żądanie (400 Bad Request)');
      case 401:
        throw new ApiError(401, errorDetail || 'Wymagana autoryzacja Bearer token lub token nieprawidłowy (401 Unauthorized)');
      case 413:
        throw new ApiError(413, errorDetail || 'Rozmiar pliku przekracza dopuszczalny limit (413 Payload Too Large)');
      case 415:
        throw new ApiError(415, errorDetail || 'Niewspierany format pliku lub niezgodność typu MIME (415 Unsupported Media Type)');
      case 422:
        throw new ApiError(422, errorDetail || 'Plik uszkodzony lub nie można odczytać struktury formularza (422 Unprocessable Entity)');
      default:
        throw new ApiError(response.status, errorDetail || `Błąd serwera (kod ${response.status})`);
    }
  }

  return (await response.json()) as DigitizeResponseDTO;
}

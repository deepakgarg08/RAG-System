/**
 * streaming.ts — SSE streaming handler using fetch + ReadableStream.
 *
 * Uses fetch instead of EventSource because EventSource only supports GET.
 * Our query endpoints are POST, so we use fetch with streaming body reading.
 *
 * SSE format from the backend:
 *   data: <plain-text token>\n\n
 *   data: [DONE]\n\n
 */

const BASE_URL = import.meta.env.VITE_SERVER_BASE_URL ?? 'http://localhost:8000';

/** Shared SSE reader — consumes a Response body and yields plain-text tokens. */
async function* readSseStream(response: Response): AsyncGenerator<string> {
  if (!response.body) throw new Error('No response body');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const token = line.slice(6);
        if (token === '[DONE]') return;
        if (token.trim()) yield token;
      }
    }
  }
}

/** MODE 3 — Stream an answer for a cross-database question (POST /api/query). */
export async function* streamQuery(question: string): AsyncGenerator<string> {
  const response = await fetch(`${BASE_URL}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    throw new Error(`Query failed: ${response.status} ${response.statusText}`);
  }

  yield* readSseStream(response);
}

/**
 * MODE 1 / MODE 2 — Stream analysis of a temporary uploaded document.
 * The file is sent as multipart form data and is NEVER stored in the database.
 *
 * @param file     The uploaded contract file (PDF / JPG / PNG).
 * @param question The user's question about the document.
 * @param mode     "single" (no DB) or "compare" (uploaded doc vs DB contracts).
 */
export async function* streamAnalyze(
  file: File,
  question: string,
  mode: 'single' | 'compare',
): AsyncGenerator<string> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('question', question);
  formData.append('mode', mode);

  const response = await fetch(`${BASE_URL}/api/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error((err as { detail?: string }).detail ?? `Analysis failed: ${response.status}`);
  }

  yield* readSseStream(response);
}

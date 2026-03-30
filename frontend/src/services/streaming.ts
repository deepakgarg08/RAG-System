/**
 * streaming.ts — SSE streaming handler using fetch + ReadableStream.
 *
 * Uses fetch instead of EventSource because EventSource only supports GET.
 * Our query endpoint is POST, so we use fetch with streaming body reading.
 *
 * SSE format from the backend:
 *   data: <plain-text token>\n\n
 *   data: [DONE]\n\n
 */

const BASE_URL = 'http://localhost:8000';

export async function* streamQuery(question: string): AsyncGenerator<string> {
  const response = await fetch(`${BASE_URL}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Query failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    // Keep the last (potentially incomplete) line in the buffer
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

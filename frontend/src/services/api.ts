/**
 * api.ts — Fetch-based HTTP client for all non-streaming API calls.
 * Streaming is handled separately in streaming.ts using fetch + ReadableStream.
 * Uses the native Fetch API — no extra HTTP library required.
 */

import type { HealthResponse, IngestResponse } from '../types';

const BASE_URL = 'http://localhost:8000';

export async function uploadContract(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${BASE_URL}/api/ingest`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail ?? 'Upload failed');
  }
  return response.json() as Promise<IngestResponse>;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BASE_URL}/health`);
  if (!response.ok) throw new Error('Health check failed');
  return response.json() as Promise<HealthResponse>;
}

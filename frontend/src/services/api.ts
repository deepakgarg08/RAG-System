/**
 * api.ts — Fetch-based HTTP client for all non-streaming API calls.
 * Streaming is handled separately in streaming.ts using fetch + ReadableStream.
 * Uses the native Fetch API — no extra HTTP library required.
 */

import type { HealthResponse, IngestResponse } from '../types';

export const BASE_URL = 'http://localhost:8000';

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

export async function getSuggestedQuestions(): Promise<string[]> {
  const response = await fetch(`${BASE_URL}/api/suggested-questions`);
  if (!response.ok) return [];
  const data = (await response.json()) as { questions: string[] };
  return data.questions ?? [];
}

/**
 * POST /api/compliance — Evaluate a contract against compliance guidelines.
 * The file is processed in-memory and is NEVER stored in the database.
 *
 * @param file       The contract file (PDF / JPG / PNG).
 * @param guidelines Optional custom guidelines. Defaults to Riverty's standard checklist.
 */
export async function checkComplianceApi(
  file: File,
  guidelines?: string,
): Promise<{ compliant: boolean; violations: string[]; explanation: string }> {
  const formData = new FormData();
  formData.append('file', file);
  if (guidelines) formData.append('guidelines', guidelines);

  const response = await fetch(`${BASE_URL}/api/compliance`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error((err as { detail?: string }).detail ?? `Compliance check failed: ${response.status}`);
  }

  return response.json() as Promise<{ compliant: boolean; violations: string[]; explanation: string }>;
}

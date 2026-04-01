/**
 * index.ts — Shared TypeScript interfaces for the Riverty Contract Review frontend.
 * Mirrors the Pydantic response models from the FastAPI backend.
 */

export interface IngestResponse {
  filename: string;
  file_type: string;
  language: string;
  chunks_created: number;
  status: 'success' | 'failed';
  error?: string;
}

export interface HealthResponse {
  status: string;
  document_count: number;
  mode: 'demo' | 'production';
  app_env: string;
}

export interface UploadedFile {
  id: string;
  filename: string;
  fileType: string;
  language: string;
  chunksCreated: number;
  uploadedAt: Date;
  status: 'success' | 'failed';
}

export interface StreamingState {
  isStreaming: boolean;
  content: string;
  isDone: boolean;
  error: string | null;
}

/** The three analysis modes exposed in the UI. */
export type AnalysisMode = 'search' | 'analyze' | 'compare';

/** Mirrors ComplianceResult from the FastAPI backend. */
export interface ComplianceResult {
  compliant: boolean;
  violations: string[];
  explanation: string;
}

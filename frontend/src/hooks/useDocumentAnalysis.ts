/**
 * useDocumentAnalysis.ts — State for temporary document analysis (MODE 1 & 2).
 *
 * Manages a temporary file that is NEVER stored in the vector database.
 * Supports:
 *   - Streaming Q&A on the uploaded doc (MODE 1: single, MODE 2: compare)
 *   - Compliance check returning a structured JSON result (MODE 1 variant)
 */

import { useState } from 'react';
import { streamAnalyze } from '../services/streaming';
import { checkComplianceApi } from '../services/api';
import type { ComplianceResult } from '../types';

export interface UseDocumentAnalysisReturn {
  analysisFile: File | null;
  setAnalysisFile: (file: File | null) => void;
  isStreaming: boolean;
  content: string;
  isDone: boolean;
  streamError: string | null;
  complianceResult: ComplianceResult | null;
  isCheckingCompliance: boolean;
  complianceError: string | null;
  submitAnalysis: (question: string, mode: 'single' | 'compare') => Promise<void>;
  runComplianceCheck: () => Promise<void>;
  clearResponse: () => void;
}

export function useDocumentAnalysis(): UseDocumentAnalysisReturn {
  const [analysisFile, setAnalysisFile] = useState<File | null>(null);

  // Streaming state (Q&A)
  const [isStreaming, setIsStreaming] = useState(false);
  const [content, setContent] = useState('');
  const [isDone, setIsDone] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  // Compliance check state
  const [complianceResult, setComplianceResult] = useState<ComplianceResult | null>(null);
  const [isCheckingCompliance, setIsCheckingCompliance] = useState(false);
  const [complianceError, setComplianceError] = useState<string | null>(null);

  async function submitAnalysis(question: string, mode: 'single' | 'compare'): Promise<void> {
    if (!analysisFile) return;

    setIsStreaming(true);
    setContent('');
    setIsDone(false);
    setStreamError(null);
    setComplianceResult(null);
    setComplianceError(null);

    try {
      for await (const token of streamAnalyze(analysisFile, question, mode)) {
        setContent((prev) => prev + token);
      }
      setIsDone(true);
    } catch (err) {
      setStreamError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setIsStreaming(false);
    }
  }

  async function runComplianceCheck(): Promise<void> {
    if (!analysisFile) return;

    setIsCheckingCompliance(true);
    setComplianceResult(null);
    setComplianceError(null);
    setContent('');
    setIsDone(false);

    try {
      const result = await checkComplianceApi(analysisFile);
      setComplianceResult(result);
    } catch (err) {
      setComplianceError(err instanceof Error ? err.message : 'Compliance check failed');
    } finally {
      setIsCheckingCompliance(false);
    }
  }

  function clearResponse(): void {
    setContent('');
    setIsDone(false);
    setStreamError(null);
    setComplianceResult(null);
    setComplianceError(null);
  }

  function handleSetAnalysisFile(file: File | null): void {
    setAnalysisFile(file);
    clearResponse();
  }

  return {
    analysisFile,
    setAnalysisFile: handleSetAnalysisFile,
    isStreaming,
    content,
    isDone,
    streamError,
    complianceResult,
    isCheckingCompliance,
    complianceError,
    submitAnalysis,
    runComplianceCheck,
    clearResponse,
  };
}

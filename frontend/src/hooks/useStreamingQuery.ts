/**
 * useStreamingQuery.ts — Manages streaming query state.
 * Consumes the async generator from streaming.ts and appends tokens to content.
 */

import { useState } from 'react';
import { streamQuery } from '../services/streaming';
import type { StreamingState } from '../types';

interface UseStreamingQueryReturn extends StreamingState {
  submitQuery: (question: string) => Promise<void>;
  clearResponse: () => void;
}

export function useStreamingQuery(): UseStreamingQueryReturn {
  const [state, setState] = useState<StreamingState>({
    isStreaming: false,
    content: '',
    isDone: false,
    error: null,
  });

  async function submitQuery(question: string): Promise<void> {
    setState({ isStreaming: true, content: '', isDone: false, error: null });

    try {
      for await (const token of streamQuery(question)) {
        setState((prev) => ({ ...prev, content: prev.content + token }));
      }
      setState((prev) => ({ ...prev, isStreaming: false, isDone: true }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isStreaming: false,
        isDone: false,
        error: err instanceof Error ? err.message : 'Query failed',
      }));
    }
  }

  function clearResponse(): void {
    setState({ isStreaming: false, content: '', isDone: false, error: null });
  }

  return { ...state, submitQuery, clearResponse };
}

/**
 * App.tsx — Root component. Wires hooks to components and passes handlers down.
 * Owns health state so document_count (from the backend) can gate the query UI
 * without requiring the user to upload something in the current session.
 */

import { useEffect, useState } from 'react';
import AppLayout from './components/Layout/AppLayout';
import FileUpload from './components/Upload/FileUpload';
import UploadStatus from './components/Upload/UploadStatus';
import QueryInput from './components/Query/QueryInput';
import StreamingResponse from './components/Query/StreamingResponse';
import SuggestedQueries from './components/Query/SuggestedQueries';
import { useFileUpload } from './hooks/useFileUpload';
import { useStreamingQuery } from './hooks/useStreamingQuery';
import { getHealth } from './services/api';
import type { HealthResponse } from './types';

export default function App(): React.ReactElement {
  const { uploadedFiles, isUploading, error: uploadError, handleUpload, clearError } = useFileUpload();
  const { content, isStreaming, isDone, error: queryError, submitQuery } = useStreamingQuery();
  const [question, setQuestion] = useState('');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [connected, setConnected] = useState(false);

  async function fetchHealth(): Promise<void> {
    try {
      const data = await getHealth();
      setHealth(data);
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }

  useEffect(() => {
    void fetchHealth();
    const interval = setInterval(() => void fetchHealth(), 30_000);
    return () => clearInterval(interval);
  }, []);

  // True if the backend already has indexed documents OR the user uploaded
  // something in this session — whichever comes first.
  const hasDocuments =
    (health !== null && health.document_count > 0) ||
    uploadedFiles.some((f) => f.status === 'success');

  function handleSubmit(): void {
    if (question.trim()) {
      void submitQuery(question.trim());
    }
  }

  function handleSuggestion(q: string): void {
    setQuestion(q);
    void submitQuery(q);
  }

  const uploadPanel = (
    <div>
      <p style={{ margin: '0 0 12px', fontSize: 11, fontWeight: 700, color: 'var(--color-gray-600)', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
        Contracts
      </p>
      <FileUpload onUpload={handleUpload} isUploading={isUploading} />
      <UploadStatus files={uploadedFiles} error={uploadError} onClearError={clearError} />
    </div>
  );

  const queryPanel = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <p style={{ margin: '0 0 12px', fontSize: 11, fontWeight: 700, color: 'var(--color-gray-600)', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
          Ask a question
        </p>
        <QueryInput
          value={question}
          onChange={setQuestion}
          onSubmit={handleSubmit}
          isStreaming={isStreaming}
          hasDocuments={hasDocuments}
        />
      </div>

      <SuggestedQueries
        onSelect={handleSuggestion}
        disabled={isStreaming || !hasDocuments}
      />

      <StreamingResponse
        content={content}
        isStreaming={isStreaming}
        isDone={isDone}
        error={queryError}
      />
    </div>
  );

  return <AppLayout uploadPanel={uploadPanel} queryPanel={queryPanel} health={health} connected={connected} />;
}

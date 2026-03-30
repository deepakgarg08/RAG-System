/**
 * App.tsx — Root component. Wires hooks to components and passes handlers down.
 */

import { useState } from 'react';
import AppLayout from './components/Layout/AppLayout';
import FileUpload from './components/Upload/FileUpload';
import UploadStatus from './components/Upload/UploadStatus';
import QueryInput from './components/Query/QueryInput';
import StreamingResponse from './components/Query/StreamingResponse';
import SuggestedQueries from './components/Query/SuggestedQueries';
import { useFileUpload } from './hooks/useFileUpload';
import { useStreamingQuery } from './hooks/useStreamingQuery';

export default function App(): React.ReactElement {
  const { uploadedFiles, isUploading, error: uploadError, handleUpload, clearError } = useFileUpload();
  const { content, isStreaming, isDone, error: queryError, submitQuery } = useStreamingQuery();
  const [question, setQuestion] = useState('');

  const hasDocuments = uploadedFiles.some((f) => f.status === 'success');

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
      <h2 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700, color: 'var(--color-gray-900)' }}>
        Document Management
      </h2>
      <FileUpload onUpload={handleUpload} isUploading={isUploading} />
      <UploadStatus files={uploadedFiles} error={uploadError} onClearError={clearError} />
    </div>
  );

  const queryPanel = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700, color: 'var(--color-gray-900)' }}>
          Query Interface
        </h2>
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

  return <AppLayout uploadPanel={uploadPanel} queryPanel={queryPanel} />;
}

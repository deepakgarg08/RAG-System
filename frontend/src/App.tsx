/**
 * App.tsx — Root component. Manages the three analysis modes and wires all hooks.
 *
 * MODE 1 "Analyze Document"  — Temp file + Q&A → POST /api/analyze (mode=single)
 *                               OR compliance check → POST /api/compliance
 * MODE 2 "Compare Document"  — Temp file + question → POST /api/analyze (mode=compare)
 * MODE 3 "Search Contracts"  — Question only → POST /api/query (existing flow)
 *
 * Left sidebar: persistent knowledge base upload (feeds the vector DB for MODE 3).
 * Right panel: mode selector + mode-specific UI.
 */

import { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import AppLayout from './components/Layout/AppLayout';
import FileUpload from './components/Upload/FileUpload';
import UploadStatus from './components/Upload/UploadStatus';
import QueryInput from './components/Query/QueryInput';
import StreamingResponse from './components/Query/StreamingResponse';
import SuggestedQueries from './components/Query/SuggestedQueries';
import ModeSelector from './components/Analysis/ModeSelector';
import TemporaryUpload from './components/Analysis/TemporaryUpload';
import CompliancePanel from './components/Analysis/CompliancePanel';
import ExampleQueries from './components/Analysis/ExampleQueries';
import { useFileUpload } from './hooks/useFileUpload';
import { useStreamingQuery } from './hooks/useStreamingQuery';
import { useDocumentAnalysis } from './hooks/useDocumentAnalysis';
import { getHealth } from './services/api';
import type { AnalysisMode, HealthResponse } from './types';

// Static example questions shown in Mode 1 and Mode 2
const ANALYZE_EXAMPLES = [
  'Does this contract contain a termination clause?',
  'What are the liability limitations?',
  'Is GDPR / data protection addressed?',
  'What is the governing law?',
];

const COMPARE_EXAMPLES = [
  'How does this contract differ from others in the database?',
  'What clauses are missing compared to similar contracts?',
  'Are the penalty terms typical for contracts of this type?',
];

export default function App(): React.ReactElement {
  // --- Persistent knowledge base upload (left sidebar, used for MODE 3) ---
  const { uploadedFiles, isUploading, error: uploadError, handleUpload, clearError } = useFileUpload();

  // --- MODE 3: Search across the database ---
  const { content: searchContent, isStreaming: searchStreaming, isDone: searchDone, error: searchError, submitQuery, clearResponse: clearSearch } = useStreamingQuery();

  // --- MODE 1 & 2: Temporary document analysis ---
  const {
    analysisFile,
    setAnalysisFile,
    isStreaming: analysisStreaming,
    content: analysisContent,
    isDone: analysisDone,
    streamError: analysisError,
    complianceResult,
    isCheckingCompliance,
    complianceError,
    submitAnalysis,
    runComplianceCheck,
    clearResponse: clearAnalysis,
  } = useDocumentAnalysis();

  // --- Shared state ---
  const [mode, setMode] = useState<AnalysisMode>('search');
  const [question, setQuestion] = useState('');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [connected, setConnected] = useState(false);
  const [connectionChecked, setConnectionChecked] = useState(false);

  async function fetchHealth(): Promise<void> {
    try {
      const data = await getHealth();
      setHealth(data);
      setConnected(true);
    } catch {
      setConnected(false);
    } finally {
      setConnectionChecked(true);
    }
  }

  useEffect(() => {
    void fetchHealth();
    const interval = setInterval(() => void fetchHealth(), 30_000);
    return () => clearInterval(interval);
  }, []);

  // Clear question + response whenever the mode changes
  function handleModeChange(newMode: AnalysisMode): void {
    setMode(newMode);
    setQuestion('');
    clearSearch();
    clearAnalysis();
  }

  // True if the DB has indexed documents OR the user persisted something this session
  const hasDbDocuments =
    (health !== null && health.document_count > 0) ||
    uploadedFiles.some((f) => f.status === 'success');

  // --- MODE 3 submit ---
  function handleSearchSubmit(): void {
    if (question.trim()) void submitQuery(question.trim());
  }

  // --- MODE 1 / 2 submit ---
  function handleAnalysisSubmit(): void {
    if (!question.trim() || !analysisFile) return;
    const apiMode = mode === 'compare' ? 'compare' : 'single';
    void submitAnalysis(question.trim(), apiMode);
  }

  const isAnyStreaming = searchStreaming || analysisStreaming || isCheckingCompliance;

  // -------------------------------------------------------------------------
  // Left sidebar — always: persistent knowledge base upload
  // -------------------------------------------------------------------------
  const uploadPanel = (
    <div>
      <p
        style={{
          margin: '0 0 4px',
          fontSize: 11,
          fontWeight: 700,
          color: 'var(--color-gray-600)',
          textTransform: 'uppercase',
          letterSpacing: '0.6px',
        }}
      >
        Knowledge Base
      </p>
      <p style={{ margin: '0 0 12px', fontSize: 11, color: 'var(--color-gray-600)' }}>
        Stored for search across contracts
      </p>
      <FileUpload onUpload={handleUpload} isUploading={isUploading} />
      <UploadStatus files={uploadedFiles} error={uploadError} onClearError={clearError} />
    </div>
  );

  // -------------------------------------------------------------------------
  // Right panel — mode-specific content
  // -------------------------------------------------------------------------

  // --- MODE 3: Search across the database ---
  const searchPanel = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SuggestedQueries
        onSelect={(q) => {
          setQuestion(q);
          void submitQuery(q);
        }}
        disabled={isAnyStreaming || !hasDbDocuments}
      />
      <div>
        <p
          style={{
            margin: '0 0 8px',
            fontSize: 11,
            fontWeight: 700,
            color: 'var(--color-gray-600)',
            textTransform: 'uppercase',
            letterSpacing: '0.6px',
          }}
        >
          Ask a question
        </p>
        <QueryInput
          value={question}
          onChange={setQuestion}
          onSubmit={handleSearchSubmit}
          isStreaming={searchStreaming}
          hasDocuments={hasDbDocuments}
        />
      </div>
      <StreamingResponse
        content={searchContent}
        isStreaming={searchStreaming}
        isDone={searchDone}
        error={searchError}
      />
    </div>
  );

  // --- MODE 1: Analyze a single document ---
  const analyzePanel = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <TemporaryUpload
        file={analysisFile}
        onFileSelect={setAnalysisFile}
        isProcessing={analysisStreaming || isCheckingCompliance}
      />

      {analysisFile && (
        <>
          <ExampleQueries
            questions={ANALYZE_EXAMPLES}
            onSelect={(q) => {
              setQuestion(q);
              void submitAnalysis(q, 'single');
            }}
            disabled={isAnyStreaming}
          />

          <div>
            <p
              style={{
                margin: '0 0 8px',
                fontSize: 11,
                fontWeight: 700,
                color: 'var(--color-gray-600)',
                textTransform: 'uppercase',
                letterSpacing: '0.6px',
              }}
            >
              Ask a question about this document
            </p>
            <QueryInput
              value={question}
              onChange={setQuestion}
              onSubmit={handleAnalysisSubmit}
              isStreaming={analysisStreaming}
              hasDocuments={true}
            />
          </div>

          {/* Compliance check — secondary action */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ flex: 1, height: 1, backgroundColor: 'var(--color-gray-300)' }} />
            <span style={{ fontSize: 12, color: 'var(--color-gray-600)', whiteSpace: 'nowrap' }}>or</span>
            <div style={{ flex: 1, height: 1, backgroundColor: 'var(--color-gray-300)' }} />
          </div>

          <button
            onClick={() => void runComplianceCheck()}
            disabled={isAnyStreaming}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              padding: '10px 16px',
              border: '1.5px solid var(--color-navy)',
              borderRadius: 'var(--radius-md)',
              backgroundColor: isAnyStreaming ? 'var(--color-gray-100)' : 'transparent',
              color: isAnyStreaming ? 'var(--color-gray-600)' : 'var(--color-navy)',
              fontWeight: 600,
              fontSize: 13,
              cursor: isAnyStreaming ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.15s, color 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!isAnyStreaming) {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--color-navy)';
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-white)';
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-navy)';
            }}
          >
            {isCheckingCompliance ? (
              <span>Checking…</span>
            ) : (
              <>
                <ShieldCheck size={15} />
                <span>Check Compliance (Riverty Guidelines)</span>
              </>
            )}
          </button>

          {/* Compliance error */}
          {complianceError && (
            <div
              style={{
                backgroundColor: '#fce8e6',
                border: '1px solid #f5c6c3',
                borderRadius: 'var(--radius-sm)',
                padding: '10px 14px',
                fontSize: 13,
                color: 'var(--color-red)',
              }}
            >
              {complianceError}
            </div>
          )}

          {/* Compliance result */}
          {complianceResult && (
            <CompliancePanel result={complianceResult} filename={analysisFile.name} />
          )}
        </>
      )}

      {/* Streaming Q&A result */}
      {(analysisContent || analysisStreaming || analysisError) && (
        <StreamingResponse
          content={analysisContent}
          isStreaming={analysisStreaming}
          isDone={analysisDone}
          error={analysisError}
        />
      )}
    </div>
  );

  // --- MODE 2: Compare uploaded document with database ---
  const comparePanel = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {!hasDbDocuments && (
        <div
          style={{
            backgroundColor: '#fef9e7',
            border: '1px solid #f9e4a0',
            borderRadius: 'var(--radius-sm)',
            padding: '8px 14px',
            fontSize: 13,
            color: '#856404',
          }}
        >
          Add contracts to the knowledge base (left sidebar) before using Compare mode.
        </div>
      )}

      <TemporaryUpload
        file={analysisFile}
        onFileSelect={setAnalysisFile}
        isProcessing={analysisStreaming}
      />

      {analysisFile && (
        <>
          <ExampleQueries
            questions={COMPARE_EXAMPLES}
            onSelect={(q) => {
              setQuestion(q);
              void submitAnalysis(q, 'compare');
            }}
            disabled={isAnyStreaming || !hasDbDocuments}
          />

          <div>
            <p
              style={{
                margin: '0 0 8px',
                fontSize: 11,
                fontWeight: 700,
                color: 'var(--color-gray-600)',
                textTransform: 'uppercase',
                letterSpacing: '0.6px',
              }}
            >
              Comparison question
            </p>
            <QueryInput
              value={question}
              onChange={setQuestion}
              onSubmit={handleAnalysisSubmit}
              isStreaming={analysisStreaming}
              hasDocuments={hasDbDocuments}
            />
          </div>
        </>
      )}

      {(analysisContent || analysisStreaming || analysisError) && (
        <StreamingResponse
          content={analysisContent}
          isStreaming={analysisStreaming}
          isDone={analysisDone}
          error={analysisError}
        />
      )}
    </div>
  );

  const queryPanel = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <ModeSelector mode={mode} onChange={handleModeChange} />
      <div style={{ height: 1, backgroundColor: 'var(--color-gray-300)' }} />
      {mode === 'search' && searchPanel}
      {mode === 'analyze' && analyzePanel}
      {mode === 'compare' && comparePanel}
    </div>
  );

  return (
    <AppLayout
      uploadPanel={uploadPanel}
      queryPanel={queryPanel}
      health={health}
      connected={connected}
      connectionChecked={connectionChecked}
    />
  );
}

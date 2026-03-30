/**
 * StreamingResponse.tsx — Renders the LLM answer as tokens stream in.
 * Shows a blinking cursor while streaming; source attribution when done.
 * Parses source file references from the answer text (lines starting with "•").
 */

interface StreamingResponseProps {
  content: string;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
}

function extractSources(content: string): string[] {
  const sources: string[] = [];
  const lines = content.split('\n');
  for (const line of lines) {
    // Lines like: "• contract_nda_techcorp_2023.txt — page 1, chunk 2/4 (relevance: 0.71)"
    const match = line.match(/^[•·-]\s+([\w.\-_]+\.\w+)/);
    if (match) sources.push(match[1]);
  }
  return [...new Set(sources)];
}

export default function StreamingResponse({
  content,
  isStreaming,
  isDone,
  error,
}: StreamingResponseProps): React.ReactElement {
  if (error) {
    return (
      <div
        style={{
          backgroundColor: '#fce8e6',
          border: '1px solid #f5c6c3',
          borderRadius: 'var(--radius-md)',
          padding: '14px 16px',
          color: 'var(--color-red)',
          fontSize: 14,
        }}
      >
        {error}
      </div>
    );
  }

  if (!content && !isStreaming) {
    return (
      <div
        style={{
          padding: '32px 16px',
          textAlign: 'center',
          color: 'var(--color-gray-600)',
          fontSize: 14,
        }}
      >
        Ask a question above to analyse your contracts.
      </div>
    );
  }

  const sources = isDone ? extractSources(content) : [];

  return (
    <div
      style={{
        backgroundColor: 'var(--color-white)',
        border: '1px solid var(--color-gray-300)',
        borderRadius: 'var(--radius-md)',
        padding: '16px',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <pre
        style={{
          margin: 0,
          fontFamily: 'inherit',
          fontSize: 14,
          lineHeight: 1.7,
          color: 'var(--color-gray-900)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {content}
        {isStreaming && <span className="streaming-cursor" />}
      </pre>

      {isDone && sources.length > 0 && (
        <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--color-gray-100)' }}>
          <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 600, color: 'var(--color-gray-600)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Sources
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {sources.map((s) => (
              <span
                key={s}
                style={{
                  backgroundColor: '#e8f0fe',
                  color: 'var(--color-blue)',
                  border: '1px solid #c5d8fb',
                  borderRadius: 'var(--radius-sm)',
                  padding: '3px 10px',
                  fontSize: 12,
                  fontFamily: 'monospace',
                }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

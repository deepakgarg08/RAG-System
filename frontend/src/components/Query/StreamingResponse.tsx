/**
 * StreamingResponse.tsx — Renders the LLM answer with a clean sources panel.
 *
 * Splits the raw content at the "**Sources:**" marker appended by the backend
 * formatter, renders the answer prose cleanly, then shows each unique source
 * as a clickable card that opens the file at the referenced page.
 */

import { ExternalLink } from 'lucide-react';
import { BASE_URL } from '../../services/api';

interface ParsedSource {
  filename: string;
  page: number | null;
  relevance: number | null;
  key: string;
}

/**
 * Split raw LLM output at the "**Sources:**" block the backend formatter appends.
 * Returns the prose answer (stripped) and the raw source lines (each starts with •).
 */
function splitContent(content: string): { answer: string; sourceLines: string[] } {
  // Find the **Sources:** marker line
  const lines = content.split('\n');
  const markerIdx = lines.findIndex((l) => l.trim().startsWith('**Sources:**'));

  if (markerIdx !== -1) {
    return {
      answer: lines.slice(0, markerIdx).join('\n').trimEnd(),
      sourceLines: lines.slice(markerIdx + 1).filter((l) => l.trimStart().startsWith('•')),
    };
  }

  // Fallback: split at the first bullet line (older format)
  const firstBullet = lines.findIndex((l) => l.trimStart().startsWith('•'));
  if (firstBullet === -1) return { answer: content, sourceLines: [] };
  return {
    answer: lines.slice(0, firstBullet).join('\n').trimEnd(),
    sourceLines: lines.slice(firstBullet).filter((l) => l.trimStart().startsWith('•')),
  };
}

function parseSource(line: string): ParsedSource {
  // e.g. "  • ecomdata_converted.pdf — page 2, chunk 32/81 (relevance: 0.80)"
  const filenameMatch = line.match(/•\s+([\w.\-_ ]+\.\w+)/);
  const pageMatch = line.match(/page (\d+)/);
  const relevanceMatch = line.match(/relevance:\s*([\d.]+)/);
  const filename = filenameMatch ? filenameMatch[1].trim() : line.replace('•', '').trim();
  return {
    filename,
    page: pageMatch ? parseInt(pageMatch[1], 10) : null,
    relevance: relevanceMatch ? parseFloat(relevanceMatch[1]) : null,
    key: line.trim(),
  };
}

/** Deduplicate by filename — show each source file once (highest relevance kept). */
function deduplicateSources(sources: ParsedSource[]): ParsedSource[] {
  const map = new Map<string, ParsedSource>();
  for (const s of sources) {
    const existing = map.get(s.filename);
    if (!existing || (s.relevance ?? 0) > (existing.relevance ?? 0)) {
      map.set(s.filename, s);
    }
  }
  return [...map.values()];
}

function relevanceColor(score: number): string {
  if (score >= 0.65) return '#1e8e3e';
  if (score >= 0.50) return '#f9ab00';
  return '#9aa0a6';
}

function sourceFileUrl(filename: string, page: number | null): string {
  const base = `${BASE_URL}/api/files/${encodeURIComponent(filename)}`;
  // PDFs support #page=N fragment for browser-native page targeting
  return page !== null && filename.toLowerCase().endsWith('.pdf')
    ? `${base}#page=${page}`
    : base;
}

interface StreamingResponseProps {
  content: string;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
}

export default function StreamingResponse({
  content,
  isStreaming,
  isDone,
  error,
}: StreamingResponseProps): React.ReactElement {
  if (error) {
    return (
      <div style={{ backgroundColor: '#fce8e6', border: '1px solid #f5c6c3', borderRadius: 'var(--radius-md)', padding: '14px 16px', color: 'var(--color-red)', fontSize: 14 }}>
        {error}
      </div>
    );
  }

  if (!content && !isStreaming) {
    return (
      <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--color-gray-600)', fontSize: 14 }}>
        Ask a question above to analyse your contracts.
      </div>
    );
  }

  const { answer, sourceLines } = splitContent(content);
  const sources = isDone ? deduplicateSources(sourceLines.map(parseSource)) : [];

  // During streaming show the raw content (sources block not arrived yet);
  // once done show the clean split answer.
  const displayText = isDone ? answer : content;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Answer prose */}
      <div
        style={{
          backgroundColor: 'var(--color-white)',
          border: '1px solid var(--color-gray-300)',
          borderRadius: 'var(--radius-md)',
          padding: '16px 18px',
          boxShadow: 'var(--shadow-sm)',
          fontSize: 14,
          lineHeight: 1.8,
          color: 'var(--color-gray-900)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {displayText}
        {isStreaming && <span className="streaming-cursor" />}
      </div>

      {/* Sources — only shown when streaming is complete */}
      {isDone && sources.length > 0 && (
        <div>
          <p style={{ margin: '0 0 6px', fontSize: 11, fontWeight: 700, color: 'var(--color-gray-600)', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
            Sources
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {sources.map((s) => (
              <a
                key={s.key}
                href={sourceFileUrl(s.filename, s.page)}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  backgroundColor: 'var(--color-white)',
                  border: '1px solid var(--color-gray-300)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '7px 12px',
                  fontSize: 13,
                  textDecoration: 'none',
                  color: 'inherit',
                  cursor: 'pointer',
                  transition: 'border-color 0.12s, background-color 0.12s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-blue)';
                  e.currentTarget.style.backgroundColor = '#f0f6ff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-gray-300)';
                  e.currentTarget.style.backgroundColor = 'var(--color-white)';
                }}
              >
                {/* Relevance dot */}
                {s.relevance !== null && (
                  <span
                    title={`Match strength: ${(s.relevance * 100).toFixed(0)}%`}
                    style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: relevanceColor(s.relevance), flexShrink: 0 }}
                  />
                )}

                {/* Filename */}
                <span style={{ flex: 1, fontFamily: 'monospace', fontSize: 12, color: 'var(--color-gray-900)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.filename}>
                  {s.filename}
                </span>

                {/* Page badge */}
                {s.page !== null && (
                  <span style={{ fontSize: 11, color: 'var(--color-gray-600)', backgroundColor: 'var(--color-gray-100)', padding: '2px 7px', borderRadius: 'var(--radius-sm)', whiteSpace: 'nowrap' }}>
                    p.{s.page}
                  </span>
                )}

                {/* Relevance % */}
                {s.relevance !== null && (
                  <span style={{ fontSize: 11, color: relevanceColor(s.relevance), fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {(s.relevance * 100).toFixed(0)}%
                  </span>
                )}

                {/* Open icon */}
                <ExternalLink size={13} color="var(--color-gray-600)" style={{ flexShrink: 0 }} />
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

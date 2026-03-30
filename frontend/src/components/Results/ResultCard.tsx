/**
 * ResultCard.tsx — Placeholder for an individual search result card.
 * Reserved for a future results list view; not used in the two-panel layout.
 */

interface ResultCardProps {
  filename: string;
  excerpt: string;
  score: number;
}

export default function ResultCard({ filename, excerpt, score }: ResultCardProps): React.ReactElement {
  return (
    <div
      style={{
        border: '1px solid var(--color-gray-300)',
        borderRadius: 'var(--radius-md)',
        padding: 16,
        backgroundColor: 'var(--color-white)',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-gray-900)', fontFamily: 'monospace' }}>
          {filename}
        </span>
        <span style={{ fontSize: 12, color: 'var(--color-gray-600)' }}>
          {(score * 100).toFixed(0)}% match
        </span>
      </div>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--color-gray-600)', lineHeight: 1.6 }}>
        {excerpt}
      </p>
    </div>
  );
}

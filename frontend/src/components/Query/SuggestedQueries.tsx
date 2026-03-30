/**
 * SuggestedQueries.tsx — Dynamically generated query pill buttons.
 * Fetches 4 questions from GET /api/suggested-questions on mount so
 * they reflect the actual documents indexed in the database.
 */

import { useEffect, useState } from 'react';
import { getSuggestedQuestions } from '../../services/api';

interface SuggestedQueriesProps {
  onSelect: (query: string) => void;
  disabled: boolean;
}

export default function SuggestedQueries({ onSelect, disabled }: SuggestedQueriesProps): React.ReactElement {
  const [questions, setQuestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSuggestedQuestions()
      .then(setQuestions)
      .catch(() => setQuestions([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-gray-600)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.6px' }}>
          Suggested questions
        </p>
        <p style={{ fontSize: 13, color: 'var(--color-gray-600)' }}>Loading…</p>
      </div>
    );
  }

  if (questions.length === 0) return <></>;

  return (
    <div>
      <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-gray-600)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.6px' }}>
        Suggested questions
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {questions.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            disabled={disabled}
            style={{
              border: '1px solid var(--color-navy)',
              borderRadius: 20,
              padding: '5px 14px',
              fontSize: 13,
              cursor: disabled ? 'not-allowed' : 'pointer',
              backgroundColor: 'transparent',
              color: disabled ? 'var(--color-gray-600)' : 'var(--color-navy)',
              borderColor: disabled ? 'var(--color-gray-300)' : 'var(--color-navy)',
              transition: 'background-color 0.15s, color 0.15s',
              opacity: disabled ? 0.6 : 1,
            }}
            onMouseEnter={(e) => {
              if (!disabled) {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--color-navy)';
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-white)';
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
              (e.currentTarget as HTMLButtonElement).style.color = disabled ? 'var(--color-gray-600)' : 'var(--color-navy)';
            }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

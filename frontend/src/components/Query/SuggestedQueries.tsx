/**
 * SuggestedQueries.tsx — Pre-built query pill buttons for common legal checks.
 * Clicking a pill fills the query input and immediately submits.
 */

interface SuggestedQueriesProps {
  onSelect: (query: string) => void;
  disabled: boolean;
}

const SUGGESTIONS = [
  "Which contracts don't have a GDPR clause?",
  'Find contracts where company name needs updating',
  'Show contracts with termination clauses',
  'Which contracts are from 2022?',
];

export default function SuggestedQueries({ onSelect, disabled }: SuggestedQueriesProps): React.ReactElement {
  return (
    <div>
      <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-gray-600)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Suggested questions
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {SUGGESTIONS.map((q) => (
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

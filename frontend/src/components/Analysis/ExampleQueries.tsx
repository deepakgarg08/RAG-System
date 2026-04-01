/**
 * ExampleQueries.tsx — Static example query chips for modes 1 and 2.
 * Shows quick-fill buttons with mode-relevant example questions.
 */

interface ExampleQueriesProps {
  questions: string[];
  onSelect: (q: string) => void;
  disabled: boolean;
}

export default function ExampleQueries({ questions, onSelect, disabled }: ExampleQueriesProps): React.ReactElement {
  if (questions.length === 0) return <></>;

  return (
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
        Example questions
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
        {questions.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            disabled={disabled}
            style={{
              border: '1px solid var(--color-blue)',
              borderRadius: 20,
              padding: '5px 13px',
              fontSize: 12,
              cursor: disabled ? 'not-allowed' : 'pointer',
              backgroundColor: 'transparent',
              color: disabled ? 'var(--color-gray-600)' : 'var(--color-blue)',
              borderColor: disabled ? 'var(--color-gray-300)' : 'var(--color-blue)',
              opacity: disabled ? 0.6 : 1,
              transition: 'background-color 0.15s, color 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!disabled) {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--color-blue)';
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-white)';
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
              (e.currentTarget as HTMLButtonElement).style.color = disabled
                ? 'var(--color-gray-600)'
                : 'var(--color-blue)';
            }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

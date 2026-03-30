/**
 * ContractList.tsx — Placeholder for a browsable contract list view.
 * Reserved for a future feature; not used in the two-panel layout.
 */

interface ContractItem {
  filename: string;
  language: string;
  chunksCreated: number;
}

interface ContractListProps {
  contracts: ContractItem[];
}

export default function ContractList({ contracts }: ContractListProps): React.ReactElement {
  if (contracts.length === 0) {
    return <p style={{ fontSize: 13, color: 'var(--color-gray-600)' }}>No contracts loaded.</p>;
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {contracts.map((c) => (
        <li
          key={c.filename}
          style={{
            padding: '8px 0',
            borderBottom: '1px solid var(--color-gray-100)',
            fontSize: 13,
            color: 'var(--color-gray-900)',
          }}
        >
          {c.filename} — {c.language.toUpperCase()} — {c.chunksCreated} chunks
        </li>
      ))}
    </ul>
  );
}

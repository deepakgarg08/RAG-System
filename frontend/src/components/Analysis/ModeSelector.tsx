/**
 * ModeSelector.tsx — Three-tab selector for the analysis mode.
 *
 * MODE 1 "Analyze Document"  — Q&A on a single uploaded doc (no DB write)
 * MODE 2 "Compare Document"  — Uploaded doc vs stored contracts (DB read-only)
 * MODE 3 "Search Contracts"  — Cross-database query (no file upload needed)
 */

import { Database, FileText, GitCompare } from 'lucide-react';
import type { AnalysisMode } from '../../types';

interface ModeSelectorProps {
  mode: AnalysisMode;
  onChange: (mode: AnalysisMode) => void;
}

interface TabDef {
  id: AnalysisMode;
  label: string;
  description: string;
  Icon: React.ElementType;
}

const TABS: TabDef[] = [
  {
    id: 'search',
    label: 'Search Contracts',
    description: 'Query across all indexed contracts',
    Icon: Database,
  },
  {
    id: 'analyze',
    label: 'Analyze Document',
    description: 'Q&A on a single uploaded document',
    Icon: FileText,
  },
  {
    id: 'compare',
    label: 'Compare Document',
    description: 'Compare an uploaded doc with indexed contracts',
    Icon: GitCompare,
  },
];

export default function ModeSelector({ mode, onChange }: ModeSelectorProps): React.ReactElement {
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
        Analysis Mode
      </p>
      <div
        style={{
          display: 'flex',
          gap: 6,
          backgroundColor: 'var(--color-gray-100)',
          borderRadius: 'var(--radius-md)',
          padding: 4,
        }}
      >
        {TABS.map(({ id, label, description, Icon }) => {
          const active = mode === id;
          return (
            <button
              key={id}
              title={description}
              onClick={() => onChange(id)}
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
                padding: '7px 8px',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: active ? 'var(--color-white)' : 'transparent',
                color: active ? 'var(--color-navy)' : 'var(--color-gray-600)',
                fontWeight: active ? 600 : 400,
                fontSize: 13,
                cursor: 'pointer',
                transition: 'background-color 0.15s, color 0.15s',
                boxShadow: active ? 'var(--shadow-sm)' : 'none',
                whiteSpace: 'nowrap',
              }}
            >
              <Icon size={14} style={{ flexShrink: 0 }} />
              <span>{label}</span>
            </button>
          );
        })}
      </div>
      {/* Mode description hint */}
      <p
        style={{
          margin: '6px 0 0',
          fontSize: 12,
          color: 'var(--color-gray-600)',
        }}
      >
        {TABS.find((t) => t.id === mode)?.description}
      </p>
    </div>
  );
}

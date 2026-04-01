/**
 * AppLayout.tsx — Root layout: fixed navy header, two-panel body, footer.
 * Health state is owned by App.tsx and passed in as props so other
 * components (e.g. QueryInput) can react to the live document count.
 */

import type { HealthResponse } from '../../types';
import StatusDot from '../common/StatusDot';

interface AppLayoutProps {
  uploadPanel: React.ReactNode;
  queryPanel: React.ReactNode;
  health: HealthResponse | null;
  connected: boolean;
  /** True after the first health check has resolved (success or failure). */
  connectionChecked: boolean;
}

export default function AppLayout({ uploadPanel, queryPanel, health, connected, connectionChecked }: AppLayoutProps): React.ReactElement {

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: 'var(--color-gray-50)' }}>
      {/* Header */}
      <header
        style={{
          backgroundColor: 'var(--color-navy)',
          color: 'var(--color-white)',
          padding: '0 24px',
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.3px' }}>
            Riverty Contract Review
          </span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              backgroundColor: 'rgba(255,255,255,0.12)',
              padding: '2px 8px',
              borderRadius: 'var(--radius-sm)',
              letterSpacing: '0.5px',
              textTransform: 'uppercase',
            }}
          >
            Demo
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
          <StatusDot connected={connected} />
          {!connectionChecked ? (
            // Initial state — first health check still in flight
            <span style={{ opacity: 0.6 }}>Connecting…</span>
          ) : connected && health ? (
            // Connected — show live document count
            <span style={{ opacity: 0.85 }}>
              {health.document_count} document{health.document_count !== 1 ? 's' : ''} indexed
            </span>
          ) : (
            // Checked but backend unreachable
            <span style={{ opacity: 0.6 }}>Disconnected</span>
          )}
        </div>
      </header>

      {/* Two-panel body */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          gap: 0,
          overflow: 'hidden',
        }}
      >
        {/* Left panel — fixed 260px sidebar */}
        <div
          style={{
            width: 260,
            flexShrink: 0,
            borderRight: '1px solid var(--color-gray-300)',
            overflowY: 'auto',
            backgroundColor: 'var(--color-white)',
            padding: '20px 16px',
          }}
        >
          {uploadPanel}
        </div>

        {/* Right panel — 60% */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: 24,
            backgroundColor: 'var(--color-gray-50)',
          }}
        >
          {queryPanel}
        </div>
      </main>

      {/* Footer */}
      <footer
        style={{
          backgroundColor: 'var(--color-white)',
          borderTop: '1px solid var(--color-gray-300)',
          padding: '8px 24px',
          fontSize: 12,
          color: 'var(--color-gray-600)',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          flexShrink: 0,
        }}
      >
        <span>
          Demo mode: ChromaDB local + BAAI/bge-m3 embeddings
        </span>
        <span style={{ color: 'var(--color-gray-300)' }}>|</span>
        <span>Production swap → Azure AI Search + Azure OpenAI</span>
      </footer>
    </div>
  );
}

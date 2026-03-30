/**
 * AppLayout.tsx — Root layout: fixed navy header, two-panel body, footer.
 * Polls GET /health every 30 seconds to keep the document count and
 * connection status dot up to date.
 */

import { useEffect, useState } from 'react';
import { getHealth } from '../../services/api';
import type { HealthResponse } from '../../types';
import StatusDot from '../common/StatusDot';

interface AppLayoutProps {
  uploadPanel: React.ReactNode;
  queryPanel: React.ReactNode;
}

export default function AppLayout({ uploadPanel, queryPanel }: AppLayoutProps): React.ReactElement {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [connected, setConnected] = useState(false);

  async function fetchHealth(): Promise<void> {
    try {
      const data = await getHealth();
      setHealth(data);
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }

  useEffect(() => {
    void fetchHealth();
    const interval = setInterval(() => void fetchHealth(), 30_000);
    return () => clearInterval(interval);
  }, []);

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
          {connected && health ? (
            <span style={{ opacity: 0.85 }}>
              {health.document_count} document{health.document_count !== 1 ? 's' : ''} indexed
            </span>
          ) : (
            <span style={{ opacity: 0.6 }}>Connecting…</span>
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
        {/* Left panel — 40% */}
        <div
          style={{
            width: '40%',
            minWidth: 320,
            borderRight: '1px solid var(--color-gray-300)',
            overflowY: 'auto',
            backgroundColor: 'var(--color-white)',
            padding: 24,
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

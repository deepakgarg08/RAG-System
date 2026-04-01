/**
 * CompliancePanel.tsx — Structured compliance result display.
 *
 * Renders the structured JSON response from POST /api/compliance:
 *   - compliant / not compliant banner
 *   - list of specific violations (if any)
 *   - plain-language explanation
 */

import { CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import type { ComplianceResult } from '../../types';

interface CompliancePanelProps {
  result: ComplianceResult;
  filename: string;
}

export default function CompliancePanel({ result, filename }: CompliancePanelProps): React.ReactElement {
  const { compliant, violations, explanation } = result;

  return (
    <div
      style={{
        border: `1px solid ${compliant ? '#c6e8d1' : '#f5c6c3'}`,
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      {/* Status banner */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 16px',
          backgroundColor: compliant ? '#e6f4ea' : '#fce8e6',
        }}
      >
        {compliant ? (
          <CheckCircle size={20} color="var(--color-green)" style={{ flexShrink: 0 }} />
        ) : (
          <XCircle size={20} color="var(--color-red)" style={{ flexShrink: 0 }} />
        )}
        <div>
          <p style={{ margin: 0, fontWeight: 700, fontSize: 14, color: compliant ? 'var(--color-green)' : 'var(--color-red)' }}>
            {compliant ? 'Compliant' : 'Not Compliant'}
          </p>
          <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--color-gray-600)' }}>
            {filename}
          </p>
        </div>
      </div>

      <div style={{ padding: '14px 16px', backgroundColor: 'var(--color-white)', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Violations */}
        {violations.length > 0 && (
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
              Violations ({violations.length})
            </p>
            <ul style={{ margin: 0, padding: '0 0 0 18px', display: 'flex', flexDirection: 'column', gap: 5 }}>
              {violations.map((v, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                  <AlertTriangle
                    size={13}
                    color="#f9ab00"
                    style={{ flexShrink: 0, marginTop: 2 }}
                  />
                  <span style={{ fontSize: 13, color: 'var(--color-gray-900)', lineHeight: 1.5 }}>{v}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Explanation */}
        {explanation && (
          <div>
            <p
              style={{
                margin: '0 0 6px',
                fontSize: 11,
                fontWeight: 700,
                color: 'var(--color-gray-600)',
                textTransform: 'uppercase',
                letterSpacing: '0.6px',
              }}
            >
              Assessment
            </p>
            <p
              style={{
                margin: 0,
                fontSize: 13,
                color: 'var(--color-gray-900)',
                lineHeight: 1.7,
              }}
            >
              {explanation}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

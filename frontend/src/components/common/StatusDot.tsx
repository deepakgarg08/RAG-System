/**
 * StatusDot.tsx — Small coloured indicator dot used in the header health display.
 */

interface StatusDotProps {
  connected: boolean;
}

export default function StatusDot({ connected }: StatusDotProps): React.ReactElement {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: connected ? 'var(--color-green)' : 'var(--color-red)',
        boxShadow: connected
          ? '0 0 0 2px rgba(30,142,62,0.25)'
          : '0 0 0 2px rgba(217,48,37,0.25)',
      }}
      title={connected ? 'Backend connected' : 'Backend unreachable'}
    />
  );
}

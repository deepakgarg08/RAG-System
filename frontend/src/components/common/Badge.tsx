/**
 * Badge.tsx — Generic coloured label badge used across the UI.
 */

interface BadgeProps {
  label: string;
  variant: 'pdf' | 'jpeg' | 'success' | 'error' | 'language' | 'neutral';
}

const variantStyles: Record<BadgeProps['variant'], React.CSSProperties> = {
  pdf: { backgroundColor: '#e8f0fe', color: '#1a73e8', border: '1px solid #c5d8fb' },
  jpeg: { backgroundColor: '#fce8e6', color: '#d93025', border: '1px solid #f5c6c3' },
  success: { backgroundColor: '#e6f4ea', color: '#1e8e3e', border: '1px solid #b7dfbf' },
  error: { backgroundColor: '#fce8e6', color: '#d93025', border: '1px solid #f5c6c3' },
  language: { backgroundColor: '#f1f3f4', color: '#5f6368', border: '1px solid #dadce0' },
  neutral: { backgroundColor: '#f1f3f4', color: '#5f6368', border: '1px solid #dadce0' },
};

export default function Badge({ label, variant }: BadgeProps): React.ReactElement {
  return (
    <span
      style={{
        ...variantStyles[variant],
        padding: '2px 8px',
        borderRadius: 'var(--radius-sm)',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.3px',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  );
}

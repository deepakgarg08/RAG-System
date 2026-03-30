/**
 * LoadingSpinner.tsx — Small inline spinner shown during file upload.
 */

export default function LoadingSpinner(): React.ReactElement {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 16,
        height: 16,
        border: '2px solid rgba(255,255,255,0.3)',
        borderTopColor: '#fff',
        borderRadius: '50%',
        animation: 'spin 0.7s linear infinite',
        verticalAlign: 'middle',
      }}
    />
  );
}

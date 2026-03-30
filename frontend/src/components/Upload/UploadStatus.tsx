/**
 * UploadStatus.tsx — List of uploaded contracts with type, language, and chunk badges.
 */

import { CheckCircle, XCircle } from 'lucide-react';
import type { UploadedFile } from '../../types';
import Badge from '../common/Badge';

interface UploadStatusProps {
  files: UploadedFile[];
  error: string | null;
  onClearError: () => void;
}

function fileTypeBadge(fileType: string): React.ReactElement {
  const isJpeg = fileType === 'jpeg' || fileType === 'jpg' || fileType === 'png';
  return <Badge label={fileType.toUpperCase()} variant={isJpeg ? 'jpeg' : 'pdf'} />;
}

function truncate(name: string, max = 28): string {
  return name.length > max ? `…${name.slice(-max + 1)}` : name;
}

export default function UploadStatus({ files, error, onClearError }: UploadStatusProps): React.ReactElement {
  return (
    <div>
      {error && (
        <div
          style={{
            backgroundColor: '#fce8e6',
            border: '1px solid #f5c6c3',
            borderRadius: 'var(--radius-sm)',
            padding: '8px 12px',
            marginBottom: 12,
            fontSize: 13,
            color: 'var(--color-red)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span>{error}</span>
          <button
            onClick={onClearError}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-red)', fontWeight: 700, fontSize: 14 }}
          >
            ×
          </button>
        </div>
      )}

      {files.length === 0 ? (
        <p style={{ fontSize: 13, color: 'var(--color-gray-600)', marginTop: 16 }}>
          No contracts uploaded yet.
        </p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: '16px 0 0' }}>
          {files.map((f) => (
            <li
              key={f.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 0',
                borderBottom: '1px solid var(--color-gray-100)',
                flexWrap: 'wrap',
              }}
            >
              {f.status === 'success' ? (
                <CheckCircle size={16} color="var(--color-green)" style={{ flexShrink: 0 }} />
              ) : (
                <XCircle size={16} color="var(--color-red)" style={{ flexShrink: 0 }} />
              )}
              <span
                style={{ fontSize: 13, color: 'var(--color-gray-900)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                title={f.filename}
              >
                {truncate(f.filename)}
              </span>
              {fileTypeBadge(f.fileType)}
              <Badge label={f.language.toUpperCase()} variant="language" />
              <Badge label={`${f.chunksCreated} chunks`} variant="neutral" />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

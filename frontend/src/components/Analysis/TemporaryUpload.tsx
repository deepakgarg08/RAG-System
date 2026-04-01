/**
 * TemporaryUpload.tsx — File drop zone for temporary document analysis.
 *
 * Files uploaded here are processed in-memory and NEVER stored in the
 * vector database. This is made visually explicit with a "Temporary" badge
 * and a clear label to avoid user confusion with the persistent upload.
 */

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { FileText, X } from 'lucide-react';
import LoadingSpinner from '../common/LoadingSpinner';

interface TemporaryUploadProps {
  file: File | null;
  onFileSelect: (file: File | null) => void;
  isProcessing: boolean;
}

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
};

export default function TemporaryUpload({
  file,
  onFileSelect,
  isProcessing,
}: TemporaryUploadProps): React.ReactElement {
  const [typeError, setTypeError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: { file: File }[]) => {
      setTypeError(null);
      if (rejectedFiles.length > 0) {
        setTypeError('Only PDF, JPG, and PNG files are supported.');
        return;
      }
      if (acceptedFiles.length > 0) onFileSelect(acceptedFiles[0]);
    },
    [onFileSelect],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    multiple: false,
    disabled: isProcessing,
  });

  // File selected — show it with a clear badge and remove button
  if (file) {
    return (
      <div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '10px 12px',
            border: '1px solid var(--color-gray-300)',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-white)',
          }}
        >
          {isProcessing ? (
            <LoadingSpinner />
          ) : (
            <FileText size={16} color="var(--color-blue)" style={{ flexShrink: 0 }} />
          )}
          <span
            style={{
              flex: 1,
              fontSize: 13,
              color: 'var(--color-gray-900)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={file.name}
          >
            {file.name}
          </span>
          {/* "Temporary" badge */}
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              backgroundColor: '#e8f4fd',
              color: '#0d7acd',
              border: '1px solid #b3d9f5',
              padding: '2px 7px',
              borderRadius: 10,
              whiteSpace: 'nowrap',
              letterSpacing: '0.3px',
              textTransform: 'uppercase',
            }}
          >
            Temporary
          </span>
          {!isProcessing && (
            <button
              onClick={() => onFileSelect(null)}
              title="Remove file"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 2,
                color: 'var(--color-gray-600)',
                display: 'flex',
                alignItems: 'center',
                flexShrink: 0,
              }}
            >
              <X size={15} />
            </button>
          )}
        </div>
        <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--color-gray-600)' }}>
          Analyse only — not stored in the knowledge base
        </p>
      </div>
    );
  }

  // No file yet — show drop zone
  return (
    <div>
      <div
        {...getRootProps()}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
          padding: '20px 16px',
          border: `1.5px dashed ${isDragActive ? 'var(--color-blue)' : 'var(--color-gray-300)'}`,
          borderRadius: 'var(--radius-md)',
          backgroundColor: isDragActive ? '#e8f0fe' : 'var(--color-gray-50)',
          cursor: 'pointer',
          transition: 'border-color 0.15s, background-color 0.15s',
        }}
      >
        <input {...getInputProps()} />
        <FileText size={22} color={isDragActive ? 'var(--color-blue)' : 'var(--color-gray-600)'} />
        <span style={{ fontSize: 13, color: 'var(--color-gray-600)', textAlign: 'center' }}>
          {isDragActive ? 'Drop to analyse' : 'Upload a contract to analyse (PDF / JPG / PNG)'}
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: '#0d7acd',
            backgroundColor: '#e8f4fd',
            padding: '2px 8px',
            borderRadius: 10,
            textTransform: 'uppercase',
            letterSpacing: '0.3px',
          }}
        >
          Temporary — not stored in the knowledge base
        </span>
      </div>
      {typeError && (
        <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--color-red)' }}>{typeError}</p>
      )}
    </div>
  );
}

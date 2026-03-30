/**
 * FileUpload.tsx — Compact single-row upload trigger.
 * Uses react-dropzone but styled as a small button bar rather than a large zone.
 */

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud } from 'lucide-react';
import LoadingSpinner from '../common/LoadingSpinner';

interface FileUploadProps {
  onUpload: (file: File) => Promise<void>;
  isUploading: boolean;
}

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
};

export default function FileUpload({ onUpload, isUploading }: FileUploadProps): React.ReactElement {
  const [typeError, setTypeError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: { file: File }[]) => {
      setTypeError(null);
      if (rejectedFiles.length > 0) {
        setTypeError('Only PDF, JPG, and PNG files are supported.');
        return;
      }
      if (acceptedFiles.length > 0) void onUpload(acceptedFiles[0]);
    },
    [onUpload],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    multiple: false,
    disabled: isUploading,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          border: `1px dashed ${isDragActive ? 'var(--color-blue)' : 'var(--color-gray-300)'}`,
          borderRadius: 'var(--radius-md)',
          backgroundColor: isDragActive ? '#e8f0fe' : 'var(--color-gray-50)',
          cursor: isUploading ? 'not-allowed' : 'pointer',
          transition: 'border-color 0.15s, background-color 0.15s',
          opacity: isUploading ? 0.7 : 1,
        }}
      >
        <input {...getInputProps()} />
        {isUploading ? (
          <LoadingSpinner />
        ) : (
          <UploadCloud size={16} color="var(--color-gray-600)" style={{ flexShrink: 0 }} />
        )}
        <span style={{ fontSize: 13, color: 'var(--color-gray-600)' }}>
          {isUploading ? 'Processing…' : isDragActive ? 'Drop to upload' : 'Upload contract (PDF / JPG / PNG)'}
        </span>
      </div>
      {typeError && (
        <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--color-red)' }}>{typeError}</p>
      )}
    </div>
  );
}

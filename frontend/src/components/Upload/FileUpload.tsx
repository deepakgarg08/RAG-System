/**
 * FileUpload.tsx — Drag-and-drop contract upload zone.
 * Accepts PDF, JPG, JPEG, PNG. Delegates to the useFileUpload hook.
 */

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload } from 'lucide-react';
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
        setTypeError('Only PDF, JPG, and PNG contracts are supported.');
        return;
      }
      if (acceptedFiles.length > 0) {
        void onUpload(acceptedFiles[0]);
      }
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
          border: `2px dashed ${isDragActive ? 'var(--color-blue)' : 'var(--color-gray-300)'}`,
          borderRadius: 'var(--radius-md)',
          padding: '32px 16px',
          textAlign: 'center',
          cursor: isUploading ? 'not-allowed' : 'pointer',
          backgroundColor: isDragActive ? '#e8f0fe' : 'var(--color-gray-50)',
          transition: 'border-color 0.15s, background-color 0.15s',
          opacity: isUploading ? 0.7 : 1,
        }}
      >
        <input {...getInputProps()} />
        <div style={{ marginBottom: 10, color: 'var(--color-gray-600)' }}>
          {isUploading ? (
            <LoadingSpinner />
          ) : (
            <Upload size={28} color="var(--color-gray-600)" />
          )}
        </div>
        <p style={{ margin: '0 0 4px', fontWeight: 600, fontSize: 14, color: 'var(--color-gray-900)' }}>
          {isUploading ? 'Processing…' : isDragActive ? 'Drop to upload' : 'Drop contracts here or click to browse'}
        </p>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--color-gray-600)' }}>
          PDF, JPG, PNG — one file at a time
        </p>
      </div>

      {typeError && (
        <p style={{ margin: '8px 0 0', fontSize: 13, color: 'var(--color-red)' }}>
          {typeError}
        </p>
      )}
    </div>
  );
}

/**
 * useFileUpload.ts — Manages file upload state and the upload flow.
 * Calls POST /api/ingest and maintains the list of successfully ingested contracts.
 */

import { useState } from 'react';
import { uploadContract } from '../services/api';
import type { UploadedFile } from '../types';

interface UseFileUploadReturn {
  uploadedFiles: UploadedFile[];
  isUploading: boolean;
  error: string | null;
  handleUpload: (file: File) => Promise<void>;
  clearError: () => void;
}

export function useFileUpload(): UseFileUploadReturn {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(file: File): Promise<void> {
    setIsUploading(true);
    setError(null);

    try {
      const result = await uploadContract(file);

      const uploaded: UploadedFile = {
        id: `${file.name}-${Date.now()}`,
        filename: result.filename,
        fileType: result.file_type,
        language: result.language,
        chunksCreated: result.chunks_created,
        uploadedAt: new Date(),
        status: result.status,
      };

      setUploadedFiles((prev) => [uploaded, ...prev]);

      if (result.status === 'failed') {
        setError(result.error ?? `Ingestion failed for ${result.filename}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  }

  function clearError(): void {
    setError(null);
  }

  return { uploadedFiles, isUploading, error, handleUpload, clearError };
}

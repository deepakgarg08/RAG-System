/**
 * QueryInput.tsx — Text area + submit button for contract questions.
 * Supports Ctrl/Cmd+Enter to submit. Warns when no documents are uploaded.
 */

import { useRef } from 'react';
import { Send } from 'lucide-react';

interface QueryInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isStreaming: boolean;
  hasDocuments: boolean;
}

export default function QueryInput({
  value,
  onChange,
  onSubmit,
  isStreaming,
  hasDocuments,
}: QueryInputProps): React.ReactElement {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const canSubmit = !isStreaming && hasDocuments && value.trim().length >= 3;

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (canSubmit) onSubmit();
    }
  }

  return (
    <div>
      {!hasDocuments && (
        <div
          style={{
            backgroundColor: '#fef9e7',
            border: '1px solid #f9e4a0',
            borderRadius: 'var(--radius-sm)',
            padding: '7px 12px',
            fontSize: 13,
            color: '#856404',
            marginBottom: 10,
          }}
        >
          Upload contracts first before asking questions.
        </div>
      )}

      <div style={{ position: 'relative' }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your contracts…"
          rows={3}
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '10px 44px 10px 12px',
            border: '1px solid var(--color-gray-300)',
            borderRadius: 'var(--radius-md)',
            fontSize: 14,
            color: 'var(--color-gray-900)',
            resize: 'vertical',
            fontFamily: 'inherit',
            outline: 'none',
            backgroundColor: 'var(--color-white)',
          }}
          disabled={isStreaming}
        />
        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          title="Submit (Ctrl+Enter)"
          style={{
            position: 'absolute',
            right: 10,
            bottom: 10,
            width: 32,
            height: 32,
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            backgroundColor: canSubmit ? 'var(--color-navy)' : 'var(--color-gray-300)',
            color: 'var(--color-white)',
            cursor: canSubmit ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background-color 0.15s',
          }}
        >
          <Send size={15} />
        </button>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--color-gray-600)' }}>
          Ctrl+Enter to submit
        </span>
        {value.length > 200 && (
          <span style={{ fontSize: 11, color: 'var(--color-gray-600)' }}>
            {value.length} characters
          </span>
        )}
      </div>
    </div>
  );
}

import { useState } from 'react';
import { uploadFiles } from '../../../api/files';

export function DataPage() {
  const [savedFiles, setSavedFiles] = useState<string[]>([]);
  const [message, setMessage] = useState('');

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setMessage('Uploading...');
    try {
      const result = await uploadFiles(files);
      setSavedFiles(result.saved_files);
      setMessage(`Uploaded ${result.saved_files.length} file(s)`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    }
  }

  return (
    <section className="card">
    <h2>Upload files or folders</h2>
    <p className="muted">Files are stored by the API under backend/data/uploads/&lt;user-id&gt;/.</p>
    <div className="row">
      <label className="button-like">
      Upload files
      <input hidden multiple type="file" onChange={(event) => handleUpload(event.target.files)} />
      </label>
      <label className="button-like">
      Upload directory
      <input
          hidden
          multiple
          type="file"
          // Chromium/Edge support this. React's TS types do not know the attribute.
          {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
          onChange={(event) => handleUpload(event.target.files)}
      />
      </label>
    </div>
    {message && <p className="message">{message}</p>}
    {savedFiles.length > 0 && (
      <ul className="file-list">
      {savedFiles.map((file) => (
        <li key={file}>{file}</li>
      ))}
      </ul>
    )}
    </section>
  );
}
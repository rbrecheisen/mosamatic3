import { useEffect, useRef, useState } from 'react';
import { DatasetSummary, listDatasets, uploadDataset } from '../../../api/files';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

export function DataPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const directoryInputRef = useRef<HTMLInputElement | null>(null);
  const pendingDatasetNameRef = useRef<string>('');

  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function refreshDatasets() {
    const result = await listDatasets();
    setDatasets(result);
  }

  useEffect(() => {
    refreshDatasets().catch((error) => {
      setMessage(error instanceof Error ? error.message : 'Could not load datasets');
    });
  }, []);

  function askForDatasetName(): string | null {
    const name = window.prompt('Dataset name');
    const trimmedName = name?.trim() ?? '';

    if (!trimmedName) return null;

    const alreadyExists = datasets.some(
      (dataset) => dataset.name.toLowerCase() === trimmedName.toLowerCase(),
    );
    if (alreadyExists) {
      setMessage(`Dataset name "${trimmedName}" already exists`);
      return null;
    }

    return trimmedName;
  }

  function startUpload(kind: 'files' | 'directory') {
    const datasetName = askForDatasetName();
    if (!datasetName) return;

    pendingDatasetNameRef.current = datasetName;
    if (kind === 'files') fileInputRef.current?.click();
    else directoryInputRef.current?.click();
  }

  async function handleUpload(files: FileList | null, input: HTMLInputElement | null) {
    const datasetName = pendingDatasetNameRef.current;
    pendingDatasetNameRef.current = '';

    if (!files || files.length === 0 || !datasetName) {
      if (input) input.value = '';
      return;
    }

    setLoading(true);
    setMessage(`Uploading "${datasetName}"...`);

    try {
      await uploadDataset(datasetName, files);
      await refreshDatasets();
      setMessage(`Uploaded "${datasetName}" (${files.length} file${files.length === 1 ? '' : 's'})`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setLoading(false);
      if (input) input.value = '';
    }
  }

  return (
    <section className="card">
      <h2>Datasets</h2>
      <p className="muted">
        Each upload action creates one dataset. Directory uploads preserve relative paths.
      </p>

      <div className="row">
        <button disabled={loading} type="button" onClick={() => startUpload('files')}>
          Upload files
        </button>
        <button disabled={loading} type="button" onClick={() => startUpload('directory')}>
          Upload directory
        </button>
      </div>

      <input
        ref={fileInputRef}
        hidden
        multiple
        type="file"
        onChange={(event) => handleUpload(event.target.files, event.currentTarget)}
      />

      <input
        ref={directoryInputRef}
        hidden
        multiple
        type="file"
        {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
        onChange={(event) => handleUpload(event.target.files, event.currentTarget)}
      />

      {message && <p className="message">{message}</p>}

      {datasets.length === 0 ? (
        <p className="muted">No datasets uploaded yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Files</th>
              <th>Total size</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((dataset) => (
              <tr key={dataset.id}>
                <td>{dataset.name}</td>
                <td>{dataset.file_count}</td>
                <td>{formatBytes(dataset.total_size_bytes)}</td>
                <td>{new Date(dataset.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

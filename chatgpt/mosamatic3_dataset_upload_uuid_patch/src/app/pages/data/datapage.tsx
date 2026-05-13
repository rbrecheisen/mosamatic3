import { useEffect, useRef, useState } from 'react';
import { createDataset, Dataset, listDatasets } from '../../../api/files';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function DataPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [message, setMessage] = useState('');
  const [pendingDatasetName, setPendingDatasetName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const directoryInputRef = useRef<HTMLInputElement | null>(null);

  async function refreshDatasets() {
    setDatasets(await listDatasets());
  }

  useEffect(() => {
    refreshDatasets().catch((error) => {
      setMessage(error instanceof Error ? error.message : 'Could not load datasets');
    });
  }, []);

  function requestDatasetNameAndOpenPicker(kind: 'files' | 'directory') {
    const datasetName = window.prompt('Dataset name');
    if (!datasetName) return;

    const trimmedName = datasetName.trim();
    if (!trimmedName) {
      setMessage('Dataset name is required');
      return;
    }
    if (datasets.some((dataset) => dataset.name === trimmedName)) {
      setMessage('A dataset with this name already exists');
      return;
    }

    setPendingDatasetName(trimmedName);
    if (kind === 'files') fileInputRef.current?.click();
    else directoryInputRef.current?.click();
  }

  async function handleUpload(files: FileList | null, input: HTMLInputElement) {
    if (!files || files.length === 0 || !pendingDatasetName) {
      input.value = '';
      setPendingDatasetName(null);
      return;
    }

    setMessage('Uploading...');
    try {
      const dataset = await createDataset(pendingDatasetName, files);
      setDatasets((current) => [dataset, ...current]);
      setMessage(`Uploaded dataset “${dataset.name}” with ${dataset.file_count} file(s)`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      input.value = '';
      setPendingDatasetName(null);
    }
  }

  return (
    <section className="card">
      <h2>Datasets</h2>
      <p className="muted">
        Each upload action is stored as one named dataset under backend/data/uploads/&lt;user-id&gt;/&lt;dataset-id&gt;/.
      </p>

      <div className="row">
        <button type="button" onClick={() => requestDatasetNameAndOpenPicker('files')}>
          Upload files
        </button>
        <button type="button" onClick={() => requestDatasetNameAndOpenPicker('directory')}>
          Upload directory
        </button>

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
          // Chromium/Edge support this. React's TS types do not know the attribute.
          {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
          onChange={(event) => handleUpload(event.target.files, event.currentTarget)}
        />
      </div>

      {message && <p className="message">{message}</p>}

      <h3>Uploaded datasets</h3>
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

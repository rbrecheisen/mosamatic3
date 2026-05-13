import { ChangeEvent, useEffect, useRef, useState } from 'react';
import { DatasetSummary, listDatasets, uploadDataset, deleteDataset } from '../../../api/files';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, index);

  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function DataPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const directoryInputRef = useRef<HTMLInputElement | null>(null);

  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);

  async function refreshDatasets() {
    const result = await listDatasets();
    setDatasets(result);
  }

  useEffect(() => {
    refreshDatasets().catch((error) => {
      console.error(error);
      setMessage(error instanceof Error ? error.message : 'Could not load datasets');
    });
  }, []);

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function openDirectoryPicker() {
    directoryInputRef.current?.click();
  }

  async function handleFilesSelected(event: ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.target.files ?? []);

    // Reset input so selecting the same file(s) again still triggers onChange.
    event.target.value = '';

    if (selectedFiles.length === 0) {
      return;
    }

    const datasetName = window.prompt('Dataset name');

    if (!datasetName?.trim()) {
      setMessage('Upload cancelled: no dataset name entered.');
      return;
    }

    const normalizedName = datasetName.trim();

    const duplicate = datasets.some(
      (dataset) => dataset.name.toLowerCase() === normalizedName.toLowerCase(),
    );

    if (duplicate) {
      setMessage(`A dataset named "${normalizedName}" already exists.`);
      return;
    }

    setUploading(true);
    setMessage('Uploading...');

    try {
      await uploadDataset(normalizedName, selectedFiles);
      await refreshDatasets();

      setMessage(
        `Uploaded dataset "${normalizedName}"`,
      );
    } catch (error) {
      console.error(error);
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteDataset(dataset: DatasetSummary) {
    const confirmed = window.confirm(
      `Delete dataset "${dataset.name}" and all ${dataset.file_count} file(s)?`,
    );

    if (!confirmed) return;

    setMessage(`Deleting dataset "${dataset.name}"...`);

    try {
      await deleteDataset(dataset.id);
      setDatasets((current) => current.filter((item) => item.id !== dataset.id));
      setMessage(`Deleted dataset "${dataset.name}".`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Delete failed');
    }
  }

  return (
    <section className="card">
      <h2>Upload files or folders</h2>

      <p className="muted">
        Each upload is stored as one dataset under backend/data/uploads/&lt;user-id&gt;/&lt;dataset-id&gt;/.
      </p>

      <div className="row">
        <button
          type="button"
          className="button-like"
          onClick={openFilePicker}
          disabled={uploading}
        >
          Upload files
        </button>

        <button
          type="button"
          className="button-like"
          onClick={openDirectoryPicker}
          disabled={uploading}
        >
          Upload directory
        </button>

        <input
          ref={fileInputRef}
          hidden
          multiple
          type="file"
          onChange={handleFilesSelected}
        />

        <input
          ref={directoryInputRef}
          hidden
          multiple
          type="file"
          {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
          onChange={handleFilesSelected}
        />
      </div>

      {message && <p className="message">{message}</p>}

      <h3>Datasets</h3>

      {datasets.length === 0 ? (
        <p className="muted">No datasets uploaded yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Files</th>
              <th>Total size</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((dataset) => (
              <tr key={dataset.id}>
                <td>{dataset.name}</td>
                <td>{dataset.file_count}</td>
                <td>{formatBytes(dataset.total_size_bytes)}</td>
                <td>{new Date(dataset.created_at).toLocaleString()}</td>
                <td>
                  <button type='button' onClick={() => handleDeleteDataset(dataset)}>delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
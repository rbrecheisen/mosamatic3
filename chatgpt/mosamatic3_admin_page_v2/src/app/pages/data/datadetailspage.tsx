import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Dataset, getDataset } from '../../../api/files';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, index);

  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function DataDetailsPage() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!datasetId) {
      setMessage('No dataset id provided.');
      setLoading(false);
      return;
    }

    getDataset(datasetId)
      .then(setDataset)
      .catch((error) => {
        console.error(error);
        setMessage(error instanceof Error ? error.message : 'Could not load dataset');
      })
      .finally(() => setLoading(false));
  }, [datasetId]);

  if (loading) {
    return (
      <section className="card">
        <p className="muted">Loading dataset...</p>
      </section>
    );
  }

  if (message || !dataset) {
    return (
      <section className="card">
        <p className="message">{message || 'Dataset not found.'}</p>
        <Link className="button-like" to="/data">Back to datasets</Link>
      </section>
    );
  }

  const totalSizeBytes = dataset.files.reduce((sum, file) => sum + file.size_bytes, 0);

  return (
    <section className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div>
          <h2>{dataset.name}</h2>
          <p className="muted">
            {dataset.files.length} file(s), {formatBytes(totalSizeBytes)} total, created{' '}
            {new Date(dataset.created_at).toLocaleString()}
          </p>
        </div>

        <Link className="button-like secondary" to="/data">
          Back to datasets
        </Link>
      </div>

      {dataset.files.length === 0 ? (
        <p className="muted">This dataset contains no files.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Relative path</th>
              <th>Size</th>
              <th>Size in KB</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {dataset.files.map((file) => (
              <tr key={file.id}>
                <td>{file.relative_path}</td>
                <td>{formatBytes(file.size_bytes)}</td>
                <td>{(file.size_bytes / 1024).toFixed(1)} KB</td>
                <td>{new Date(file.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
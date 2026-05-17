import { useEffect, useState } from 'react';
import {
  AdminDataset,
  AdminSummary,
  AdminUser,
  getAdminSummary,
  listAdminDatasets,
  listAdminUsers,
} from '../../../api/admin';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, index);

  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function AdminPage() {
  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [datasets, setDatasets] = useState<AdminDataset[]>([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getAdminSummary(), listAdminUsers(), listAdminDatasets()])
      .then(([summaryResult, usersResult, datasetsResult]) => {
        setSummary(summaryResult);
        setUsers(usersResult);
        setDatasets(datasetsResult);
      })
      .catch((error) => {
        console.error(error);
        setMessage(error instanceof Error ? error.message : 'Could not load admin data');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <section className="card">
        <p className="muted">Loading admin page...</p>
      </section>
    );
  }

  return (
    <section className="card">
      <p className="eyebrow">Admin</p>
      <h2>Application administration</h2>

      {message && <p className="message">{message}</p>}

      {summary && (
        <div className="grid">
          <div className="card">
            <p className="muted">Users</p>
            <h3>{summary.user_count}</h3>
          </div>
          <div className="card">
            <p className="muted">Datasets</p>
            <h3>{summary.dataset_count}</h3>
          </div>
          <div className="card">
            <p className="muted">Dataset files</p>
            <h3>{summary.dataset_file_count}</h3>
          </div>
        </div>
      )}

      <h3>Users</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>Username/email</th>
            <th>Active</th>
            <th>Admin</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.email}</td>
              <td>{user.is_active ? 'yes' : 'no'}</td>
              <td>{user.is_admin ? 'yes' : 'no'}</td>
              <td>{new Date(user.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Datasets</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Owner id</th>
            <th>Files</th>
            <th>Total size</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {datasets.map((dataset) => (
            <tr key={dataset.id}>
              <td>{dataset.name}</td>
              <td>{dataset.owner_id}</td>
              <td>{dataset.file_count}</td>
              <td>{formatBytes(dataset.total_size_bytes)}</td>
              <td>{new Date(dataset.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

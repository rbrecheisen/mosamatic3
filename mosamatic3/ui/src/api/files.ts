import { request } from './client';

export type DatasetFile = {
  id: string;
  relative_path: string;
  size_bytes: number;
  created_at: string;
};

export type Dataset = {
  id: string;
  name: string;
  kind: 'input' | 'output' | string;
  source_task_key?: string | null;
  source_task_id?: string | null;
  created_at: string;
  file_count: number;
  total_size_bytes: number;
  files: DatasetFile[];
};

export type DatasetSummary = {
  id: string;
  name: string;
  kind: 'input' | 'output' | string;
  source_task_key?: string | null;
  source_task_id?: string | null;
  created_at: string;
  file_count: number;
  total_size_bytes: number;
};

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('access_token');
  if (!token) {
    return {};
  }
  return {
    Authorization: `Bearer ${token}`,
  };
}

export async function uploadDataset(
  name: string,
  files: FileList | File[],
): Promise<Dataset> {
  const formData = new FormData();
  formData.append('name', name);
  Array.from(files).forEach((file) => {
    const relativePath =
      (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    formData.append('files', file, relativePath);
  });
  return request<Dataset>('/api/datasets', {
    method: 'POST',
    body: formData,
  });
}

export async function listDatasets(): Promise<DatasetSummary[]> {
  return request<DatasetSummary[]>('/api/datasets');
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  return request<Dataset>(`/api/datasets/${datasetId}`);
}

export async function deleteDataset(datasetId: string): Promise<void> {
  await request<void>(`/api/datasets/${datasetId}`, {
    method: 'DELETE',
  });
}

export async function deleteOutputResults(): Promise<void> {
  await request<void>('/api/datasets/output-results', {
    method: 'DELETE',
  });
}

export async function downloadDataset(datasetId: string): Promise<void> {
  const response = await fetch(`/api/datasets/${datasetId}/download`, {
    method: 'GET',
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to download dataset');
  }
  const blob = await response.blob();
  const contentDisposition = response.headers.get('Content-Disposition');
  const filenameMatch = contentDisposition?.match(/filename="(.+)"/);
  const filename = filenameMatch?.[1] ?? `dataset-${datasetId}.zip`;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
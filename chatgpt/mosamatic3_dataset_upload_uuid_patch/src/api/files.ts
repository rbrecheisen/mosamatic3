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
  created_at: string;
  file_count: number;
  total_size_bytes: number;
  files: DatasetFile[];
};

/**
 * Upload files or directories as one named dataset.
 */
export async function createDataset(name: string, files: FileList | File[]): Promise<Dataset> {
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

/**
 * Retrieve the current user's datasets.
 */
export async function listDatasets(): Promise<Dataset[]> {
  return request<Dataset[]>('/api/datasets');
}

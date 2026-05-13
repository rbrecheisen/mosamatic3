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
  files: DatasetFile[];
};

export type DatasetSummary = {
  id: string;
  name: string;
  created_at: string;
  file_count: number;
  total_size_bytes: number;
};

export async function uploadDataset(
  name: string,
  files: FileList | File[],
): Promise<{ dataset: Dataset }> {
  const formData = new FormData();
  formData.append('name', name);

  Array.from(files).forEach((file) => {
    const relativePath =
      (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

    formData.append('files', file, relativePath);
  });

  return request<{ dataset: Dataset }>('/api/datasets', {
    method: 'POST',
    body: formData,
  });
}

export async function listDatasets(): Promise<DatasetSummary[]> {
  return request<DatasetSummary[]>('/api/datasets');
}

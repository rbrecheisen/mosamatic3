import { request } from './client';

export type UploadedFile = {
  path: string;
  name: string;
  size_bytes?: number;
  is_directory: boolean;
  created_at?: string;
};

/**
 * Upload files or directories to the backend API.
 * @param files 
 * @returns 
 */
export async function uploadFiles(files: FileList | File[]): Promise<{ saved_files: string[] }> {
  const formData = new FormData();
  Array.from(files).forEach((file) => {
    const relativePath =
      (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

    formData.append('files', file, relativePath);
  });
  return request<{ saved_files: string[] }>('/api/uploads', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Retrieve list of uploaded files and directories.
 * @returns JSON data describing files.
 */
export async function listUploadedFiles(): Promise<UploadedFile[]> {
  return request<UploadedFile[]>('/api/uploads');
}
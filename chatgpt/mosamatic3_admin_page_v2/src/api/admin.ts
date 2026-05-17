import { request } from './client';

export type AdminSummary = {
  user_count: number;
  dataset_count: number;
  dataset_file_count: number;
};

export type AdminUser = {
  id: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
};

export type AdminDataset = {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
  file_count: number;
  total_size_bytes: number;
};

export async function getAdminSummary(): Promise<AdminSummary> {
  return request<AdminSummary>('/api/admin/summary');
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  return request<AdminUser[]>('/api/admin/users');
}

export async function listAdminDatasets(): Promise<AdminDataset[]> {
  return request<AdminDataset[]>('/api/admin/datasets');
}

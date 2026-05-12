const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type User = {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
};

export type FormSubmission = {
  id: number;
  text_value: string;
  enabled: boolean;
  choice: string;
  notes?: string | null;
  created_at: string;
};

export type ExampleFormPayload = {
  text_value: string;
  enabled: boolean;
  choice: string;
  notes?: string;
};

export function getToken(): string | null {
  return localStorage.getItem('access_token');
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem('access_token', token);
  else localStorage.removeItem('access_token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${response.status}`);
  }
  return response.json();
}

export async function register(email: string, password: string): Promise<User> {
  return request<User>('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams();
  form.set('username', email);
  form.set('password', password);

  const data = await request<{ access_token: string }>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  });
  setToken(data.access_token);
}

export async function getCurrentUser(): Promise<User> {
  return request<User>('/api/auth/me');
}

export async function uploadFiles(files: FileList | File[]): Promise<{ saved_files: string[] }> {
  const formData = new FormData();
  Array.from(files).forEach((file) => {
    // webkitRelativePath is present when the browser input uses webkitdirectory.
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    formData.append('files', file, relativePath);
  });

  return request<{ saved_files: string[] }>('/api/uploads', {
    method: 'POST',
    body: formData,
  });
}

export async function createFormSubmission(payload: ExampleFormPayload): Promise<FormSubmission> {
  return request<FormSubmission>('/api/forms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function listFormSubmissions(): Promise<FormSubmission[]> {
  return request<FormSubmission[]>('/api/forms');
}

import { request, setToken } from './client';

export type User = {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
};

/**
 * Register user with given email and password.
 * @param email 
 * @param password 
 * @returns JSON data describing user.
 */
export async function register(email: string, password: string): Promise<User> {
  return request<User>('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
}

/**
 * Login user with given email and password.
 * @param email 
 * @param password 
 */
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

/**
 * Get currently logged in user from backend API.
 * @returns JSON data of current user.
 */
export async function getCurrentUser(): Promise<User> {
  return request<User>('/api/auth/me');
}
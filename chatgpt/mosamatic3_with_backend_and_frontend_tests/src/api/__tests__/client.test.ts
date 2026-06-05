import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getToken, request, setToken } from '../client';

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('stores, reads and clears the access token', () => {
    setToken('abc');
    expect(getToken()).toBe('abc');

    setToken(null);
    expect(getToken()).toBeNull();
  });

  it('adds the bearer token to authenticated requests', async () => {
    setToken('secret-token');
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    await request('/api/example');

    const [, options] = fetchMock.mock.calls[0];
    const headers = options?.headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer secret-token');
  });

  it('throws the backend detail message for failed requests', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Not allowed' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    }));

    await expect(request('/api/forbidden')).rejects.toThrow('Not allowed');
  });
});

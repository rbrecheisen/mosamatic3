import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { renderWithRouter } from '../../test/render';
import { ProtectedRoute } from '../protectedroute';

vi.mock('../authcontext', () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from '../authcontext';

const mockedUseAuth = vi.mocked(useAuth);

describe('ProtectedRoute', () => {
  it('shows a loading message while authentication is still loading', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    renderWithRouter(
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/home" element={<h1>Home</h1>} />
        </Route>
      </Routes>,
      ['/home'],
    );

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('redirects anonymous users to login', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    renderWithRouter(
      <Routes>
        <Route path="/login" element={<h1>Login page</h1>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/home" element={<h1>Home</h1>} />
        </Route>
      </Routes>,
      ['/home'],
    );

    expect(screen.getByRole('heading', { name: /login page/i })).toBeInTheDocument();
  });

  it('renders protected content for authenticated users', () => {
    mockedUseAuth.mockReturnValue({
      user: {
        id: 1,
        email: 'ralph@example.com',
        is_active: true,
        is_admin: false,
        created_at: '2026-06-05T08:00:00Z',
      },
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    renderWithRouter(
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/home" element={<h1>Home</h1>} />
        </Route>
      </Routes>,
      ['/home'],
    );

    expect(screen.getByRole('heading', { name: /home/i })).toBeInTheDocument();
  });
});

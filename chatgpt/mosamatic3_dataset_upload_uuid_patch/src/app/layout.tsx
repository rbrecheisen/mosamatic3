import { Outlet } from 'react-router-dom';
import { useAuth } from './authcontext';

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Body composition analysis and reporting</p>
          <h1>Mosamatic3</h1>
        </div>
        {user && (
          <div className="user-box">
            <span>{user.email}</span>
            <button className="secondary" onClick={logout}>Logout</button>
          </div>
        )}
      </header>
      <Outlet />
    </main>
  );
}
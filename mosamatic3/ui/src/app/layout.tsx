import { Link, NavLink, useNavigate, Outlet } from 'react-router-dom';
import { useAuth } from './authcontext';

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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
      {user && (
        <div className='row'>
          <button className='button-like' onClick={() => navigate('/data')}>Data</button>
          <button className='button-like' onClick={() => navigate('/analyze')}>Analyze</button>
          <button className='button-like' onClick={() => navigate('/report')}>Report</button>
        </div>
      )}
      &nbsp;
      <Outlet />
    </main>
  );
}
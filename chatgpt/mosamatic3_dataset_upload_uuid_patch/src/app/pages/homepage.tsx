// src/features/dashboard/HomePage.tsx
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../authcontext';

export function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <section className="page">
      <div className="card">
        <p className="eyebrow">Welcome</p>
        <h2>
          Hello{user?.email ? `, ${user.email}` : ''}.
        </h2>
        <p className="muted">
          You are logged in. From here you can upload data or start an analysis.
        </p>
        <div className="actions">
          <button className="button-like" onClick={() => navigate('/data')}>Data</button>
          &nbsp;
          <button className="button-like" onClick={() => navigate('/analyse')}>Analyze</button>
          &nbsp;
          <button className="button-like" onClick={() => navigate('/report')}>Report</button>
        </div>
      </div>
    </section>
  );
}
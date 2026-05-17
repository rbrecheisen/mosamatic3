import { useAuth } from '../authcontext';

export function HomePage() {
  const { user } = useAuth();

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
      </div>
    </section>
  );
}
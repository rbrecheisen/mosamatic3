import { useEffect, useState } from 'react';
import { AuthPanel } from './components/authpanel';
import { ExampleForm } from './components/exampleform';
import { UploadPanel } from './components/uploadpanel';
import { getCurrentUser, setToken, User } from './api/client';
import './styles.css';

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshUser() {
    try {
      setUser(await getCurrentUser());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshUser();
  }, []);

  function logout() {
    setToken(null);
    setUser(null);
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Analysis and reporting</p>
          <h1>Mosamatic3</h1>
        </div>
        {user && (
          <div className="user-box">
            <span>{user.email}</span>
            <button className="secondary" onClick={logout}>Logout</button>
          </div>
        )}
      </header>

      {loading ? <p>Loading...</p> : <AuthPanel onLoggedIn={refreshUser} />}

      {user ? (
        <div className="grid">
          <UploadPanel />
          <ExampleForm />
        </div>
      ) : (
        <section className="card muted">Login or register first to use uploads and form storage.</section>
      )}
    </main>
  );
}

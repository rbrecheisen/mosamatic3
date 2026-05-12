import { useState } from 'react';
import { login, register, User } from '../api/client';

type Props = {
  onLoggedIn: (user: User | null) => Promise<void>;
};

export function AuthPanel({ onLoggedIn }: Props) {
  const [email, setEmail] = useState('demo@example.com');
  const [password, setPassword] = useState('demo12345');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [message, setMessage] = useState<string>('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setMessage('');
    try {
      if (mode === 'register') await register(email, password);
      await login(email, password);
      await onLoggedIn(null);
      setMessage('Logged in');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Something went wrong');
    }
  }

  return (
    <section className="card">
      <h2>Account</h2>
      <form onSubmit={submit} className="stack">
        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
        </label>
        <label>
          Password
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" required />
        </label>
        <div className="row">
          <button type="button" className={mode === 'login' ? 'secondary active' : 'secondary'} onClick={() => setMode('login')}>
            Login
          </button>
          <button type="button" className={mode === 'register' ? 'secondary active' : 'secondary'} onClick={() => setMode('register')}>
            Register + login
          </button>
          <button type="submit">Submit</button>
        </div>
      </form>
      {message && <p className="message">{message}</p>}
    </section>
  );
}

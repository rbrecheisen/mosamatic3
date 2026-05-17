// src/app/ErrorPage.tsx
import { Link, useRouteError } from 'react-router-dom';

export function ErrorPage() {
  const error = useRouteError();
  let message = 'Something went wrong.';
  if (error instanceof Error) {
    message = error.message;
  }
  return (
    <section className="page">
      <div className="card">
        <h2>Oops</h2>
        <p className="error">{message}</p>
        <Link className="button-like" to="/home">
          Back to home
        </Link>
      </div>
    </section>
  );
}
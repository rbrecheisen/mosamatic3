import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './authcontext';

export function AdminRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return <p className="muted">Loading...</p>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!user.is_admin) {
    return <Navigate to="/home" replace />;
  }

  return <Outlet />;
}

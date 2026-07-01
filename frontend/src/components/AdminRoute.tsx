import { Navigate, Outlet } from "react-router-dom";
import { useAuth, isAdmin } from "../auth";

export default function AdminRoute() {
  const { user, loading } = useAuth();

  if (loading) return <p className="muted">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin(user)) return <p className="error">Admin access required.</p>;

  return <Outlet />;
}

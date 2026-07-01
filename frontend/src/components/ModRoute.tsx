import { Navigate, Outlet } from "react-router-dom";
import { useAuth, isMod } from "../auth";

export default function ModRoute() {
  const { user, loading } = useAuth();

  if (loading) return <p className="muted">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (!isMod(user)) return <p className="error">Moderator access required.</p>;

  return <Outlet />;
}

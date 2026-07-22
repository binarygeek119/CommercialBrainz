import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

/** Silent gate: non–power users never see bulk-submit UI. */
export default function BulkSubmitRoute() {
  const { user, loading } = useAuth();

  if (loading) return <p className="muted">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.bulk_submit_enabled && !user.can_bulk_submit) {
    return <Navigate to="/submit" replace />;
  }

  return <Outlet />;
}

import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { api, type LoginAnnouncement } from "../api";
import { useAuth } from "../auth";

const SKIP_PATHS = new Set([
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/verify-email/pending",
]);

export default function LoginAnnouncementGate() {
  const { user, loading: authLoading } = useAuth();
  const location = useLocation();
  const [announcement, setAnnouncement] = useState<LoginAnnouncement | null>(null);
  const [error, setError] = useState("");
  const [acking, setAcking] = useState(false);

  useEffect(() => {
    if (!user) {
      setAnnouncement(null);
      return;
    }
    let cancelled = false;
    api
      .myAnnouncement()
      .then((doc) => {
        if (!cancelled) {
          setAnnouncement(doc);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (authLoading || !user || SKIP_PATHS.has(location.pathname)) {
    return null;
  }

  if (error && !announcement) {
    return null;
  }

  if (!announcement?.body) {
    return null;
  }

  const dismiss = async () => {
    setAcking(true);
    setError("");
    try {
      await api.ackAnnouncement();
      setAnnouncement(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAcking(false);
    }
  };

  return (
    <div
      className="terms-gate-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-announcement-title"
    >
      <div className="terms-gate-card">
        <p className="terms-gate-badge">Site notice</p>
        <h1 id="login-announcement-title" className="terms-gate-title">
          {announcement.title || "Announcement"}
        </h1>
        <div className="terms-gate-scroll">
          <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{announcement.body}</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
        <button
          type="button"
          className="btn btn-primary terms-gate-btn"
          onClick={() => void dismiss()}
          disabled={acking}
        >
          {acking ? "Saving…" : "OK"}
        </button>
      </div>
    </div>
  );
}

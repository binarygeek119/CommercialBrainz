import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const token = searchParams.get("token") || "";

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!token);

  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await api.verifyEmail(token);
        if (!cancelled) {
          setMessage(res.message);
          await refresh();
          setTimeout(() => navigate("/"), 2500);
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, navigate, refresh]);

  if (!token) {
    return (
      <div className="card" style={{ maxWidth: 480, margin: "2rem auto" }}>
        <p className="error">Invalid verification link.</p>
        <p className="muted">
          <Link to="/verify-email/pending">Resend verification email</Link>
        </p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto" }}>
      <h1 className="page-title">Verify email</h1>
      <div className="card">
        {loading && <p className="muted">Verifying your email…</p>}
        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}
        {!loading && error && (
          <p className="muted" style={{ marginTop: "1rem" }}>
            <Link to="/verify-email/pending">Request a new verification link</Link>
          </p>
        )}
      </div>
    </div>
  );
}

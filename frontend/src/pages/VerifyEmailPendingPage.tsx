import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";

export default function VerifyEmailPendingPage() {
  const { user, refresh } = useAuth();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleResend = async () => {
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const res = await api.resendVerification();
      setMessage(res.message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setError("");
    setMessage("");
    try {
      const u = await api.me();
      if (u.email_verified) {
        setMessage("Email verified! You can vote and submit edits.");
        await refresh();
      } else {
        setError("Not verified yet. Check your inbox or resend the email.");
      }
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (!user) {
    return (
      <div className="card" style={{ maxWidth: 480, margin: "2rem auto" }}>
        <p className="muted">
          <Link to="/login">Log in</Link> to resend a verification email.
        </p>
      </div>
    );
  }

  if (user.email_verified) {
    return (
      <div className="card" style={{ maxWidth: 480, margin: "2rem auto" }}>
        <p className="success">Your email is verified.</p>
        <p className="muted" style={{ marginTop: "1rem" }}>
          <Link to="/">Go to home</Link>
        </p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto" }}>
      <h1 className="page-title">Check your email</h1>
      <div className="card">
        <p>
          We sent a verification link to <strong>{user.email}</strong>.
        </p>
        <p className="muted">
          Verify your email to vote on edits and submit commercial links. You can browse the site
          while you wait.
        </p>
        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "1rem" }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleResend}
            disabled={loading}
          >
            {loading ? "Sending…" : "Resend verification email"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={handleRefresh}>
            I&apos;ve verified — refresh
          </button>
        </div>
      </div>
    </div>
  );
}

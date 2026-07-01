import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");

    if (!token) {
      setError("Missing reset token. Use the link from your email.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.resetPassword(token, password);
      setMessage(res.message);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="card" style={{ maxWidth: 400, margin: "2rem auto" }}>
        <p className="error">Invalid reset link.</p>
        <p className="muted">
          <Link to="/forgot-password">Request a new password reset</Link>
        </p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 400, margin: "2rem auto" }}>
      <h1 className="page-title">Reset password</h1>
      <form onSubmit={handleSubmit} className="card">
        <div className="form-group">
          <label>New password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </div>
        <div className="form-group">
          <label>Confirm password</label>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
          />
        </div>
        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Updating…" : "Update password"}
        </button>
        <p className="muted" style={{ marginTop: "1rem" }}>
          <Link to="/login">Back to log in</Link>
        </p>
      </form>
    </div>
  );
}

import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const res = await api.forgotPassword(email);
      setMessage(res.message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "2rem auto" }}>
      <h1 className="page-title">Forgot password</h1>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        Enter your account email and we&apos;ll send a reset link if the account exists.
      </p>
      <form onSubmit={handleSubmit} className="card">
        <div className="form-group">
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Sending…" : "Send reset link"}
        </button>
        <p className="muted" style={{ marginTop: "1rem" }}>
          <Link to="/login">Back to log in</Link>
        </p>
      </form>
    </div>
  );
}

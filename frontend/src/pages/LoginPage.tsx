import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "2rem auto" }}>
      <h1 className="page-title">Log in</h1>
      <form onSubmit={handleSubmit} className="card">
        <div className="form-group">
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn btn-primary">Log in</button>
        <p className="muted" style={{ marginTop: "1rem" }}>
          <Link to="/forgot-password">Forgot password?</Link>
        </p>
        <p className="muted" style={{ marginTop: "0.5rem" }}>
          No account? <Link to="/register">Register</Link>
        </p>
      </form>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth";
import { api } from "../api";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    inviteCode: searchParams.get("invite") ?? "",
  });
  const [error, setError] = useState("");

  const { data: registrationSettings, isLoading: settingsLoading } = useQuery({
    queryKey: ["registration-settings"],
    queryFn: () => api.registrationSettings(),
  });

  useEffect(() => {
    const invite = searchParams.get("invite");
    if (invite) {
      setForm((prev) => ({ ...prev, inviteCode: invite }));
    }
  }, [searchParams]);

  const inviteOnly = registrationSettings?.invite_only ?? false;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await register(
        form.username,
        form.email,
        form.password,
        inviteOnly ? form.inviteCode : form.inviteCode || undefined
      );
      navigate("/verify-email/pending");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "2rem auto" }}>
      <h1 className="page-title">Register</h1>
      {settingsLoading ? (
        <p className="muted" style={{ marginBottom: "1rem" }}>Loading registration settings…</p>
      ) : inviteOnly ? (
        <p className="muted" style={{ marginBottom: "1rem" }}>
          Registration is <strong>invite-only</strong>. You need a valid invite code to create an
          account. Browsing the site does not require an account.
        </p>
      ) : (
        <p className="muted" style={{ marginBottom: "1rem" }}>
          New accounts start as <strong>vote-only</strong>. We&apos;ll email you a verification link
          — confirm your address to vote and submit. You can upgrade to submit access after passing a
          short quiz on our submission terms.
        </p>
      )}
      <form onSubmit={handleSubmit} className="card">
        {inviteOnly && (
          <div className="form-group">
            <label>Invite code</label>
            <input
              value={form.inviteCode}
              onChange={(e) => setForm({ ...form, inviteCode: e.target.value })}
              required
              placeholder="XXXX-XXXX-XXXX"
              autoComplete="off"
            />
          </div>
        )}
        <div className="form-group">
          <label>Username</label>
          <input
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
            minLength={3}
          />
        </div>
        <div className="form-group">
          <label>Email</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
        </div>
        <div className="form-group">
          <label>Password</label>
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
            minLength={8}
          />
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn btn-primary">Create account</button>
        <p className="muted" style={{ marginTop: "1rem" }}>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}

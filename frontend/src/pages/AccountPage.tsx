import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth, isEmailVerified } from "../auth";
import { api, type ApiToken, type ApiTokenCreated } from "../api";

function formatDate(value: string | null): string {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function formatPoints(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export default function AccountPage() {
  const { user, loading, refresh, logout } = useAuth();
  const queryClient = useQueryClient();

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  const [emailPassword, setEmailPassword] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [changingEmail, setChangingEmail] = useState(false);

  const [tokenLabel, setTokenLabel] = useState("");
  const [creatingToken, setCreatingToken] = useState(false);
  const [createdToken, setCreatedToken] = useState<ApiTokenCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const [deletePassword, setDeletePassword] = useState("");
  const [recipientUsername, setRecipientUsername] = useState("");
  const [requestingDeletion, setRequestingDeletion] = useState(false);
  const [cancellingDeletion, setCancellingDeletion] = useState(false);

  const { data: tokens = [], isLoading: tokensLoading } = useQuery({
    queryKey: ["api-tokens"],
    queryFn: () => api.listApiTokens(),
    enabled: !!user,
  });

  const { data: deletionRequest, refetch: refetchDeletion } = useQuery({
    queryKey: ["deletion-request"],
    queryFn: () => api.getDeletionRequest(),
    enabled: !!user,
  });

  if (loading) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;

  const clearMessages = () => {
    setError("");
    setSuccess("");
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match");
      return;
    }
    setChangingPassword(true);
    try {
      const result = await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccess(result.message);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setChangingPassword(false);
    }
  };

  const handleChangeEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    setChangingEmail(true);
    try {
      await api.changeEmail({ password: emailPassword, new_email: newEmail.trim() });
      setSuccess("Email updated. Check your inbox to verify the new address.");
      setEmailPassword("");
      setNewEmail("");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setChangingEmail(false);
    }
  };

  const handleCreateToken = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    setCreatingToken(true);
    setCreatedToken(null);
    try {
      const created = await api.createApiToken(tokenLabel.trim() || undefined);
      setCreatedToken(created);
      setTokenLabel("");
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCreatingToken(false);
    }
  };

  const handleRevokeToken = async (token: ApiToken) => {
    if (!window.confirm(`Revoke token ${token.token_prefix}…?`)) return;
    clearMessages();
    try {
      await api.revokeApiToken(token.id);
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const copyToken = async () => {
    if (!createdToken) return;
    await navigator.clipboard.writeText(createdToken.token);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  const handleRequestDeletion = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    const points = user.reputation_points ?? 0;
    if (
      points > 0 &&
      !recipientUsername.trim() &&
      !window.confirm(
        "You have reputation points but no recipient. The request will fail unless you enter someone to receive them."
      )
    ) {
      return;
    }
    if (
      !window.confirm(
        "Request account deletion? A moderator must approve before your account is removed."
      )
    ) {
      return;
    }
    setRequestingDeletion(true);
    try {
      await api.requestAccountDeletion({
        password: deletePassword,
        recipient_username: recipientUsername.trim() || undefined,
      });
      setSuccess("Account deletion requested. A moderator will review it.");
      setDeletePassword("");
      setRecipientUsername("");
      refetchDeletion();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRequestingDeletion(false);
    }
  };

  const handleCancelDeletion = async () => {
    if (!window.confirm("Cancel your account deletion request?")) return;
    clearMessages();
    setCancellingDeletion(true);
    try {
      await api.cancelDeletionRequest();
      setSuccess("Account deletion request cancelled.");
      refetchDeletion();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCancellingDeletion(false);
    }
  };

  const points = user.reputation_points ?? 0;
  const pendingDeletion = deletionRequest?.status === "pending";

  return (
    <div>
      <h1 className="page-title">Account settings</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        Signed in as <strong>{user.username}</strong> ·{" "}
        <Link to={`/user/${encodeURIComponent(user.username)}`}>Public profile</Link>
      </p>

      {error && <p className="error">{error}</p>}
      {success && <p className="success">{success}</p>}

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ marginTop: 0 }}>Reputation</h2>
        <p style={{ fontSize: "1.75rem", fontWeight: 700, margin: "0.25rem 0" }}>
          {formatPoints(points)} points
        </p>
        <p className="muted" style={{ margin: 0 }}>
          {user.accepted_edits_count} accepted edit{user.accepted_edits_count === 1 ? "" : "s"}
        </p>
      </div>

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ marginTop: 0 }}>Email</h2>
        <p>
          Current: <strong>{user.email}</strong>{" "}
          {!isEmailVerified(user) && <span className="badge badge-submitted">Unverified</span>}
        </p>
        {!isEmailVerified(user) && (
          <p className="muted">
            Verify your email to vote and submit.{" "}
            <button
              type="button"
              className="btn btn-secondary"
              style={{ marginLeft: "0.5rem" }}
              onClick={async () => {
                clearMessages();
                try {
                  const result = await api.resendVerification();
                  setSuccess(result.message);
                } catch (err) {
                  setError((err as Error).message);
                }
              }}
            >
              Resend verification
            </button>
          </p>
        )}
        <form onSubmit={handleChangeEmail} style={{ marginTop: "1rem" }}>
          <div className="form-group">
            <label htmlFor="email-password">Current password</label>
            <input
              id="email-password"
              type="password"
              value={emailPassword}
              onChange={(e) => setEmailPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <div className="form-group">
            <label htmlFor="new-email">New email</label>
            <input
              id="new-email"
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <button type="submit" className="btn btn-secondary" disabled={changingEmail}>
            {changingEmail ? "Updating…" : "Change email"}
          </button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ marginTop: 0 }}>Password</h2>
        <form onSubmit={handleChangePassword}>
          <div className="form-group">
            <label htmlFor="current-password">Current password</label>
            <input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <div className="form-group">
            <label htmlFor="new-password">New password</label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          <div className="form-group">
            <label htmlFor="confirm-password">Confirm new password</label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          <button type="submit" className="btn btn-secondary" disabled={changingPassword}>
            {changingPassword ? "Updating…" : "Change password"}
          </button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ marginTop: 0 }}>Read-only API tokens</h2>
        <p className="muted">
          Tokens can read public API data at the authenticated rate limit (5 req/s). They cannot
          vote, submit edits, or change account settings. Use{" "}
          <code>Authorization: Bearer &lt;token&gt;</code> or{" "}
          <code>X-API-Key: &lt;token&gt;</code>.
        </p>

        <form onSubmit={handleCreateToken} style={{ marginTop: "1rem" }}>
          <div className="form-group">
            <label htmlFor="token-label">Label (optional)</label>
            <input
              id="token-label"
              value={tokenLabel}
              onChange={(e) => setTokenLabel(e.target.value)}
              placeholder='e.g. "Home scraper", "Archive mirror"'
            />
          </div>
          <button type="submit" className="btn btn-secondary" disabled={creatingToken}>
            {creatingToken ? "Creating…" : "Create read-only token"}
          </button>
        </form>

        {createdToken && (
          <div
            className="card"
            style={{ marginTop: "1rem", border: "1px solid var(--warning, #c90)" }}
          >
            <p style={{ marginTop: 0 }}>
              <strong>Copy this token now.</strong> It will not be shown again.
            </p>
            <code
              style={{
                display: "block",
                wordBreak: "break-all",
                padding: "0.75rem",
                background: "var(--surface)",
                borderRadius: 4,
                marginBottom: "0.75rem",
              }}
            >
              {createdToken.token}
            </code>
            <button type="button" className="btn btn-secondary" onClick={copyToken}>
              {copied ? "Copied!" : "Copy token"}
            </button>
          </div>
        )}

        <h3 style={{ marginTop: "1.5rem" }}>Active tokens</h3>
        {tokensLoading ? (
          <p className="muted">Loading tokens…</p>
        ) : tokens.length === 0 ? (
          <p className="muted">No active API tokens.</p>
        ) : (
          <div className="stack">
            {tokens.map((token) => (
              <div
                key={token.id}
                className="flex-between"
                style={{ alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}
              >
                <div>
                  <strong className="mono">{token.token_prefix}…</strong>
                  {token.label && <span className="muted"> · {token.label}</span>}
                  <p className="muted" style={{ margin: "0.35rem 0 0" }}>
                    {token.scope.replace("_", " ")} · created {formatDate(token.created_at)} ·
                    last used {formatDate(token.last_used_at)}
                  </p>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => handleRevokeToken(token)}
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: "1.5rem", borderColor: "var(--danger, #c33)" }}>
        <h2 style={{ marginTop: 0 }}>Delete account</h2>
        {pendingDeletion ? (
          <>
            <p>
              Your deletion request is <strong>pending moderator approval</strong> (submitted{" "}
              {formatDate(deletionRequest.created_at)}).
            </p>
            {deletionRequest.points_to_transfer > 0 && deletionRequest.recipient_username && (
              <p className="muted">
                {formatPoints(deletionRequest.points_to_transfer)} points will transfer to{" "}
                <strong>{deletionRequest.recipient_username}</strong> if approved.
              </p>
            )}
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleCancelDeletion}
              disabled={cancellingDeletion}
            >
              {cancellingDeletion ? "Cancelling…" : "Cancel deletion request"}
            </button>
          </>
        ) : (
          <>
            <p className="muted">
              Account deletion requires moderator approval. If you have reputation points, specify
              another member to receive them. Close any open edits before requesting deletion.
            </p>
            <form onSubmit={handleRequestDeletion} style={{ marginTop: "1rem" }}>
              {points > 0 && (
                <div className="form-group">
                  <label htmlFor="recipient-username">
                    Transfer {formatPoints(points)} points to (username)
                  </label>
                  <input
                    id="recipient-username"
                    value={recipientUsername}
                    onChange={(e) => setRecipientUsername(e.target.value)}
                    placeholder="recipient username"
                    required={points > 0}
                  />
                </div>
              )}
              <div className="form-group">
                <label htmlFor="delete-password">Confirm with your password</label>
                <input
                  id="delete-password"
                  type="password"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </div>
              <button type="submit" className="btn btn-danger" disabled={requestingDeletion}>
                {requestingDeletion ? "Submitting…" : "Request account deletion"}
              </button>
            </form>
          </>
        )}
      </div>

      <p className="muted">
        <button type="button" className="btn btn-secondary" onClick={logout}>
          Log out
        </button>
      </p>
    </div>
  );
}

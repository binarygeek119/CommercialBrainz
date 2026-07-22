import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export const REPORT_REASONS = [
  {
    value: "banned",
    label: "Banned",
    hint: "Needs to be flagged correctly",
  },
  {
    value: "adult_ad",
    label: "Adult/sexual (ad, non-porn)",
    hint: "Needs to be flagged correctly",
  },
  {
    value: "adult_porn",
    label: "Adult/sexual (porn, non-ad)",
    hint: "Will be removed",
  },
  {
    value: "hate_speech",
    label: "Hate speech",
    hint: "Moderators will review",
  },
  {
    value: "other",
    label: "Other",
    hint: "Moderators will review",
  },
] as const;

type Props = {
  commercialSbid: string;
  commercialTitle: string;
  loggedIn: boolean;
  onClose: () => void;
  onSubmitted?: () => void;
};

export default function ReportCommercialDialog({
  commercialSbid,
  commercialTitle,
  loggedIn,
  onClose,
  onSubmitted,
}: Props) {
  const [reason, setReason] = useState<string>("");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const selected = REPORT_REASONS.find((r) => r.value === reason);
  const needsDetails = reason === "other";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!loggedIn || !reason) return;
    if (needsDetails && !details.trim()) {
      setError("Please describe the issue for Other.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.reportCommercial(commercialSbid, {
        reason,
        details: details.trim() || undefined,
      });
      setDone(true);
      onSubmitted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit report");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="report-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="report-commercial-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div className="report-dialog-card">
        <h2 id="report-commercial-title" className="report-dialog-title">
          Report commercial
        </h2>
        <p className="muted" style={{ marginTop: 0 }}>
          {commercialTitle}
        </p>

        {!loggedIn ? (
          <>
            <p>You need to be logged in to report content.</p>
            <div className="report-dialog-actions">
              <Link to="/login" className="btn btn-primary">
                Log in
              </Link>
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Cancel
              </button>
            </div>
          </>
        ) : done ? (
          <>
            <p>Thanks — your report was submitted for review.</p>
            {selected && <p className="muted">{selected.hint}</p>}
            <div className="report-dialog-actions">
              <button type="button" className="btn btn-primary" onClick={onClose}>
                Close
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={(e) => void handleSubmit(e)}>
            <div className="form-group">
              <label htmlFor="report-reason">Why are you reporting this?</label>
              <select
                id="report-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
              >
                <option value="" disabled>
                  Select a reason…
                </option>
                {REPORT_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>

            {selected && (
              <p className="muted" style={{ marginTop: "-0.35rem" }}>
                {selected.hint}
              </p>
            )}

            <div className="form-group">
              <label htmlFor="report-details">
                Details{needsDetails ? " (required)" : " (optional)"}
              </label>
              <textarea
                id="report-details"
                value={details}
                onChange={(e) => setDetails(e.target.value)}
                rows={4}
                maxLength={2000}
                placeholder={
                  needsDetails
                    ? "Describe the issue…"
                    : "Optional context for moderators…"
                }
                required={needsDetails}
              />
            </div>

            {error && <p className="error">{error}</p>}

            <div className="report-dialog-actions">
              <button type="submit" className="btn btn-primary" disabled={!reason || busy}>
                {busy ? "Submitting…" : "Submit report"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={busy}
                onClick={onClose}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

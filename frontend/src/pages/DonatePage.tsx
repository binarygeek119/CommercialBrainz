import { useEffect, useState, type FormEvent } from "react";
import donateMd from "@site-docs/donate.md?raw";
import { api, type DonateFundsPublic, type DonationFundTotals } from "../api";
import SiteDocMarkdown from "../components/SiteDocMarkdown";

type ModalKind = "cookies" | null;

const BUY_ME_A_COFFEE_URL = "https://www.buymeacoffee.com/binarygeekq";

const DOMAIN_MESSAGE = "Donation for the CommercialBrainz domain";
const VM_MESSAGE = "Donation for the CommercialBrainz cloud VM";

function buyMeACoffeeUrl(message: string): string {
  const url = new URL(BUY_ME_A_COFFEE_URL);
  // BMC's page has a "Say something nice..." field. `message` is the common
  // query key; we also copy to the clipboard as a reliable fallback.
  url.searchParams.set("message", message);
  return url.toString();
}

async function openBuyMeACoffee(message: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(message);
  } catch {
    // Clipboard may be blocked; still open the donation page.
  }
  window.open(buyMeACoffeeUrl(message), "_blank", "noopener,noreferrer");
}

function formatMoney(n: number): string {
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function FundBar({ label, totals }: { label: string; totals: DonationFundTotals }) {
  const hasGoal = totals.goal > 0;
  const pct = hasGoal ? Math.min(100, (totals.balance / totals.goal) * 100) : 0;
  return (
    <div className="donate-fund-bar">
      <div className="donate-fund-bar-header">
        <strong>{label}</strong>
        <span>
          {hasGoal
            ? `${formatMoney(totals.balance)} / ${formatMoney(totals.goal)}`
            : `${formatMoney(totals.balance)} in fund`}
        </span>
      </div>
      <div
        className="donate-fund-bar-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={hasGoal ? totals.goal : 100}
        aria-valuenow={hasGoal ? totals.balance : 0}
        aria-label={`${label} fund`}
      >
        <div className="donate-fund-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="muted donate-fund-bar-meta">
        {hasGoal
          ? `${formatMoney(totals.raised)} donated · ${formatMoney(totals.spent)} paid`
          : "Set a goal in admin"}
      </p>
    </div>
  );
}

function CookieDonateModal({
  onClose,
  onSubmitted,
}: {
  onClose: () => void;
  onSubmitted: (message: string) => void;
}) {
  const [cookies, setCookies] = useState("");
  const [note, setNote] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!agreed) {
      setError("Please accept the agreement before submitting.");
      return;
    }
    setBusy(true);
    try {
      const result = await api.donateYouTubeCookies({
        cookies,
        agreement_accepted: true,
        donor_note: note.trim() || undefined,
      });
      onSubmitted(result.message);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit cookies");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="report-overlay" role="dialog" aria-modal="true" aria-labelledby="cookie-donate-title">
      <form className="report-dialog-card" style={{ maxWidth: 560 }} onSubmit={(e) => void handleSubmit(e)}>
        <h2 id="cookie-donate-title" className="report-dialog-title">
          Donate YouTube cookies
        </h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Paste a Netscape <code>cookies.txt</code> from a throwaway YouTube/Google account used
          only for login — nothing personal, no payment methods, no mail you care about. We use it
          only so yt-dlp can fetch metadata and hashes when our cookies expire.
        </p>

        <div className="form-group">
          <label htmlFor="donate-cookies-text">cookies.txt</label>
          <textarea
            id="donate-cookies-text"
            rows={8}
            value={cookies}
            onChange={(e) => setCookies(e.target.value)}
            required
            placeholder="# Netscape HTTP Cookie File"
            style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.85rem" }}
          />
        </div>
        <div className="form-group">
          <label htmlFor="donate-cookies-note">Note (optional)</label>
          <input
            id="donate-cookies-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            placeholder="e.g. dummy account created 2026-07"
          />
        </div>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start", marginBottom: "1rem" }}>
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            style={{ marginTop: "0.2rem" }}
          />
          <span>
            I confirm these cookies are from a disposable account with no personal data, and I
            understand CommercialBrainz will store them encrypted and use them only for YouTube
            scraping.
          </span>
        </label>
        {error && <p className="error">{error}</p>}
        <div className="report-dialog-actions">
          <button type="submit" className="btn btn-primary" disabled={busy || !cookies.trim()}>
            {busy ? "Submitting…" : "Submit cookies"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

export default function DonatePage() {
  const [modal, setModal] = useState<ModalKind>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [pendingCookies, setPendingCookies] = useState<number | null>(null);
  const [funds, setFunds] = useState<DonateFundsPublic | null>(null);

  useEffect(() => {
    api
      .donateCookieBacklogStats()
      .then((stats) => setPendingCookies(stats.pending + stats.active))
      .catch(() => setPendingCookies(null));
  }, [flash]);

  useEffect(() => {
    api
      .donateFunds()
      .then(setFunds)
      .catch(() => setFunds(null));
  }, []);

  return (
    <div style={{ maxWidth: 760 }}>
      {funds && (
        <section className="donate-funds" aria-label="Fund progress">
          <FundBar label="Cloud VM" totals={funds.cloud_vm} />
          <FundBar label="Domain" totals={funds.domain} />
        </section>
      )}

      <div style={funds ? { marginTop: "1.25rem" } : undefined}>
        <SiteDocMarkdown source={donateMd} file="donate.md" className="card" />
      </div>

      {flash && (
        <div className="card" style={{ marginTop: "1.25rem", borderColor: "var(--success)" }}>
          <p style={{ margin: 0 }}>{flash}</p>
        </div>
      )}

      <section className="card" style={{ marginTop: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Donate now</h2>
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          Buttons open Buy Me a Coffee and copy the matching fund note to your clipboard. Cookie
          donations use the form below.
        </p>
        <div className="stack" style={{ gap: "0.75rem" }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void openBuyMeACoffee(DOMAIN_MESSAGE)}
          >
            Donate toward the domain
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void openBuyMeACoffee(VM_MESSAGE)}
          >
            Donate toward the VM
          </button>
          <div>
            <button type="button" className="btn btn-primary" onClick={() => setModal("cookies")}>
              Donate cookies
            </button>
            {pendingCookies != null && (
              <p className="muted" style={{ fontSize: "0.9rem", marginBottom: 0, marginTop: "0.5rem" }}>
                Backlog currently holds {pendingCookies} usable donation
                {pendingCookies === 1 ? "" : "s"} (pending or active).
              </p>
            )}
          </div>
        </div>
      </section>

      {modal === "cookies" && (
        <CookieDonateModal
          onClose={() => setModal(null)}
          onSubmitted={(message) => setFlash(message)}
        />
      )}
    </div>
  );
}

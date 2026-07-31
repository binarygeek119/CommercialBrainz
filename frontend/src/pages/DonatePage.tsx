import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";
import { api } from "../api";

type ModalKind = "domain" | "vm" | "cookies" | null;

function DummyDonateModal({
  title,
  body,
  onClose,
}: {
  title: string;
  body: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="report-overlay" role="dialog" aria-modal="true" aria-labelledby="donate-modal-title">
      <div className="report-dialog-card" style={{ maxWidth: 420 }}>
        <h2 id="donate-modal-title" className="report-dialog-title">
          {title}
        </h2>
        <div style={{ marginBottom: "1rem" }}>
          {body}
        </div>
        <div className="report-dialog-actions">
          <button type="button" className="btn btn-primary" disabled title="Coming soon">
            Donate (coming soon)
          </button>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="muted" style={{ margin: "0.75rem 0 0", fontSize: "0.85rem" }}>
          Payment checkout is a placeholder for now — thanks for your interest.
        </p>
      </div>
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
            required
            rows={10}
            value={cookies}
            onChange={(e) => setCookies(e.target.value)}
            placeholder="# Netscape HTTP Cookie File&#10;…"
            disabled={busy}
            spellCheck={false}
            style={{ fontFamily: "var(--mono)", fontSize: "0.85rem" }}
          />
        </div>

        <div className="form-group">
          <label htmlFor="donate-cookies-note">Optional note</label>
          <input
            id="donate-cookies-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            disabled={busy}
            placeholder="e.g. exported from Chrome, dummy account"
          />
        </div>

        <label
          style={{
            display: "flex",
            gap: "0.6rem",
            alignItems: "flex-start",
            marginBottom: "1rem",
            fontSize: "0.9rem",
          }}
        >
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            disabled={busy}
            style={{ marginTop: "0.2rem" }}
          />
          <span>
            I confirm this is a disposable account with no payment info, addresses, government ID,
            or important email. I understand CommercialBrainz will try to keep the cookie file safe,
            but I am responsible for what I submit. Cookies go into a backlog and may become active
            for YouTube metadata and fingerprint downloads when older cookies expire.
          </span>
        </label>

        {error && <p className="error">{error}</p>}

        <div className="report-dialog-actions">
          <button type="submit" className="btn btn-primary" disabled={busy || !cookies.trim() || !agreed}>
            {busy ? "Submitting…" : "Submit to backlog"}
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

  useEffect(() => {
    api
      .donateCookieBacklogStats()
      .then((stats) => setPendingCookies(stats.pending + stats.active))
      .catch(() => setPendingCookies(null));
  }, [flash]);

  return (
    <div style={{ maxWidth: 760 }}>
      <h1 className="page-title">Donate</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        CommercialBrainz is a volunteer project. Money, spare YouTube cookies, and your time all
        help keep the archive online and growing.
      </p>

      {flash && (
        <div className="card" style={{ marginBottom: "1.25rem", borderColor: "var(--success)" }}>
          <p style={{ margin: 0 }}>{flash}</p>
        </div>
      )}

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Domain</h2>
        <p>
          Help cover domain registration and DNS so the site name stays ours year after year.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => setModal("domain")}>
          Donate toward the domain
        </button>
      </section>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Cloud VM</h2>
        <p>
          Donate toward the cloud virtual machine that runs the site — API, workers, database, and
          storage for hashes and thumbnails.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => setModal("vm")}>
          Donate toward the VM
        </button>
      </section>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>YouTube cookies</h2>
        <p>
          YouTube often blocks anonymous scrapers. We use logged-in cookies so yt-dlp can pull
          metadata and download media for fingerprints. When a cookie jar expires, we move to the
          next one in the backlog.
        </p>
        <p>
          Please only donate cookies from a dummy account: created just for YouTube login, no
          payment methods, no personal mail, no identity documents. Submissions are encrypted at
          rest with a site seed (<code>COOKIE_ENCRYPTION_SEED</code>). We will behave and keep
          them as safe as we can — but you choose what you send.
        </p>
        {pendingCookies != null && (
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            Backlog currently holds {pendingCookies} usable donation
            {pendingCookies === 1 ? "" : "s"} (pending or active).
          </p>
        )}
        <button type="button" className="btn btn-primary" onClick={() => setModal("cookies")}>
          Donate cookies
        </button>
        <p className="muted" style={{ marginBottom: 0, marginTop: "0.75rem", fontSize: "0.85rem" }}>
          <a
            href="https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies"
            target="_blank"
            rel="noreferrer"
          >
            How to export cookies.txt
          </a>
        </p>
      </section>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Donate time</h2>
        <p>Not everyone can give money or cookies. Time helps just as much:</p>
        <ul style={{ paddingLeft: "1.2rem" }}>
          <li>
            Improve <Link to="/browse">metadata</Link> — titles, brands, decades, regions.
          </li>
          <li>
            <Link to="/voting">Vote</Link> on open edits so good submissions land faster.
          </li>
          <li>
            Grow into moderation — help review reports and keep quality high (ask a mod/admin after
            you have a track record).
          </li>
          <li>Write or fix documentation for contributors and API users.</li>
          <li>
            Help with coding. Much of the codebase is AI-assisted and needs human audit — and in
            places, replacement. If you enjoy FastAPI, React, Postgres, or yt-dlp plumbing, we would
            love a hand.
          </li>
        </ul>
        <p style={{ marginBottom: 0 }}>
          Start by <Link to="/register">registering</Link>, reading the{" "}
          <Link to="/terms">Terms</Link>, and introducing yourself on an edit or to a moderator.
        </p>
      </section>

      {modal === "domain" && (
        <DummyDonateModal
          title="Domain donation"
          body={
            <p style={{ margin: 0 }}>
              This would go toward renewing the CommercialBrainz domain and related DNS costs.
            </p>
          }
          onClose={() => setModal(null)}
        />
      )}
      {modal === "vm" && (
        <DummyDonateModal
          title="Cloud VM donation"
          body={
            <p style={{ margin: 0 }}>
              This would go toward the cloud VM that keeps the site, workers, and database running.
            </p>
          }
          onClose={() => setModal(null)}
        />
      )}
      {modal === "cookies" && (
        <CookieDonateModal
          onClose={() => setModal(null)}
          onSubmitted={(message) => setFlash(message)}
        />
      )}
    </div>
  );
}

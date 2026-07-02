import { useState } from "react";

const STORAGE_KEY = "commercialbrainz_dev_disclaimer_ack";

function hasAcknowledged(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export default function DevSiteDisclaimer() {
  const [visible, setVisible] = useState(() => !hasAcknowledged());

  if (!visible) return null;

  const acknowledge = () => {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // Private browsing may block storage; still dismiss for this session.
    }
    setVisible(false);
  };

  return (
    <div className="dev-disclaimer-overlay" role="dialog" aria-modal="true" aria-labelledby="dev-disclaimer-title">
      <div className="dev-disclaimer-card">
        <p className="dev-disclaimer-badge">Development environment</p>
        <h1 id="dev-disclaimer-title" className="dev-disclaimer-title">
          Test site only
        </h1>
        <p>
          This is a <strong>test site</strong>, not the real CommercialBrainz service. It is for
          development and evaluation only.
        </p>
        <ul className="dev-disclaimer-list">
          <li>Do not treat content or accounts here as production data.</li>
          <li>Submissions, votes, and uploads may be deleted at any time.</li>
          <li>Data will not be kept or migrated to a live site.</li>
        </ul>
        <button type="button" className="btn btn-primary dev-disclaimer-btn" onClick={acknowledge}>
          I understand — continue
        </button>
      </div>
    </div>
  );
}

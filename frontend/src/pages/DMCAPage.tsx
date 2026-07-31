import { useState } from "react";
import { useSearchParams } from "react-router";
import dmcaMd from "@site-docs/dmca.md?raw";
import { api } from "../api";
import SiteDocMarkdown from "../components/SiteDocMarkdown";

export default function DMCAPage() {
  const [params] = useSearchParams();
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    video_sbid: params.get("video") || "",
    claimant_name: "",
    claimant_email: "",
    claimant_address: "",
    claim_text: "",
    signature: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.submitDmca(form);
      setSubmitted(true);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (submitted) {
    return (
      <div className="card">
        <h2>DMCA Notice Submitted</h2>
        <p>Your takedown request has been received and will be reviewed by our moderation team.</p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 760 }}>
      <SiteDocMarkdown source={dmcaMd} file="dmca.md" className="card" />

      <form
        onSubmit={handleSubmit}
        className="card"
        style={{ maxWidth: 600, marginTop: "1.25rem" }}
      >
        <h2 style={{ marginTop: 0 }}>Submit a notice</h2>
        <div className="form-group">
          <label>Video CBID *</label>
          <input
            required
            value={form.video_sbid}
            onChange={(e) => setForm({ ...form, video_sbid: e.target.value })}
            placeholder="550e8400-e29b-41d4-a716-446655440000"
          />
        </div>
        <div className="form-group">
          <label>Your Name *</label>
          <input
            required
            value={form.claimant_name}
            onChange={(e) => setForm({ ...form, claimant_name: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Email *</label>
          <input
            required
            type="email"
            value={form.claimant_email}
            onChange={(e) => setForm({ ...form, claimant_email: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Address</label>
          <textarea
            value={form.claimant_address}
            onChange={(e) => setForm({ ...form, claimant_address: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Description of copyrighted work and infringement *</label>
          <textarea
            required
            minLength={20}
            value={form.claim_text}
            onChange={(e) => setForm({ ...form, claim_text: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Electronic Signature *</label>
          <input
            required
            value={form.signature}
            onChange={(e) => setForm({ ...form, signature: e.target.value })}
            placeholder="Your full legal name"
          />
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn btn-primary">
          Submit DMCA Notice
        </button>
      </form>
    </div>
  );
}

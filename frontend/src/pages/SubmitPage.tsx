import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api";

export default function SubmitPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    youtube_url: "",
    commercial_title: "",
    advertiser_name: "",
    year: "",
    language: "",
    region: "",
    transcript: "",
    slogan: "",
    tags: "",
    comment: "",
  });

  if (!user) {
    return (
      <div className="card">
        <p>You must <a href="/login">log in</a> to submit commercials.</p>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const edit = await api.submitVideo({
        youtube_url: form.youtube_url,
        commercial: {
          title: form.commercial_title,
          advertiser_name: form.advertiser_name || undefined,
          year: form.year ? parseInt(form.year) : undefined,
        },
        language: form.language || undefined,
        region: form.region || undefined,
        transcript: form.transcript || undefined,
        slogan: form.slogan || undefined,
        tags: form.tags ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
        comment: form.comment || undefined,
      });
      navigate(`/edits/${edit.id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">Submit Commercial Video</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        Submissions enter the edit queue for community voting (MusicBrainz-style).
        Mods may auto-apply edits instantly.
      </p>

      <form onSubmit={handleSubmit} className="card" style={{ maxWidth: 600 }}>
        <div className="form-group">
          <label>YouTube URL *</label>
          <input
            required
            value={form.youtube_url}
            onChange={(e) => setForm({ ...form, youtube_url: e.target.value })}
            placeholder="https://www.youtube.com/watch?v=..."
          />
        </div>
        <div className="form-group">
          <label>Commercial Title *</label>
          <input
            required
            value={form.commercial_title}
            onChange={(e) => setForm({ ...form, commercial_title: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Advertiser / Brand</label>
          <input
            value={form.advertiser_name}
            onChange={(e) => setForm({ ...form, advertiser_name: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Year</label>
          <input
            type="number"
            value={form.year}
            onChange={(e) => setForm({ ...form, year: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Language</label>
          <input
            value={form.language}
            onChange={(e) => setForm({ ...form, language: e.target.value })}
            placeholder="en"
          />
        </div>
        <div className="form-group">
          <label>Region</label>
          <input
            value={form.region}
            onChange={(e) => setForm({ ...form, region: e.target.value })}
            placeholder="US"
          />
        </div>
        <div className="form-group">
          <label>Slogan</label>
          <input
            value={form.slogan}
            onChange={(e) => setForm({ ...form, slogan: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Transcript</label>
          <textarea
            value={form.transcript}
            onChange={(e) => setForm({ ...form, transcript: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Tags (comma-separated)</label>
          <input
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
            placeholder="superbowl, automotive, humor"
          />
        </div>
        <div className="form-group">
          <label>Edit comment</label>
          <textarea
            value={form.comment}
            onChange={(e) => setForm({ ...form, comment: e.target.value })}
            placeholder="Source, context, or notes for voters..."
          />
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Submitting..." : "Submit for review"}
        </button>
      </form>
    </div>
  );
}

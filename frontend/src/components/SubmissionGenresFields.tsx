import {
  EMPTY_SUBMISSION_GENRES,
  GENRE_FLAG_LABELS,
  type SubmissionGenres,
} from "../utils/submissionGenres";

interface Props {
  value: SubmissionGenres;
  onChange: (genres: SubmissionGenres) => void;
}

export default function SubmissionGenresFields({ value, onChange }: Props) {
  const update = (patch: Partial<SubmissionGenres>) =>
    onChange({ ...value, ...patch });

  return (
    <fieldset style={{ border: "none", padding: 0, margin: "0 0 1rem" }}>
      <legend style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Genres & classification</legend>
      <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
        Optional context for voters — audience, placement, authenticity, and campaign type.
      </p>

      <div className="form-group">
        <label htmlFor="genre-age-range">Age range</label>
        <input
          id="genre-age-range"
          value={value.age_range}
          onChange={(e) => update({ age_range: e.target.value })}
          placeholder='e.g. "kids", "18-34", "all ages"'
        />
      </div>

      <div className="form-group">
        <label htmlFor="genre-target-channel">Channel it&apos;s for</label>
        <input
          id="genre-target-channel"
          value={value.target_channel}
          onChange={(e) => update({ target_channel: e.target.value })}
          placeholder="e.g. Nickelodeon, ESPN, local news"
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: "0.35rem 1rem",
          marginBottom: "0.75rem",
        }}
      >
        {GENRE_FLAG_LABELS.map(({ key, label }) => (
          <label key={key} style={{ display: "flex", gap: "0.45rem", alignItems: "center" }}>
            <input
              type="checkbox"
              checked={Boolean(value[key])}
              onChange={(e) => update({ [key]: e.target.checked } as Partial<SubmissionGenres>)}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>

      <div style={{ display: "grid", gap: "0.75rem" }}>
        <div className="form-group" style={{ margin: 0 }}>
          <label htmlFor="genre-holiday">Holiday</label>
          <input
            id="genre-holiday"
            value={value.holiday}
            onChange={(e) => update({ holiday: e.target.value })}
            placeholder="e.g. Christmas, Super Bowl Sunday"
          />
        </div>
        <div className="form-group" style={{ margin: 0 }}>
          <label htmlFor="genre-event">Event</label>
          <input
            id="genre-event"
            value={value.event}
            onChange={(e) => update({ event: e.target.value })}
            placeholder="e.g. Olympics, product launch"
          />
        </div>
        <div className="form-group" style={{ margin: 0 }}>
          <label htmlFor="genre-store">Store</label>
          <input
            id="genre-store"
            value={value.store}
            onChange={(e) => update({ store: e.target.value })}
            placeholder="e.g. grocery, big-box retail"
          />
        </div>
        <div className="form-group" style={{ margin: 0 }}>
          <label htmlFor="genre-service">Service</label>
          <input
            id="genre-service"
            value={value.service}
            onChange={(e) => update({ service: e.target.value })}
            placeholder="e.g. streaming, insurance, delivery"
          />
        </div>
      </div>
    </fieldset>
  );
}

export { EMPTY_SUBMISSION_GENRES };

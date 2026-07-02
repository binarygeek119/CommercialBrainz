import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth, isMod } from "../auth";
import { api } from "../api";
import BrandMetadataDiff, { hasMetadataChanges } from "../components/BrandMetadataDiff";
import BrandLogoMetadataDiff, { hasLogoMetadataChanges } from "../components/BrandLogoMetadataDiff";
import BrandLogoImage from "../components/BrandLogoImage";
import CommercialMetadataDiff, {
  hasCommercialMetadataChanges,
} from "../components/CommercialMetadataDiff";
import { formatLogoContext } from "../utils/brandLogos";

export default function EditDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [voteComment, setVoteComment] = useState("");

  const { data: edit, isLoading } = useQuery({
    queryKey: ["edit", id],
    queryFn: () => api.getEdit(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const fp = query.state.data?.fingerprint_preview;
      if (query.state.data?.status === "open" && fp?.status !== "completed" && fp?.status !== "failed") {
        return 5000;
      }
      return false;
    },
  });

  const { data: duplicates } = useQuery({
    queryKey: ["edit-duplicates", id],
    queryFn: () => api.getEditDuplicates(id!),
    enabled: !!id && edit?.fingerprint_preview?.status === "completed",
  });

  const handleVote = async (choice: string | null) => {
    if (!user) return;
    setError("");
    try {
      await api.vote(id!, choice, choice === null ? undefined : voteComment || undefined);
      queryClient.invalidateQueries({ queryKey: ["edit", id] });
      queryClient.invalidateQueries({ queryKey: ["open-edits"] });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (isLoading) return <p className="muted">Loading...</p>;
  if (!edit) return null;

  const yesVotes = edit.votes.filter((v) => v.choice === "yes").length;
  const noVotes = edit.votes.filter((v) => v.choice === "no").length;
  const viewerVote = user ? edit.votes.find((v) => v.voter_id === user.id) : undefined;
  const fp = edit.fingerprint_preview;
  const brandEditId = edit.after_state.brand_edit_id as string | undefined;
  const viewerIsMod = isMod(user);

  return (
    <div>
      <h1 className="page-title">Edit #{edit.id.slice(0, 8)}</h1>
      <div className="card">
        <div className="flex-between">
          <span className={`badge badge-${edit.status === "open" ? "open" : edit.status}`}>
            {edit.status}
          </span>
          <span className="mono muted">{edit.edit_type}</span>
        </div>
        {edit.comment && <p style={{ marginTop: "1rem" }}>{edit.comment}</p>}
        {edit.editor_username && (
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            Submitted by{" "}
            <Link to={`/user/${encodeURIComponent(edit.editor_username)}`}>
              {edit.editor_username}
            </Link>
          </p>
        )}
        <p className="muted">
          Expires: {new Date(edit.expires_at).toLocaleString()} · Yes: {yesVotes} · No: {noVotes}
          {edit.status === "open" && (
            <>
              {" "}
              · {viewerIsMod
                ? "Your yes/no vote applies or rejects this edit immediately"
                : "Edits with no votes after 14 days are auto-approved; otherwise a moderator decides"}
            </>
          )}
        </p>
        {brandEditId && (
          <p style={{ marginTop: "0.75rem" }}>
            This submission includes a{" "}
            <Link to={`/edits/${brandEditId}`}>new brand awaiting approval</Link>.
          </p>
        )}
      </div>

      {edit.edit_type === "create_advertiser" && (
        <>
          <div className="card">
            <h3>Brand proposal</h3>
            <p>
              <strong>{(edit.after_state.name as string) || "Unnamed brand"}</strong>
            </p>
            <p className="muted" style={{ marginTop: "0.5rem" }}>
              Approved brands appear in search when a moderator or admin votes yes on this edit.
            </p>
          </div>
          {hasMetadataChanges({}, edit.after_state) && (
            <BrandMetadataDiff after={edit.after_state} />
          )}
        </>
      )}

      {edit.edit_type === "edit_advertiser" &&
        hasMetadataChanges(edit.before_state ?? {}, edit.after_state) && (
          <BrandMetadataDiff before={edit.before_state ?? {}} after={edit.after_state} />
        )}

      {edit.edit_type === "edit_commercial" &&
        hasCommercialMetadataChanges(edit.before_state ?? {}, edit.after_state) && (
          <CommercialMetadataDiff before={edit.before_state ?? {}} after={edit.after_state} />
        )}

      {(edit.edit_type === "add_advertiser_logo" ||
        edit.edit_type === "edit_advertiser_logo" ||
        (edit.edit_type === "edit_advertiser" &&
          typeof edit.after_state.logo_url === "string")) && (
        <div className="card">
          <h3>
            {edit.edit_type === "add_advertiser_logo"
              ? "Proposed logo version"
              : edit.edit_type === "edit_advertiser_logo"
                ? "Logo metadata update"
                : "Proposed brand logo"}
          </h3>
          {(edit.edit_type === "add_advertiser_logo" ||
            edit.edit_type === "edit_advertiser_logo") && (
            <p style={{ marginBottom: "0.75rem" }}>
              <strong>{formatLogoContext(edit.after_state)}</strong>
            </p>
          )}
          {typeof edit.after_state.notes === "string" && edit.after_state.notes && (
            <p className="muted" style={{ marginBottom: "0.75rem" }}>
              {edit.after_state.notes}
            </p>
          )}
          {typeof edit.after_state.image_url === "string" && (
            <BrandLogoImage
              src={edit.after_state.image_url as string}
              alt="Proposed logo"
              size="preview"
            />
          )}
          {!edit.after_state.image_url && typeof edit.after_state.logo_url === "string" && (
            <BrandLogoImage
              src={edit.after_state.logo_url as string}
              alt="Proposed logo"
              size="preview"
            />
          )}
          {edit.edit_type === "edit_advertiser" &&
            typeof edit.before_state?.logo_url === "string" && (
            <>
              <p className="muted" style={{ marginTop: "0.75rem" }}>
                Current main logo:
              </p>
              <BrandLogoImage
                src={edit.before_state.logo_url as string}
                alt="Current logo"
                size="xs"
              />
            </>
          )}
          {edit.edit_type === "add_advertiser_logo" && (
            <p className="muted" style={{ marginTop: "0.75rem" }}>
              If approved, this joins the brand&apos;s logo gallery. Users then vote on popularity
              to decide which version is the main logo site-wide.
            </p>
          )}
        </div>
      )}

      {edit.edit_type === "edit_advertiser_logo" &&
        hasLogoMetadataChanges(edit.before_state ?? {}, edit.after_state) && (
          <BrandLogoMetadataDiff before={edit.before_state ?? {}} after={edit.after_state} />
        )}

      {edit.edit_type === "edit_video" && typeof edit.after_state.thumbnail_url === "string" && (
        <div className="card">
          <h3>Proposed thumbnail</h3>
          <img
            src={edit.after_state.thumbnail_url as string}
            alt="Proposed thumbnail"
            style={{ width: "100%", maxWidth: 480, borderRadius: 4 }}
          />
          {typeof edit.before_state?.thumbnail_url === "string" && (
            <>
              <p className="muted" style={{ marginTop: "0.75rem" }}>
                Current thumbnail:
              </p>
              <img
                src={edit.before_state.thumbnail_url as string}
                alt="Current thumbnail"
                style={{ width: "100%", maxWidth: 240, borderRadius: 4, marginTop: "0.35rem" }}
              />
            </>
          )}
        </div>
      )}

      {edit.edit_type === "create_video" && (
        <div className="card">
          <h3>Fingerprint preview</h3>
          {!fp && <p className="muted">Queued for fingerprinting…</p>}
          {fp && (
            <>
              <p className="muted">Status: {fp.status}</p>
              {fp.duration_sec != null && (
                <p className="muted">
                  Duration: {fp.duration_sec.toFixed(1)}s
                  {typeof fp.probe?.resolution === "string" ? ` · ${fp.probe.resolution}` : ""}
                  {typeof fp.probe?.fps === "number" ? ` · ${fp.probe.fps} fps` : ""}
                </p>
              )}
              {(fp.probe?.video_codec || fp.probe?.audio_codec) && (
                <p className="muted" style={{ fontSize: "0.9rem" }}>
                  {fp.probe?.video_codec ? `Video: ${fp.probe.video_codec}` : ""}
                  {fp.probe?.video_codec && fp.probe?.audio_codec ? " · " : ""}
                  {fp.probe?.audio_codec ? `Audio: ${fp.probe.audio_codec}` : ""}
                  {typeof fp.probe?.audio_channels === "number"
                    ? ` (${fp.probe.audio_channels}ch`
                    : ""}
                  {typeof fp.probe?.audio_sample_rate === "number"
                    ? ` @ ${fp.probe.audio_sample_rate} Hz)`
                    : typeof fp.probe?.audio_channels === "number"
                      ? ")"
                      : ""}
                </p>
              )}
              {fp.probe?.audio_analysis &&
                typeof fp.probe.audio_analysis === "object" &&
                (fp.probe.audio_analysis as Record<string, unknown>).mean_volume_db != null && (
                  <p className="muted" style={{ fontSize: "0.9rem" }}>
                    Loudness: mean {(fp.probe.audio_analysis as Record<string, number>).mean_volume_db} dB
                    {(fp.probe.audio_analysis as Record<string, number>).max_volume_db != null &&
                      ` · peak ${(fp.probe.audio_analysis as Record<string, number>).max_volume_db} dB`}
                  </p>
                )}
              {fp.phash && <p className="mono">pHash: {fp.phash}</p>}
              {fp.file_sha256 && (
                <p className="mono" style={{ wordBreak: "break-all" }}>
                  SHA256: {fp.file_sha256}
                </p>
              )}
              {fp.audio_fingerprint && (
                <p className="mono" style={{ wordBreak: "break-all" }}>
                  Chromaprint: {fp.audio_fingerprint.slice(0, 64)}…
                </p>
              )}
              {fp.error_message && <p className="error">{fp.error_message}</p>}
            </>
          )}
          {duplicates && duplicates.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <h4>Possible duplicates</h4>
              <ul>
                {duplicates.map((d) => (
                  <li key={d.video_sbid}>
                    <Link to={`/video/${d.video_sbid}`}>{d.youtube_id}</Link>
                    {" "}(distance {d.hamming_distance})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h3>Proposed changes</h3>
        <pre style={{ overflow: "auto", fontSize: "0.85rem", color: "var(--text-muted)" }}>
          {JSON.stringify(edit.after_state, null, 2)}
        </pre>
      </div>

      {edit.votes.length > 0 && (
        <div className="card">
          <h3>Votes</h3>
          {edit.votes.map((v) => (
            <p key={v.id}>
              <strong>{v.choice}</strong>
              {v.comment && ` — ${v.comment}`}
            </p>
          ))}
        </div>
      )}

      {edit.status === "open" && user && (
        <div className="card">
          <h3>{viewerIsMod ? "Moderator vote" : "Cast your vote"}</h3>
          {viewerIsMod ? (
            <p className="muted" style={{ marginBottom: "0.75rem" }}>
              Yes applies this edit right away. No rejects it. Community votes do not affect the outcome.
            </p>
          ) : (
            <p className="muted" style={{ marginBottom: "0.75rem" }}>
              Community votes are recorded for feedback. If nobody votes within 14 days, the edit
              is auto-approved. Otherwise a moderator or admin yes/no vote decides the edit.
            </p>
          )}
          <div className="form-group">
            <label>Comment (optional)</label>
            <textarea value={voteComment} onChange={(e) => setVoteComment(e.target.value)} />
          </div>
          <div className="vote-buttons">
            <button
              className={`btn btn-success${viewerVote?.choice === "yes" ? " active" : ""}`}
              onClick={() => handleVote("yes")}
            >
              Yes
            </button>
            <button
              className={`btn btn-danger${viewerVote?.choice === "no" ? " active" : ""}`}
              onClick={() => handleVote("no")}
            >
              No
            </button>
            {!viewerIsMod && (
              <button
                className={`btn btn-secondary${viewerVote?.choice === "abstain" ? " active" : ""}`}
                onClick={() => handleVote("abstain")}
              >
                Abstain
              </button>
            )}
            {viewerVote && (
              <button className="btn btn-secondary" onClick={() => handleVote(null)}>
                Remove vote
              </button>
            )}
          </div>
          {error && <p className="error">{error}</p>}
        </div>
      )}

      {!user && edit.status === "open" && (
        <p className="muted"><a href="/login">Log in</a> to vote on this edit.</p>
      )}
    </div>
  );
}

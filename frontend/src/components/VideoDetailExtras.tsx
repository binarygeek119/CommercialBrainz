import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth, canSubmit } from "../auth";
import VideoThumbnailUpload from "./VideoThumbnailUpload";
import { formatSubmissionGenres, type SubmissionGenres } from "../utils/submissionGenres";

interface Props {
  videoSbid: string;
}

export default function VideoDetailExtras({ videoSbid }: Props) {
  const { user } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["video", videoSbid],
    queryFn: () => api.getVideo(videoSbid),
    refetchInterval: (query) =>
      query.state.data?.hash_status === "pending" ? 10000 : false,
  });

  if (isLoading) return <p className="muted" style={{ fontSize: "0.85rem" }}>Loading video details…</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data) return null;

  const hashError =
    typeof data.metadata?.hash_error === "string" ? data.metadata.hash_error : null;
  const genreLines = formatSubmissionGenres(data.metadata?.genres as SubmissionGenres | undefined);

  return (
    <div style={{ marginTop: "0.75rem" }}>
      {data.youtube_url && (
        <p style={{ marginBottom: "0.75rem" }}>
          <a href={data.youtube_url} target="_blank" rel="noreferrer noopener">
            Watch on YouTube ({data.youtube_id})
          </a>
        </p>
      )}

      {data.visibility !== "public" && (
        <p className="error">This link is not publicly available ({data.visibility}).</p>
      )}

      {user && canSubmit(user) && data.visibility === "public" && (
        <VideoThumbnailUpload videoSbid={videoSbid} />
      )}

      <div className="grid grid-2" style={{ marginTop: "0.75rem" }}>
        {(genreLines.length > 0 || data.tags?.length || data.credits?.length) && (
          <div className="card" style={{ margin: 0 }}>
            {genreLines.length > 0 && (
              <>
                <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Genres</h4>
                <ul style={{ margin: "0 0 0.75rem", paddingLeft: "1.1rem" }}>
                  {genreLines.map((line) => (
                    <li key={line} className="muted" style={{ fontSize: "0.9rem" }}>
                      {line}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {data.tags && data.tags.length > 0 && (
              <>
                <h4 style={{ margin: "0 0 0.35rem", fontSize: "0.95rem" }}>Tags</h4>
                <p style={{ margin: "0 0 0.75rem" }}>{data.tags.map((t) => `#${t}`).join(" ")}</p>
              </>
            )}
            {data.credits && data.credits.length > 0 && (
              <>
                <h4 style={{ margin: "0 0 0.35rem", fontSize: "0.95rem" }}>Credits</h4>
                {data.credits.map((c, i) => (
                  <p key={i} className="muted" style={{ margin: "0.15rem 0" }}>
                    {c.role}: {c.name}
                  </p>
                ))}
              </>
            )}
          </div>
        )}

        <div className="card" style={{ margin: 0 }}>
          <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Media fingerprints</h4>
          <p className="muted" style={{ marginBottom: "0.5rem", fontSize: "0.85rem" }}>
            Status: {data.hash_status || "pending"}
            {data.hashed_at && ` · computed ${new Date(data.hashed_at).toLocaleString()}`}
          </p>
          {data.phash && (
            <p className="mono" style={{ fontSize: "0.85rem" }}>
              pHash: {data.phash}
            </p>
          )}
          {data.file_sha256 && (
            <p className="mono" style={{ fontSize: "0.85rem", wordBreak: "break-all" }}>
              SHA256: {data.file_sha256}
            </p>
          )}
          {data.audio_fingerprint && (
            <p className="mono" style={{ fontSize: "0.85rem", wordBreak: "break-all" }}>
              Chromaprint: {data.audio_fingerprint.slice(0, 80)}
              {data.audio_fingerprint.length > 80 ? "…" : ""}
            </p>
          )}
          {!data.phash && data.hash_status !== "failed" && !hashError && (
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              Fingerprinting in progress or not yet started.
            </p>
          )}
          {hashError && data.hash_status !== "failed" && (
            <>
              <p className="error">{hashError}</p>
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                Retrying automatically every few minutes.
              </p>
            </>
          )}
          {data.hash_status === "failed" && (
            <>
              <p className="error">
                {hashError || "Fingerprinting failed after multiple attempts."}
              </p>
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                An admin can retry from Admin → Fingerprints or Fingerprint queue.
              </p>
            </>
          )}
        </div>
      </div>

      {data.transcript && (
        <div className="card" style={{ marginTop: "0.75rem" }}>
          <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Transcript</h4>
          <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{data.transcript}</p>
        </div>
      )}

      <p style={{ marginTop: "0.75rem", marginBottom: 0, fontSize: "0.85rem" }}>
        <Link to={`/dmca?video=${data.sbid}`}>Report DMCA takedown</Link>
      </p>
    </div>
  );
}

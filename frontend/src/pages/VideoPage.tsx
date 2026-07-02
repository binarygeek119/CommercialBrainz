import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth, canSubmit } from "../auth";
import VideoThumbnailUpload from "../components/VideoThumbnailUpload";
import { formatRegionDisplay } from "../data/regions";
import { videoThumbnailUrl } from "../utils/videoThumbnail";

export default function VideoPage() {
  const { sbid } = useParams<{ sbid: string }>();
  const { user } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["video", sbid],
    queryFn: () => api.getVideo(sbid!),
    enabled: !!sbid,
    refetchInterval: (query) =>
      query.state.data?.hash_status === "pending" ? 10000 : false,
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data) return null;

  const thumb = videoThumbnailUrl(data);
  const hashError =
    typeof data.metadata?.hash_error === "string" ? data.metadata.hash_error : null;

  return (
    <div>
      <h1 className="page-title">{data.commercial?.title || data.slogan || "Video"}</h1>

      {thumb && (
        <div className="card" style={{ marginBottom: "1rem", padding: 0, overflow: "hidden" }}>
          <img
            src={thumb}
            alt=""
            style={{ width: "100%", display: "block", maxHeight: 420, objectFit: "cover" }}
          />
        </div>
      )}

      {data.youtube_url && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <a href={data.youtube_url} target="_blank" rel="noreferrer">
            Watch on YouTube ({data.youtube_id})
          </a>
        </div>
      )}

      {user && canSubmit(user) && data.visibility === "public" && sbid && (
        <VideoThumbnailUpload videoSbid={sbid} />
      )}

      {data.visibility !== "public" && (
        <p className="error">This video link is not publicly available ({data.visibility}).</p>
      )}

      <div className="grid grid-2">
        <div className="card">
          <h3>Details</h3>
          {data.advertiser && (
            <p>
              Advertiser:{" "}
              <Link to={`/advertiser/${data.advertiser.sbid}`}>{data.advertiser.name}</Link>
            </p>
          )}
          {data.commercial && (
            <p>
              Commercial:{" "}
              <Link to={`/commercial/${data.commercial.sbid}`}>{data.commercial.title}</Link>
            </p>
          )}
          {data.language && <p>Language: {data.language}</p>}
          {formatRegionDisplay(data.region, data.sub_region) && (
            <p>Region: {formatRegionDisplay(data.region, data.sub_region)}</p>
          )}
          {data.duration_ms && <p>Duration: {Math.round(data.duration_ms / 1000)}s</p>}
          {data.slogan && <p>Slogan: {data.slogan}</p>}
        </div>

        <div className="card">
          <h3>Tags & Credits</h3>
          {data.tags && data.tags.length > 0 && (
            <p>{data.tags.map((t) => `#${t}`).join(" ")}</p>
          )}
          {data.credits && data.credits.map((c, i) => (
            <p key={i} className="muted">
              {c.role}: {c.name}
            </p>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Media Fingerprints</h3>
        <p className="muted" style={{ marginBottom: "0.75rem" }}>
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
          <p className="muted">Fingerprinting in progress or not yet started.</p>
        )}
        {hashError && data.hash_status !== "failed" && (
          <>
            <p className="error">{hashError}</p>
            <p className="muted">Retrying automatically every few minutes.</p>
          </>
        )}
        {data.hash_status === "failed" && (
          <>
            <p className="error">
              {hashError || "Fingerprinting failed after multiple attempts."}
            </p>
            <p className="muted">
              An admin can retry from Admin → Fingerprints or Fingerprint queue.
            </p>
          </>
        )}
      </div>

      {data.transcript && (
        <div className="card">
          <h3>Transcript</h3>
          <p>{data.transcript}</p>
        </div>
      )}

      <p style={{ marginTop: "1rem" }}>
        <Link to={`/dmca?video=${data.sbid}`}>Report DMCA takedown</Link>
      </p>
    </div>
  );
}

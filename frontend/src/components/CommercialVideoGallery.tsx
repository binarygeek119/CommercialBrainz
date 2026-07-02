import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type CommercialDetail, type Video } from "../api";
import { useAuth } from "../auth";
import AddCommercialLinkForm from "./AddCommercialLinkForm";
import CommercialVideoEntry from "./CommercialVideoEntry";

interface Props {
  commercial: CommercialDetail;
}

function VideoLinkCard({
  video,
  commercialSbid,
  canVote,
  onVoted,
}: {
  video: Video;
  commercialSbid: string;
  canVote: boolean;
  onVoted: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const castVote = async (choice: "up" | "down" | null) => {
    setLoading(true);
    setError("");
    try {
      await api.voteCommercialVideoPopularity(commercialSbid, video.sbid, choice);
      onVoted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <CommercialVideoEntry video={video} />
      <div style={{ padding: "0 0.75rem 0.75rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            Popularity: {video.popularity_score != null && video.popularity_score > 0 ? "+" : ""}
            {video.popularity_score ?? 0}
          </span>
          {canVote && (
            <>
              <button
                type="button"
                className={`btn btn-secondary${video.viewer_vote === "up" ? " active" : ""}`}
                disabled={loading}
                onClick={() => castVote(video.viewer_vote === "up" ? null : "up")}
                style={{ padding: "0.2rem 0.55rem", fontSize: "0.85rem" }}
              >
                ▲ Up
              </button>
              <button
                type="button"
                className={`btn btn-secondary${video.viewer_vote === "down" ? " active" : ""}`}
                disabled={loading}
                onClick={() => castVote(video.viewer_vote === "down" ? null : "down")}
                style={{ padding: "0.2rem 0.55rem", fontSize: "0.85rem" }}
              >
                ▼ Down
              </button>
            </>
          )}
          <Link to={`/video/${video.sbid}`} className="btn btn-secondary" style={{ fontSize: "0.85rem" }}>
            Open video page
          </Link>
        </div>
        {error && <p className="error" style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>{error}</p>}
      </div>
    </div>
  );
}

export default function CommercialVideoGallery({ commercial }: Props) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data: videos = commercial.videos ?? [], isLoading, error } = useQuery({
    queryKey: ["commercial-videos", commercial.sbid],
    queryFn: () => api.getCommercialVideos(commercial.sbid),
    initialData: commercial.videos,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["commercial-videos", commercial.sbid] });
    queryClient.invalidateQueries({ queryKey: ["commercial", commercial.sbid] });
  };

  return (
    <section style={{ marginTop: "1.5rem" }}>
      <h2>YouTube links</h2>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        A commercial can have many YouTube links — different cuts, lengths, edits, or backup uploads.
        Each link is fingerprinted separately. After community approval, vote on which link should be
        the <strong>main link</strong> for this commercial (highest net score wins).
      </p>

      <AddCommercialLinkForm commercial={commercial} onSubmitted={refresh} />

      {isLoading && !videos.length && <p className="muted">Loading links…</p>}
      {error && <p className="error">{(error as Error).message}</p>}

      {videos.length > 0 ? (
        <div className="stack" style={{ marginTop: "1.25rem" }}>
          {videos.map((video) => (
            <VideoLinkCard
              key={video.sbid}
              video={video}
              commercialSbid={commercial.sbid}
              canVote={!!user}
              onVoted={refresh}
            />
          ))}
        </div>
      ) : (
        !isLoading && <p className="muted" style={{ marginTop: "1rem" }}>No public links yet.</p>
      )}

      {!user && videos.length > 0 && (
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          <Link to="/login">Log in</Link> to vote on which link should be main.
        </p>
      )}
    </section>
  );
}

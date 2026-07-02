import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type CommercialDetail, type Video } from "../api";
import { useAuth, canSubmit } from "../auth";
import AddCommercialLinkForm from "./AddCommercialLinkForm";
import SplitCommercialLinkForm from "./SplitCommercialLinkForm";
import CommercialVideoEntry from "./CommercialVideoEntry";
import VideoDetailExtras from "./VideoDetailExtras";

interface Props {
  commercial: CommercialDetail;
  selectedVideoSbid: string | null;
  onSelectVideo: (videoSbid: string) => void;
}

function VideoLinkCard({
  video,
  commercial,
  canVote,
  canSplit,
  selected,
  onSelect,
  onVoted,
  onSplitSubmitted,
}: {
  video: Video;
  commercial: CommercialDetail;
  canVote: boolean;
  canSplit: boolean;
  selected: boolean;
  onSelect: () => void;
  onVoted: () => void;
  onSplitSubmitted: () => void;
}) {
  const commercialSbid = commercial.sbid;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showSplit, setShowSplit] = useState(false);

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
    <div id={`video-${video.sbid}`}>
      <CommercialVideoEntry
        video={video}
        commercialSbid={commercialSbid}
        selected={selected}
        onSelect={onSelect}
      />
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
          {!selected && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: "0.85rem" }}
              onClick={onSelect}
            >
              View details
            </button>
          )}
          {canSplit && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: "0.85rem" }}
              onClick={() => setShowSplit((open) => !open)}
            >
              {showSplit ? "Cancel split" : "Split to own commercial"}
            </button>
          )}
        </div>
        {error && <p className="error" style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>{error}</p>}
      </div>
      {showSplit && canSplit && (
        <SplitCommercialLinkForm
          commercial={commercial}
          video={video}
          onSubmitted={() => {
            setShowSplit(false);
            onSplitSubmitted();
          }}
        />
      )}
      {selected && <div style={{ padding: "0 0.75rem 0.75rem" }}><VideoDetailExtras videoSbid={video.sbid} /></div>}
    </div>
  );
}

export default function CommercialVideoGallery({
  commercial,
  selectedVideoSbid,
  onSelectVideo,
}: Props) {
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

  const canSplit = !!user && canSubmit(user) && videos.length >= 2;

  return (
    <section style={{ marginTop: "1.5rem" }}>
      <h2>YouTube links</h2>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        A commercial has one <strong>master link</strong> (main YouTube upload) and optional{" "}
        <strong>sub links</strong> (alternate cuts, mirrors, regional copies). Sub links inherit
        metadata from the master; you only specify what differs. Popularity votes pick the master
        link. If a sub link is really a separate commercial, submit a{" "}
        <strong>split proposal</strong> for community vote (20+ yes votes, or after 3 months).
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
              commercial={commercial}
              canVote={!!user}
              canSplit={canSplit}
              selected={video.sbid === selectedVideoSbid}
              onSelect={() => onSelectVideo(video.sbid)}
              onVoted={refresh}
              onSplitSubmitted={refresh}
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

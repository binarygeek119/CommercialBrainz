import { useState } from "react";
import { Link } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type DuplicateIssue,
  type DuplicateVoteChoice,
  type Video,
} from "../api";
import { useAuth, canSubmit } from "../auth";
import { commercialUrl } from "../utils/commercialUrls";
import { videoThumbnailUrl } from "../utils/videoThumbnail";
import { videoDisplayTitle } from "../utils/videoMetadata";

const ACTIONS: { choice: DuplicateVoteChoice; label: string; help: string }[] = [
  {
    choice: "add_as_sub_link",
    label: "Add as sub link",
    help: "Move this upload onto the other commercial as a sub link.",
  },
  {
    choice: "remove_from_database",
    label: "Remove from database",
    help: "Hide this upload (removed visibility).",
  },
  {
    choice: "make_master_link",
    label: "Make master link",
    help: "Keep both on this video’s commercial and make it the master link.",
  },
];

function tallyFor(
  issue: DuplicateIssue,
  choice: DuplicateVoteChoice,
  subjectId: string
): number {
  return (
    issue.tallies.find((t) => t.choice === choice && t.subject_video_id === subjectId)
      ?.count ?? 0
  );
}

function VideoSide({
  video,
  issue,
  selectedSubject,
  onSelectSubject,
}: {
  video: Video;
  issue: DuplicateIssue;
  selectedSubject: string | null;
  onSelectSubject: (id: string) => void;
}) {
  const thumb = videoThumbnailUrl(video);
  const selected = selectedSubject === video.sbid;
  return (
    <button
      type="button"
      className="card"
      onClick={() => onSelectSubject(video.sbid)}
      style={{
        margin: 0,
        textAlign: "left",
        cursor: "pointer",
        border: selected ? "2px solid var(--accent)" : undefined,
        width: "100%",
      }}
    >
      {thumb ? (
        <img
          src={thumb}
          alt=""
          style={{ width: "100%", maxHeight: 180, objectFit: "cover", display: "block" }}
        />
      ) : (
        <div className="video-card-thumb-placeholder" style={{ height: 120 }} />
      )}
      <h3 style={{ margin: "0.75rem 0 0.35rem", fontSize: "1rem" }}>
        {videoDisplayTitle(video)}
      </h3>
      <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
        {video.is_main ? "Master link · " : "Sub link · "}
        score {video.popularity_score ?? 0}
      </p>
      <p style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>
        <Link
          to={commercialUrl(video.commercial_id, video.sbid)}
          onClick={(e) => e.stopPropagation()}
        >
          Open commercial
        </Link>
        {video.youtube_url ? (
          <>
            {" · "}
            <a
              href={video.youtube_url}
              target="_blank"
              rel="noreferrer noopener"
              onClick={(e) => e.stopPropagation()}
            >
              YouTube
            </a>
          </>
        ) : null}
      </p>
      <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.8rem" }}>
        Votes targeting this side:{" "}
        {ACTIONS.map((a) => tallyFor(issue, a.choice, video.sbid)).reduce((a, b) => a + b, 0)}
      </p>
    </button>
  );
}

function DuplicateIssueCard({
  issue,
  canVote,
}: {
  issue: DuplicateIssue;
  canVote: boolean;
}) {
  const queryClient = useQueryClient();
  const [subjectId, setSubjectId] = useState<string | null>(
    issue.my_vote?.subject_video_id ?? null
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!issue.video_a || !issue.video_b) {
    return (
      <div className="card">
        <p className="muted">This duplicate issue is missing video data.</p>
      </div>
    );
  }

  const cast = async (choice: DuplicateVoteChoice) => {
    if (!subjectId) {
      setError("Select which video the action applies to.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.voteDuplicateIssue(issue.id, choice, subjectId);
      await queryClient.invalidateQueries({ queryKey: ["duplicate-issues"] });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const clearVote = async () => {
    setBusy(true);
    setError("");
    try {
      await api.clearDuplicateVote(issue.id);
      setSubjectId(null);
      await queryClient.invalidateQueries({ queryKey: ["duplicate-issues"] });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <div className="flex-between" style={{ marginBottom: "0.75rem" }}>
        <div>
          <span className="badge badge-open">open</span>
          <span className="muted" style={{ marginLeft: "0.5rem", fontSize: "0.85rem" }}>
            Match: {(issue.match_types || []).join(", ") || issue.best_match_type || "hash"}
            {issue.hamming_distance != null ? ` · distance ${issue.hamming_distance}` : ""}
            {" · "}
            {issue.vote_count}/{issue.vote_threshold} votes to resolve
          </span>
        </div>
      </div>

      <p className="muted" style={{ marginTop: 0 }}>
        Are these the same commercial upload? Select the video your action should apply to, then
        vote.
      </p>

      <div className="grid grid-2" style={{ marginBottom: "1rem" }}>
        <VideoSide
          video={issue.video_a}
          issue={issue}
          selectedSubject={subjectId}
          onSelectSubject={setSubjectId}
        />
        <VideoSide
          video={issue.video_b}
          issue={issue}
          selectedSubject={subjectId}
          onSelectSubject={setSubjectId}
        />
      </div>

      {canVote ? (
        <div className="stack" style={{ gap: "0.5rem" }}>
          {!subjectId && (
            <p className="muted" style={{ margin: 0, fontSize: "0.9rem" }}>
              Click a video above to choose the subject of your vote.
            </p>
          )}
          {ACTIONS.map((action) => {
            const count = subjectId ? tallyFor(issue, action.choice, subjectId) : 0;
            const mine =
              issue.my_vote?.choice === action.choice &&
              issue.my_vote?.subject_video_id === subjectId;
            return (
              <div key={action.choice} className="flex-between" style={{ gap: "0.75rem" }}>
                <div style={{ minWidth: 0 }}>
                  <strong>{action.label}</strong>
                  <p className="muted" style={{ margin: "0.15rem 0 0", fontSize: "0.85rem" }}>
                    {action.help}
                    {subjectId ? ` · ${count} vote${count === 1 ? "" : "s"}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  className={`btn ${mine ? "btn-primary" : "btn-secondary"}`}
                  disabled={busy || !subjectId}
                  onClick={() => void cast(action.choice)}
                >
                  {mine ? "Your vote" : "Vote"}
                </button>
              </div>
            );
          })}
          {issue.my_vote && (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => void clearVote()}
              style={{ alignSelf: "flex-start" }}
            >
              Clear my vote
            </button>
          )}
        </div>
      ) : (
        <p className="muted" style={{ marginBottom: 0 }}>
          <Link to="/login">Log in</Link> with submit access to vote on duplicates.
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

export default function DuplicatesPage() {
  const { user } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["duplicate-issues"],
    queryFn: () => api.listDuplicateIssues(),
    refetchInterval: 15000,
  });

  const issues = data?.items ?? [];

  return (
    <div>
      <h1 className="page-title">Possible duplicates</h1>
      <p className="muted" style={{ marginBottom: "1.5rem", maxWidth: 720 }}>
        After fingerprinting, hash matches appear here. Submitters vote what to do with one of the
        two uploads. When a choice reaches the vote threshold, it is applied and the issue leaves
        this page. If a new match joins the set, voting starts over.
      </p>

      {isLoading && <p className="muted">Loading…</p>}
      {error && <p className="error">{(error as Error).message}</p>}

      <div className="stack">
        {issues.map((issue) => (
          <DuplicateIssueCard
            key={issue.id}
            issue={issue}
            canVote={Boolean(user && canSubmit(user))}
          />
        ))}
        {!isLoading && issues.length === 0 && (
          <p className="muted">No open duplicate issues right now.</p>
        )}
      </div>
    </div>
  );
}

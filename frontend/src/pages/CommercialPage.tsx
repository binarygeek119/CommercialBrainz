import { useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth, canSubmit } from "../auth";
import CommercialMetadataForm from "../components/CommercialMetadataForm";
import CommercialMetadataDisplay from "../components/CommercialMetadataDisplay";
import CommercialVideoGallery from "../components/CommercialVideoGallery";
import { videoThumbnailUrl } from "../utils/videoThumbnail";
import { videoDisplayTitle } from "../utils/videoMetadata";

export default function CommercialPage() {
  const { sbid } = useParams<{ sbid: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const [showMetadataForm, setShowMetadataForm] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["commercial", sbid],
    queryFn: () => api.getCommercial(sbid!),
    enabled: !!sbid,
  });

  const videos = data?.videos ?? [];
  const selectedFromUrl = searchParams.get("video");

  const selectedVideoSbid = useMemo(() => {
    if (!videos.length) return null;
    if (selectedFromUrl && videos.some((v) => v.sbid === selectedFromUrl)) {
      return selectedFromUrl;
    }
    return videos.find((v) => v.is_main)?.sbid ?? videos[0]?.sbid ?? null;
  }, [videos, selectedFromUrl]);

  const selectedVideo = videos.find((v) => v.sbid === selectedVideoSbid) ?? null;

  const selectVideo = (videoSbid: string) => {
    setSearchParams({ video: videoSbid }, { replace: true });
  };

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data) return null;

  const heroThumb = selectedVideo ? videoThumbnailUrl(selectedVideo) : null;

  return (
    <div>
      <div className="flex-between" style={{ alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h1 className="page-title" style={{ marginTop: 0 }}>
            {data.title}
          </h1>
          {data.campaign_name && data.campaign_name !== data.title && (
            <p className="muted">{data.campaign_name}</p>
          )}
          {selectedVideo && (
            <p className="muted" style={{ marginTop: "0.35rem" }}>
              Viewing: <strong>{videoDisplayTitle(selectedVideo)}</strong>
              {selectedVideo.is_main && (
                <span className="badge badge-open" style={{ marginLeft: "0.5rem", textTransform: "none" }}>
                  Main link
                </span>
              )}
            </p>
          )}
        </div>
        {user && canSubmit(user) && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowMetadataForm((open) => !open)}
          >
            {showMetadataForm ? "Hide metadata editor" : "Edit metadata"}
          </button>
        )}
      </div>

      {heroThumb && selectedVideo && (
        <div className="card" style={{ marginTop: "1rem", padding: 0, overflow: "hidden" }}>
          <img
            src={heroThumb}
            alt=""
            style={{ width: "100%", display: "block", maxHeight: 420, objectFit: "cover" }}
          />
        </div>
      )}

      <CommercialMetadataDisplay commercial={data} />

      {showMetadataForm && user && canSubmit(user) && (
        <CommercialMetadataForm commercial={data} />
      )}

      {!user && (
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          <a href="/login">Log in</a> and unlock submit access to propose metadata edits.
        </p>
      )}

      <CommercialVideoGallery
        commercial={data}
        selectedVideoSbid={selectedVideoSbid}
        onSelectVideo={selectVideo}
      />
    </div>
  );
}

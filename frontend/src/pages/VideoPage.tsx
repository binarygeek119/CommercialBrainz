import { Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { commercialUrl } from "../utils/commercialUrls";

/** Legacy /video/:sbid URLs redirect to the unified commercial view. */
export default function VideoPage() {
  const { sbid } = useParams<{ sbid: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["video-redirect", sbid],
    queryFn: () => api.getVideo(sbid!),
    enabled: !!sbid,
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data?.commercial_id) return <p className="error">Video not found</p>;

  return <Navigate to={commercialUrl(data.commercial_id, data.sbid)} replace />;
}

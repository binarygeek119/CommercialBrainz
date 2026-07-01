import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import OpenEditCard from "../components/OpenEditCard";

export default function VotingPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["open-edits"],
    queryFn: () => api.openEdits(),
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  const edits = data?.items ?? [];

  return (
    <div>
      <h1 className="page-title">Vote on submissions</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        Community submissions awaiting your vote. Edits close after 7 days or 3 unanimous votes.
        Earn reputation when your own submissions are approved.
      </p>
      <div className="stack">
        {edits.map((edit) => (
          <OpenEditCard key={edit.id} edit={edit} />
        ))}
        {edits.length === 0 && <p className="muted">No open edits right now.</p>}
      </div>
      {(data?.total ?? 0) > edits.length && (
        <p className="muted" style={{ marginTop: "1rem" }}>
          Showing {edits.length} of {data?.total} open edits.
        </p>
      )}
    </div>
  );
}

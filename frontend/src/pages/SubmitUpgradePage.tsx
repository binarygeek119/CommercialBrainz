import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type QuizQuestion } from "../api";
import { useAuth, canSubmit } from "../auth";

export default function SubmitUpgradePage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [terms, setTerms] = useState<{ title: string; sections: { heading: string; body: string }[] } | null>(null);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (canSubmit(user)) {
      navigate("/submit", { replace: true });
      return;
    }
    Promise.all([api.getSubmissionTerms(), api.getSubmissionQuiz()])
      .then(([t, q]) => {
        setTerms(t);
        setQuestions(q.questions);
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [user, navigate]);

  if (!user) {
    return (
      <div className="card">
        <p>
          You must <Link to="/login">log in</Link> to upgrade your account for submissions.
        </p>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (questions.some((q) => answers[q.id] === undefined)) {
      setError("Please answer every question.");
      return;
    }
    setSubmitting(true);
    try {
      await api.submitSubmissionQuiz(answers);
      await refresh();
      navigate("/submit");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <p className="muted">Loading submission quiz...</p>;
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <h1 className="page-title">Become a Submitter</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        New accounts are <strong>vote-only</strong>. To submit commercial links, read the terms below
        and pass a short quiz on what may be submitted.
      </p>

      {terms && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <h2>{terms.title}</h2>
          {terms.sections.map((section) => (
            <div key={section.heading} style={{ marginTop: "1rem" }}>
              <h3 style={{ fontSize: "1rem", marginBottom: "0.35rem" }}>{section.heading}</h3>
              <p className="muted" style={{ margin: 0 }}>{section.body}</p>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="card">
        <h2 style={{ marginTop: 0 }}>Submission Quiz</h2>
        <p className="muted">Answer all questions correctly to unlock submit access.</p>

        {questions.map((q, idx) => (
          <fieldset key={q.id} className="form-group" style={{ border: "none", padding: 0, margin: "1.25rem 0" }}>
            <legend style={{ fontWeight: 600, marginBottom: "0.5rem" }}>
              {idx + 1}. {q.prompt}
            </legend>
            {q.options.map((option, optionIndex) => (
              <label key={optionIndex} style={{ display: "block", marginBottom: "0.35rem", cursor: "pointer" }}>
                <input
                  type="radio"
                  name={q.id}
                  value={optionIndex}
                  checked={answers[q.id] === optionIndex}
                  onChange={() => setAnswers({ ...answers, [q.id]: optionIndex })}
                  style={{ marginRight: "0.5rem" }}
                />
                {option}
              </label>
            ))}
          </fieldset>
        ))}

        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Checking answers..." : "Submit quiz & unlock submissions"}
        </button>
      </form>
    </div>
  );
}

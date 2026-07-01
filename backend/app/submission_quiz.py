"""Submission terms quiz — users must pass before gaining submit privileges."""

from dataclasses import dataclass


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    prompt: str
    options: tuple[str, ...]
    correct_index: int


QUIZ_QUESTIONS: tuple[QuizQuestion, ...] = (
    QuizQuestion(
        id="acceptable_content",
        prompt="Which links may you submit to CommercialBrainz?",
        options=(
            "Publicly available YouTube videos of television or streaming commercials",
            "Unlisted or private YouTube videos",
            "Movie trailers and music videos",
            "Any YouTube video you find interesting",
        ),
        correct_index=0,
    ),
    QuizQuestion(
        id="duplicate_url",
        prompt="Can you submit the same YouTube URL more than once for one commercial?",
        options=(
            "Yes, if the quality is different",
            "No — each URL may only appear once",
            "Yes, on different commercial listings",
            "Only moderators decide this case-by-case",
        ),
        correct_index=1,
    ),
    QuizQuestion(
        id="multiple_versions",
        prompt="A single commercial may include multiple YouTube links when:",
        options=(
            "They are different versions (e.g. :30 vs :60) and each is clearly labeled",
            "They are identical reuploads of the same URL",
            "They are random duplicates with no labels",
            "They point to non-commercial content",
        ),
        correct_index=0,
    ),
    QuizQuestion(
        id="hosting",
        prompt="What does CommercialBrainz do with the videos you link?",
        options=(
            "Hosts and streams the video files",
            "Claims ownership of the commercial content",
            "Indexes links only — it does not host video",
            "Downloads and archives every submission",
        ),
        correct_index=2,
    ),
    QuizQuestion(
        id="violations",
        prompt="What may happen if you repeatedly violate submission terms?",
        options=(
            "Nothing — all submissions are anonymous",
            "Your submission privileges may be revoked",
            "You automatically become a moderator",
            "Only your oldest submissions are removed",
        ),
        correct_index=1,
    ),
    QuizQuestion(
        id="metadata",
        prompt="When submitting, you agree to:",
        options=(
            "Provide accurate metadata when available and avoid misleading titles",
            "Invent campaign details if unknown",
            "Submit without any labels for version variants",
            "Ignore copyright — linking is always fair use",
        ),
        correct_index=0,
    ),
)

QUIZ_PASS_SCORE = len(QUIZ_QUESTIONS)  # all questions must be correct


def quiz_for_client() -> list[dict]:
    return [
        {"id": q.id, "prompt": q.prompt, "options": list(q.options)}
        for q in QUIZ_QUESTIONS
    ]


def grade_quiz(answers: dict[str, int]) -> tuple[int, int, bool]:
    total = len(QUIZ_QUESTIONS)
    correct = 0
    for q in QUIZ_QUESTIONS:
        if answers.get(q.id) == q.correct_index:
            correct += 1
    return correct, total, correct >= QUIZ_PASS_SCORE

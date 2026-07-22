export const AGE_RANGE_OPTIONS = [
  "Kids",
  "Teens",
  "18-34",
  "35-49",
  "50-64",
  "65+",
  "All ages",
] as const;

export interface SubmissionGenres {
  age_range: string;
  target_channel: string;
  banned: boolean;
  adult_rated: boolean;
  late_night: boolean;
  fake: boolean;
  real: boolean;
  ai_enhanced: boolean;
  holiday: string;
  event: string;
  store: string;
  service: string;
}

export const EMPTY_SUBMISSION_GENRES: SubmissionGenres = {
  age_range: "",
  target_channel: "",
  banned: false,
  adult_rated: false,
  late_night: false,
  fake: false,
  real: false,
  ai_enhanced: false,
  holiday: "",
  event: "",
  store: "",
  service: "",
};

export const GENRE_FLAG_LABELS: { key: keyof SubmissionGenres; label: string }[] = [
  { key: "banned", label: "Banned" },
  { key: "adult_rated", label: "Adult rated" },
  { key: "late_night", label: "Late night" },
  { key: "fake", label: "Fake" },
  { key: "real", label: "Real" },
  { key: "ai_enhanced", label: "AI enhanced" },
];

export function parseAgeRangeSelections(value: string): string[] {
  if (!value.trim()) return [];
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function isAgeRangeSelected(value: string, option: string): boolean {
  return parseAgeRangeSelections(value).includes(option);
}

export function toggleAgeRangeSelection(
  current: string,
  option: string,
  checked: boolean
): string {
  const selected = new Set(parseAgeRangeSelections(current));
  if (checked) selected.add(option);
  else selected.delete(option);
  return AGE_RANGE_OPTIONS.filter((opt) => selected.has(opt)).join(", ");
}

export function submissionGenresPayload(genres: SubmissionGenres) {
  const payload: Record<string, string | boolean> = {};
  for (const { key } of GENRE_FLAG_LABELS) {
    if (genres[key]) payload[key] = true;
  }
  if (genres.age_range.trim()) payload.age_range = genres.age_range.trim();
  if (genres.target_channel.trim()) payload.target_channel = genres.target_channel.trim();
  if (genres.holiday.trim()) payload.holiday = genres.holiday.trim();
  if (genres.event.trim()) payload.event = genres.event.trim();
  if (genres.store.trim()) payload.store = genres.store.trim();
  if (genres.service.trim()) payload.service = genres.service.trim();
  return Object.keys(payload).length ? payload : undefined;
}

export function genresFromMetadata(raw: unknown): SubmissionGenres {
  const g = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const bool = (key: keyof SubmissionGenres) => Boolean(g[key]);
  return {
    ...EMPTY_SUBMISSION_GENRES,
    age_range: typeof g.age_range === "string" ? g.age_range : "",
    target_channel: typeof g.target_channel === "string" ? g.target_channel : "",
    holiday: typeof g.holiday === "string" ? g.holiday : "",
    event: typeof g.event === "string" ? g.event : "",
    store: typeof g.store === "string" ? g.store : "",
    service: typeof g.service === "string" ? g.service : "",
    banned: bool("banned"),
    adult_rated: bool("adult_rated"),
    late_night: bool("late_night"),
    fake: bool("fake"),
    real: bool("real"),
    ai_enhanced: bool("ai_enhanced"),
  };
}

export function formatSubmissionGenres(genres: Partial<SubmissionGenres> | undefined): string[] {
  if (!genres) return [];
  const lines: string[] = [];
  if (genres.age_range) lines.push(`Age range: ${genres.age_range}`);
  if (genres.target_channel) lines.push(`Channel: ${genres.target_channel}`);
  for (const { key, label } of GENRE_FLAG_LABELS) {
    if (genres[key]) lines.push(label);
  }
  if (genres.holiday) lines.push(`Holiday: ${genres.holiday}`);
  if (genres.event) lines.push(`Event: ${genres.event}`);
  if (genres.store) lines.push(`Store: ${genres.store}`);
  if (genres.service) lines.push(`Service: ${genres.service}`);
  return lines;
}

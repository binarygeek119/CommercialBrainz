const API_BASE = "/api/v1";

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  access_level: string;
  can_submit: boolean;
  is_auto_editor: boolean;
  accepted_edits_count: number;
  created_at: string;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  options: string[];
}

export interface Video {
  sbid: string;
  commercial_id: string;
  youtube_id: string | null;
  youtube_url: string | null;
  channel_name: string | null;
  duration_ms: number | null;
  language: string | null;
  region: string | null;
  transcript: string | null;
  slogan: string | null;
  visibility: string;
  created_at: string;
  commercial?: { sbid: string; title: string };
  advertiser?: { sbid: string; name: string };
  tags?: string[];
  credits?: { role: string; name: string }[];
}

export interface Edit {
  id: string;
  edit_type: string;
  status: string;
  entity_type: string;
  entity_id: string | null;
  after_state: Record<string, unknown>;
  editor_id: string;
  comment: string | null;
  expires_at: string;
  created_at: string;
  votes: { id: string; voter_id: string; choice: string; comment: string | null }[];
}

export interface SearchResult {
  type: string;
  sbid: string;
  title: string;
  subtitle: string | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

function getToken(): string | null {
  return localStorage.getItem("commercialbrainz_token");
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("commercialbrainz_token", token);
  else localStorage.removeItem("commercialbrainz_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "User-Agent": "CommercialBrainz-Web/0.1.0 (https://commercialbrainz.org)",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  register: (data: { username: string; email: string; password: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { username: string; password: string }) =>
    request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify(data) }),

  me: () => request<User>("/auth/me"),

  getSubmissionTerms: () =>
    request<{ title: string; sections: { heading: string; body: string }[] }>(
      "/auth/submission-terms"
    ),

  getSubmissionQuiz: () =>
    request<{ questions: QuizQuestion[]; pass_score: number }>("/auth/submission-quiz"),

  submitSubmissionQuiz: (answers: Record<string, number>) =>
    request<{ passed: boolean; score: number; total: number; can_submit: boolean }>(
      "/auth/submission-upgrade",
      { method: "POST", body: JSON.stringify({ answers }) }
    ),

  search: (query: string, type = "all") =>
    request<SearchResult[]>(`/search?query=${encodeURIComponent(query)}&type=${type}`),

  browseVideos: (offset = 0, limit = 25) =>
    request<Paginated<Video>>(`/browse/videos?offset=${offset}&limit=${limit}`),

  getVideo: (sbid: string) => request<Video>(`/videos/${sbid}`),

  getCommercial: (sbid: string) => request<Record<string, unknown>>(`/commercials/${sbid}`),

  submitVideo: (data: Record<string, unknown>) =>
    request<Edit>("/edits/submit-video", { method: "POST", body: JSON.stringify(data) }),

  openEdits: (offset = 0) => request<Paginated<Edit>>(`/edits/open?offset=${offset}`),

  getEdit: (id: string) => request<Edit>(`/edits/${id}`),

  vote: (editId: string, choice: string, comment?: string) =>
    request<unknown>(`/edits/${editId}/vote`, {
      method: "POST",
      body: JSON.stringify({ choice, comment }),
    }),

  submitDmca: (data: Record<string, unknown>) =>
    request<unknown>("/dmca", { method: "POST", body: JSON.stringify(data) }),

  dmcaQueue: (status?: string) =>
    request<Paginated<Record<string, unknown>>>(
      `/dmca/queue${status ? `?status=${status}` : ""}`
    ),

  reviewDmca: (id: string, status: string, review_notes?: string) =>
    request<unknown>(`/dmca/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ status, review_notes }),
    }),

  setUserRole: (userId: string, role: string) =>
    request<User>(`/admin/users/${userId}/role/${role}`, { method: "POST" }),
};

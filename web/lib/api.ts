export const API = (process.env.NEXT_PUBLIC_API_URL || "https://api-production-377ba.up.railway.app").replace(/\/$/, "");

export type Dev = { name: string; team: string };
export type GNode = { id: string; label: string; name: string; team?: string; status?: string; dev?: string; [k: string]: unknown };
export type GLink = { source: string; target: string; type: string };
export type Path = { nodes: GNode[]; links: GLink[] };
export type Trace = { name: string; cypher: string; params: Record<string, unknown>; ms: number; rows: number }[];

export type Memory = {
  solution: {
    id: string; title: string; summary: string; code: string; status: string; effort_minutes: number;
    attempts: number; tokens_spent: number; visibility: string; created_at: number;
  };
  task: { id: string; text: string };
  similarity: number;
  score: number;
  author: Dev;
  project: { name: string } | null;
  session: { id: string; started_at: number };
  lessons: { text: string; kind: "pitfall" | "tip" | "dead_end" }[];
  errors: { signature: string }[];
  skipped: { id: string; title: string; status: string; reason: string }[];
  builds_on: { id: string; title: string }[];
  reuse_count: number;
  tokens_saved_estimate: number;
  path: Path;
};

export type Overview = {
  teams: { name: string; components: string[]; devs: string[] }[];
  projects: { name: string; repo: string; started_at: number; components: string[] }[];
  counts: { sessions: number; live_sessions: number; solutions: number; questions: number; tokens_saved: number };
};

export type LiveSession = {
  id: string; task: string; agent: string; started_at: number; last_seen: number; dev: Dev; components: string[];
  overlaps: { session_id: string; dev: Dev; task: string; score: number }[];
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = j.detail || msg;
    } catch {}
    throw new ApiError(r.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return r.json() as Promise<T>;
}

export function get<T>(path: string): Promise<T> {
  return fetch(`${API}${path}`, { cache: "no-store" }).then((r) => handle<T>(r));
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => handle<T>(r));
}

export function ago(ts?: number | null): string {
  if (!ts) return "";
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  const d = Math.floor(s / 86400);
  return d < 14 ? `${d} days ago` : `${Math.round(d / 7)} weeks ago`;
}

export function effort(minutes?: number, attempts?: number): string {
  const m = minutes || 0;
  const span = m >= 480 ? `${Math.round(m / 480)} working day${m >= 960 ? "s" : ""}` : m >= 60 ? `${Math.round(m / 60)}h` : `${m}m`;
  return `${span}${attempts ? ` · ${attempts} attempts` : ""}`;
}

export function tokens(n?: number): string {
  const v = n || 0;
  return v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`;
}

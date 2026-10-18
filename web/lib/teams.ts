// One color per team, used everywhere (graph nodes, badges, charts).
const KNOWN: Record<string, string> = {
  Identity: "#a78bfa",
  Payments: "#f59e0b",
  Data: "#38bdf8",
  Mobile: "#f472b6",
  Platform: "#a3e635",
  Mycelium: "#34d399",
};
const FALLBACK = ["#fb923c", "#60a5fa", "#e879f9", "#4ade80", "#facc15", "#22d3ee"];

export function teamColor(team?: string | null): string {
  if (!team) return "#94a3b8";
  if (KNOWN[team]) return KNOWN[team];
  let h = 0;
  for (const c of team) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return FALLBACK[h % FALLBACK.length];
}

export const LABEL_COLOR: Record<string, string> = {
  Task: "#94a3b8",
  Solution: "#34d399",
  Session: "#2dd4bf",
  Lesson: "#fbbf24",
  Question: "#e879f9",
  Project: "#60a5fa",
  Error: "#f87171",
};

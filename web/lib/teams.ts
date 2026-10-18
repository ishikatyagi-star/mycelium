// One color per team, used everywhere (graph nodes, badges, charts). Tuned for legibility on white.
const KNOWN: Record<string, string> = {
  Identity: "#7c3aed",
  Payments: "#d97706",
  Data: "#0284c7",
  Mobile: "#db2777",
  Platform: "#4d7c0f",
  Mycelium: "#059669",
};
const FALLBACK = ["#ea580c", "#2563eb", "#c026d3", "#16a34a", "#ca8a04", "#0891b2"];

export function teamColor(team?: string | null): string {
  if (!team) return "#64748b";
  if (KNOWN[team]) return KNOWN[team];
  let h = 0;
  for (const c of team) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return FALLBACK[h % FALLBACK.length];
}

export const LABEL_COLOR: Record<string, string> = {
  Task: "#64748b",
  Solution: "#15803d",
  Session: "#0d9488",
  Lesson: "#b45309",
  Question: "#a21caf",
  Project: "#2563eb",
  Error: "#dc2626",
};

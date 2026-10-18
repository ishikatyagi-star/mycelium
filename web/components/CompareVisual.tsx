"use client";

import { useEffect, useState } from "react";
import { effort, tokens, type Memory } from "@/lib/api";
import { teamColor } from "@/lib/teams";

const STEPS = [
  { vector: "Read the question", graph: "Read the question" },
  { vector: "Find look-alike past problems", graph: "Find look-alike past problems" },
  { vector: "Return the closest one", graph: "Check: was that fix replaced?" },
  { vector: "Nothing else to check", graph: "Collect dead ends and who solved it" },
  { vector: "Result", graph: "Result" },
];

const RED = "#dc2626", GREEN = "#15803d", GREY = "#64748b", AMBER = "#b45309", PINK = "#a21caf";

export default function CompareVisual({ query, vector, graph }: { query: string; vector: Memory[]; graph: Memory[] }) {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);
  const play = () => { setStep(0); setPlaying(true); };

  useEffect(() => {
    if (!playing) return;
    if (step >= STEPS.length - 1) { setPlaying(false); return; }
    const t = setTimeout(() => setStep((s) => s + 1), step === 0 ? 900 : 1500);
    return () => clearTimeout(t);
  }, [step, playing]);
  useEffect(() => { play(); }, [query]);

  const v = vector[0], g = graph[0];
  if (!v || !g) return null;
  const vBad = v.solution.status !== "active";

  return (
    <div className="card p-4 space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-bold">How each one answers</h2>
        <span className="text-sm text-muted">“{query}”</span>
        <div className="ml-auto flex items-center gap-2">
          {STEPS.map((_, i) => (
            <button key={i} onClick={() => { setPlaying(false); setStep(i); }}
                    className="w-7 h-7 rounded-full text-xs font-bold border transition"
                    style={{ background: i <= step ? "var(--primary)" : "transparent", color: i <= step ? "#fff" : undefined,
                             borderColor: i <= step ? "var(--primary)" : "var(--border-strong)" }}>{i + 1}</button>
          ))}
          <button className="btn !py-1 !px-2.5 !text-xs" onClick={play}>{playing ? "Playing…" : "▶ Replay"}</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* vector lane */}
        <div className="rounded-xl border border-line p-3 space-y-3">
          <div className="flex items-center justify-between">
            <div className="font-bold text-muted">Vector search</div>
            <div className="text-sm text-subtle">finds look-alikes</div>
          </div>
          <Caption text={STEPS[step].vector} />
          <svg viewBox="0 0 560 300" className="w-full h-auto">
            <QueryNode x={50} y={150} on />
            {/* similarity axis */}
            <g style={{ opacity: step >= 1 ? 1 : 0.15, transition: "opacity .6s" }}>
              <line x1={150} y1={250} x2={540} y2={250} stroke="var(--border)" strokeWidth={2} />
              {[0.6, 0.7, 0.8, 0.9, 1.0].map((t) => (
                <g key={t}>
                  <line x1={sx(t)} y1={246} x2={sx(t)} y2={254} stroke="var(--border)" />
                  <text x={sx(t)} y={270} textAnchor="middle" fontSize={12} fill="var(--muted)">{t.toFixed(1)}</text>
                </g>
              ))}
              <text x={345} y={290} textAnchor="middle" fontSize={12} fill="var(--muted)">similarity to your question</text>
              {vector.slice(0, 3).map((m, i) => {
                const x = sx(m.similarity), y = 60 + i * 62, top = i === 0, bad = m.solution.status !== "active";
                const c = step >= 4 && top ? (bad ? RED : GREEN) : top && step >= 2 ? (bad ? RED : GREY) : GREY;
                return (
                  <g key={m.solution.id}>
                    <line x1={x} y1={y + 10} x2={x} y2={246} stroke={c} strokeDasharray="3 3" opacity={0.5} />
                    <line x1={92} y1={150} x2={x - 12} y2={y} stroke={c} strokeDasharray="5 4" opacity={step >= 1 ? 0.6 : 0}
                          style={{ transition: "opacity .6s" }} />
                    <circle cx={x} cy={y} r={top && step >= 2 ? 13 : 9} fill={c} opacity={top || step < 2 ? 1 : 0.35}
                            style={{ transition: "all .5s" }} />
                    <text x={Math.min(Math.max(x, 210), 440)} y={y - 19} textAnchor="middle" fontSize={12} fill="var(--text)"
                          opacity={top || step < 2 ? 1 : 0.4}>{trim(m.solution.title, 36)}</text>
                    <text x={x + 18} y={y + 4} fontSize={12} fill="var(--muted)">{m.similarity.toFixed(2)}</text>
                    {top && step >= 2 && (
                      <text x={x} y={y + 30} textAnchor="middle" fontSize={11.5} fontWeight={600}
                            fill={bad ? RED : GREEN} className="feed-item">{bad ? `top-1 · ${m.solution.status}` : "top-1"}</text>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>
          <Outcome show={step >= 4} bad={vBad}
                   title={`Uses “${trim(v.solution.title, 56)}”`}
                   body={vBad
                     ? "This fix already failed in production. A vector search can't know that."
                     : "Probably fine, but no dead ends and no one to ask."} />
        </div>

        {/* graph lane */}
        <div className="rounded-xl border-2 p-3 space-y-3" style={{ borderColor: "color-mix(in srgb, var(--primary) 40%, var(--border))" }}>
          <div className="flex items-center justify-between">
            <div className="font-bold" style={{ color: "var(--primary)" }}>Mycelium</div>
            <div className="text-sm text-subtle">follows what happened</div>
          </div>
          <Caption text={STEPS[step].graph} accent />
          <GraphWalk m={g} step={step} />
          <Outcome show={step >= 4} bad={false}
                   title={`Uses “${trim(g.solution.title, 56)}”`}
                   body={`The working fix, with ${g.lessons.length} lessons, credited to ${g.author.name}. Saves ~${tokens(g.tokens_saved_estimate)} tokens and ${effort(g.solution.effort_minutes, g.solution.attempts)}.`} />
        </div>
      </div>
    </div>
  );
}

function sx(sim: number) {
  return 150 + ((Math.max(0.55, Math.min(1, sim)) - 0.55) / 0.45) * 390;
}

function trim(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function Caption({ text, accent }: { text: string; accent?: boolean }) {
  return (
    <div key={text} className="feed-item text-sm font-semibold rounded-lg px-3 py-2"
         style={accent ? { color: "var(--primary)", background: "var(--primary-soft)" } : { color: "var(--muted)", background: "var(--surface-2)" }}>{text}</div>
  );
}

function Outcome({ show, bad, title, body }: { show: boolean; bad: boolean; title: string; body: string }) {
  return (
    <div className="rounded-xl p-3 text-sm transition-all duration-500"
         style={{ opacity: show ? 1 : 0.15, borderLeft: `4px solid ${bad ? RED : GREEN}`,
                  background: `color-mix(in srgb, ${bad ? RED : GREEN} ${show ? 10 : 3}%, transparent)` }}>
      <div className="font-bold" style={{ color: bad ? RED : GREEN }}>{bad ? "✗ " : "✓ "}{title}</div>
      <div className="text-fg/80 mt-1">{body}</div>
    </div>
  );
}

function QueryNode({ x, y, on }: { x: number; y: number; on: boolean }) {
  return (
    <g opacity={on ? 1 : 0.2}>
      <rect x={x - 42} y={y - 20} width={84} height={40} rx={10} fill="var(--surface-2)" stroke={PINK} strokeWidth={1.5} />
      <text x={x} y={y - 2} textAnchor="middle" fontSize={12} fill="var(--text)" fontWeight={600}>Your</text>
      <text x={x} y={y + 12} textAnchor="middle" fontSize={12} fill="var(--text)" fontWeight={600}>question</text>
    </g>
  );
}

type N = { id: string; x: number; y: number; label: string; sub?: string; color: string; phase: number; cross?: boolean; w?: number };
type E = { from: string; to: string; label: string; color: string; phase: number; dashed?: boolean };

function GraphWalk({ m, step }: { m: Memory; step: number }) {
  const stale = m.skipped[0];
  const lessons = m.lessons.filter((l) => l.kind !== "tip").slice(0, 2);
  const nodes: N[] = [
    { id: "q", x: 50, y: 150, label: "Your question", color: PINK, phase: 0 },
    { id: "task", x: 160, y: 150, label: "Similar task", sub: `sim ${m.similarity.toFixed(2)}`, color: GREY, phase: 1, w: 96 },
    ...(stale ? [{ id: "stale", x: 290, y: 70, label: trim(stale.title, 20), sub: "superseded", color: RED, phase: 2, cross: true, w: 158 } as N,
                 { id: "err", x: 470, y: 32, label: "Error", sub: trim(stale.reason.replace("failed with ", ""), 24), color: RED, phase: 3, w: 178 } as N] : []),
    { id: "fix", x: 290, y: stale ? 190 : 150, label: trim(m.solution.title, 20), sub: "current fix", color: GREEN, phase: 2, w: 158 },
    ...lessons.map((l, i) => ({ id: `l${i}`, x: 470, y: 102 + i * 50, label: l.kind === "dead_end" ? "Dead end" : "Pitfall",
                                sub: trim(l.text, 24), color: AMBER, phase: 3, w: 178 } as N)),
    { id: "dev", x: 470, y: 232, label: m.author.name, sub: m.author.team, color: teamColor(m.author.team), phase: 3, w: 120 },
    ...(m.project ? [{ id: "proj", x: 290, y: 272, label: m.project.name, sub: "project", color: "#60a5fa", phase: 3, w: 130 } as N] : []),
  ];
  const edges: E[] = [
    { from: "q", to: "task", label: "vector", color: PINK, phase: 1, dashed: true },
    ...(stale ? [{ from: "task", to: "stale", label: "SOLVES", color: GREY, phase: 2 } as E,
                 { from: "fix", to: "stale", label: "SUPERSEDES", color: GREEN, phase: 2 } as E,
                 { from: "stale", to: "err", label: "FAILED_WITH", color: RED, phase: 3 } as E]
             : [{ from: "task", to: "fix", label: "SOLVES", color: GREY, phase: 2 } as E]),
    ...lessons.map((_, i) => ({ from: "fix", to: `l${i}`, label: "TAUGHT", color: AMBER, phase: 3 } as E)),
    { from: "fix", to: "dev", label: "BY", color: teamColor(m.author.team), phase: 3 },
    ...(m.project ? [{ from: "fix", to: "proj", label: "IN_PROJECT", color: "#60a5fa", phase: 3 } as E] : []),
  ];
  const at = (id: string) => nodes.find((n) => n.id === id)!;
  return (
    <svg viewBox="0 0 560 300" className="w-full h-auto">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--muted)" />
        </marker>
      </defs>
      {edges.map((e, i) => {
        const a = at(e.from), b = at(e.to);
        if (!a || !b) return null;
        const on = step >= e.phase;
        const len = Math.hypot(b.x - a.x, b.y - a.y);
        return (
          <g key={i}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={e.color} strokeWidth={on ? 2 : 1}
                  strokeDasharray={e.dashed ? "5 4" : `${len}`} strokeDashoffset={on || e.dashed ? 0 : len}
                  opacity={on ? 0.9 : 0.08} markerEnd="url(#arr)" style={{ transition: "stroke-dashoffset .9s ease, opacity .6s" }} />
            {on && (
              <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 5} textAnchor="middle" fontSize={12} fill={e.color}
                    fontFamily="ui-monospace, monospace" className="feed-item">{e.label}</text>
            )}
          </g>
        );
      })}
      {nodes.map((n) => {
        const on = step >= n.phase;
        const w = n.w || 84;
        const glow = step >= 4 && n.id === "fix";
        return (
          <g key={n.id} opacity={on ? 1 : 0.12} style={{ transition: "opacity .6s" }}>
            {glow && <rect x={n.x - w / 2 - 6} y={-6 + n.y - 20} width={w + 12} height={52} rx={14} fill="none" stroke={GREEN} strokeWidth={2} opacity={0.6}>
              <animate attributeName="opacity" values="0.7;0.15;0.7" dur="1.6s" repeatCount="indefinite" />
            </rect>}
            <rect x={n.x - w / 2} y={n.y - 20} width={w} height={40} rx={10} fill="var(--surface-2)" stroke={n.color} strokeWidth={1.5} />
            <text x={n.x} y={n.y - 3} textAnchor="middle" fontSize={12} fontWeight={600} fill={n.color}
                  textDecoration={n.cross ? "line-through" : undefined}>{n.label}</text>
            {n.sub && <text x={n.x} y={n.y + 11} textAnchor="middle" fontSize={12} fill="var(--muted)">{n.sub}</text>}
            {n.cross && on && <text x={n.x + w / 2 - 4} y={n.y - 12} fontSize={16} fill={RED} fontWeight={700}>✕</text>}
          </g>
        );
      })}
    </svg>
  );
}

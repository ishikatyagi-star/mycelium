"use client";

import { AlertTriangle, Check, Flame, Folder, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ago, effort, tokens, type Memory } from "@/lib/api";
import PathGraph from "./PathGraph";
import { DevBadge } from "./ui";

const KIND: Record<string, { label: string; color: string }> = {
  pitfall: { label: "Pitfall", color: "var(--warn)" },
  dead_end: { label: "Dead end", color: "var(--bad)" },
  tip: { label: "Tip", color: "var(--good)" },
};

export default function MemoryCard({ m, rank, tone }: { m: Memory; rank?: number; tone?: "bad" | "good" }) {
  const [showCode, setShowCode] = useState(false);
  const [showPath, setShowPath] = useState(false);
  const [allLessons, setAllLessons] = useState(false);
  const s = m.solution;
  const stale = s.status !== "active";
  const border = tone === "bad" || stale ? "var(--bad)" : tone === "good" ? "var(--good)" : undefined;
  const lessons = allLessons ? m.lessons : m.lessons.slice(0, 3);
  return (
    <div className="card p-5 space-y-3" style={border ? { borderColor: border, borderWidth: 1.5 } : undefined}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-bold leading-snug">
          {rank !== undefined && <span className="text-subtle font-mono text-sm mr-2">#{rank}</span>}
          {s.title}
        </h3>
        {stale ? (
          <span className="chip shrink-0" style={{ color: "var(--bad)", borderColor: "var(--bad)", background: "var(--bad-soft)" }}>
            <AlertTriangle size={13} aria-hidden /> {s.status}
          </span>
        ) : (
          <span className="chip shrink-0" style={{ color: "var(--good)", borderColor: "var(--good)", background: "var(--good-soft)" }}>
            <Check size={13} aria-hidden /> current
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-muted">
        <DevBadge dev={m.author} small />
        {m.project && <span className="inline-flex items-center gap-1"><Folder size={14} aria-hidden /> {m.project.name}</span>}
        <span>{ago(s.created_at)}</span>
        <span className="inline-flex items-center gap-1" style={s.effort_minutes >= 240 ? { color: "var(--warn)", fontWeight: 600 } : undefined}>
          {s.effort_minutes >= 240 && <Flame size={14} aria-hidden />}{effort(s.effort_minutes, s.attempts)}
        </span>
        {m.reuse_count > 0 && <span className="inline-flex items-center gap-1"><RefreshCw size={13} aria-hidden /> reused {Math.round(m.reuse_count)}×</span>}
      </div>

      <p className="leading-relaxed">{s.summary}</p>

      {m.skipped.map((k) => (
        <div key={k.id} className="rounded-lg px-3 py-2 text-sm" style={{ background: "var(--bad-soft)" }}>
          <span className="font-semibold" style={{ color: "var(--bad)" }}>Skipped:</span> {k.title}{" "}
          <span className="text-muted">({k.reason})</span>
        </div>
      ))}

      {m.lessons.length > 0 && (
        <ul className="space-y-1.5">
          {lessons.map((l, i) => (
            <li key={i} className="text-sm flex gap-3">
              <span className="text-xs font-bold uppercase tracking-wide mt-0.5 shrink-0 w-16" style={{ color: KIND[l.kind]?.color }}>
                {KIND[l.kind]?.label || l.kind}
              </span>
              <span>{l.text}</span>
            </li>
          ))}
          {m.lessons.length > 3 && !allLessons && (
            <li><button className="text-sm font-semibold" style={{ color: "var(--primary)" }} onClick={() => setAllLessons(true)}>+{m.lessons.length - 3} more</button></li>
          )}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        {!stale && m.tokens_saved_estimate > 0 && (
          <span className="text-sm font-semibold mr-auto" style={{ color: "var(--good)" }}>~{tokens(m.tokens_saved_estimate)} tokens saved if reused</span>
        )}
        {s.code && <button className="btn !min-h-[32px] !py-1 !px-3 !text-xs" onClick={() => setShowCode(!showCode)}>{showCode ? "Hide code" : "Code"}</button>}
        <button className="btn !min-h-[32px] !py-1 !px-3 !text-xs" onClick={() => setShowPath(!showPath)}>{showPath ? "Hide path" : "Graph path"}</button>
        <Link href={`/lineage/${s.id}`} className="btn !min-h-[32px] !py-1 !px-3 !text-xs">Lineage</Link>
      </div>
      {showCode && s.code && <pre className="text-xs font-mono bg-surface-2 rounded-lg p-3 overflow-auto whitespace-pre">{s.code}</pre>}
      {showPath && <PathGraph path={m.path} />}
    </div>
  );
}

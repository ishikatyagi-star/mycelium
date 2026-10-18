"use client";

import Link from "next/link";
import { useState } from "react";
import { ago, effort, tokens, type Memory } from "@/lib/api";
import PathGraph from "./PathGraph";
import { DevBadge } from "./ui";

const KIND: Record<string, { label: string; color: string }> = {
  pitfall: { label: "Pitfall", color: "var(--warn)" },
  dead_end: { label: "Dead end", color: "var(--danger)" },
  tip: { label: "Tip", color: "var(--ok)" },
};

export default function MemoryCard({ m, rank, tone }: { m: Memory; rank?: number; tone?: "bad" | "good" }) {
  const [showCode, setShowCode] = useState(false);
  const [showPath, setShowPath] = useState(false);
  const s = m.solution;
  const stale = s.status !== "active";
  const border = tone === "bad" || stale ? "var(--danger)" : tone === "good" ? "var(--accent)" : undefined;
  return (
    <div className="card p-4 space-y-3" style={border ? { borderColor: border } : undefined}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {rank !== undefined && <span className="text-muted text-xs font-mono">#{rank}</span>}
            <h3 className="font-semibold leading-snug">{s.title}</h3>
          </div>
          <div className="text-xs text-muted mt-1 truncate">solves: {m.task.text}</div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {stale ? (
            <span className="chip" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}>
              {s.status === "superseded" ? "⚠ superseded" : "⚠ broken"}
            </span>
          ) : (
            <span className="chip" style={{ color: "var(--ok)" }}>✓ current</span>
          )}
          <span className="text-[11px] text-muted font-mono">sim {m.similarity.toFixed(2)}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <DevBadge dev={m.author} />
        {m.project && <span className="chip">📁 {m.project.name}</span>}
        <span className="chip">{ago(s.created_at)}</span>
        {s.effort_minutes >= 240 && (
          <span className="chip" style={{ color: "var(--warn)", borderColor: "var(--warn)" }}>🔥 hard-won: {effort(s.effort_minutes, s.attempts)}</span>
        )}
        {s.effort_minutes < 240 && <span className="chip">{effort(s.effort_minutes, s.attempts)}</span>}
        {m.reuse_count > 0 && <span className="chip">♻ reused {Math.round(m.reuse_count)}×</span>}
        {m.tokens_saved_estimate > 0 && !stale && (
          <span className="chip" style={{ color: "var(--accent)" }}>~{tokens(m.tokens_saved_estimate)} tokens saved</span>
        )}
      </div>

      <p className="text-sm leading-relaxed">{s.summary}</p>

      {m.skipped.length > 0 && (
        <div className="rounded-lg px-3 py-2 text-sm" style={{ background: "color-mix(in srgb, var(--danger) 10%, transparent)" }}>
          {m.skipped.map((k) => (
            <div key={k.id}>
              <span className="font-medium" style={{ color: "var(--danger)" }}>Skipped stale fix:</span> “{k.title}”{" "}
              <span className="text-muted">({k.reason})</span>
            </div>
          ))}
        </div>
      )}

      {m.lessons.length > 0 && (
        <ul className="space-y-1">
          {m.lessons.map((l, i) => (
            <li key={i} className="text-sm flex gap-2">
              <span className="text-[10px] uppercase font-semibold tracking-wide mt-0.5 shrink-0 w-16" style={{ color: KIND[l.kind]?.color }}>
                {KIND[l.kind]?.label || l.kind}
              </span>
              <span>{l.text}</span>
            </li>
          ))}
        </ul>
      )}

      {m.errors.length > 0 && (
        <div className="text-xs text-muted">Errors on record: {m.errors.map((e) => e.signature).join(" · ")}</div>
      )}

      {m.builds_on.length > 0 && (
        <div className="text-xs text-muted">
          Builds on:{" "}
          {m.builds_on.map((b) => (
            <span key={b.id} className="mr-2">{b.title}</span>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        {s.code && (
          <button className="btn !py-1 !px-2.5 !text-xs" onClick={() => setShowCode(!showCode)}>
            {showCode ? "Hide code" : "Show code"}
          </button>
        )}
        <button className="btn !py-1 !px-2.5 !text-xs" onClick={() => setShowPath(!showPath)}>
          {showPath ? "Hide path" : "Show graph path"}
        </button>
        <Link href={`/lineage/${s.id}`} className="btn !py-1 !px-2.5 !text-xs">Lineage</Link>
      </div>
      {showCode && s.code && (
        <pre className="text-xs font-mono bg-surface-2 rounded-lg p-3 overflow-auto whitespace-pre">{s.code}</pre>
      )}
      {showPath && <PathGraph path={m.path} />}
    </div>
  );
}

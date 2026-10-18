"use client";

import { useState } from "react";
import type { Dev, Trace } from "@/lib/api";
import { teamColor } from "@/lib/teams";

export function DevBadge({ dev, small }: { dev: Dev | { name: string; team?: string }; small?: boolean }) {
  const c = teamColor(dev.team);
  return (
    <span className="chip" style={{ borderColor: `${c}66`, background: `${c}14`, fontSize: small ? "0.7rem" : undefined }}>
      <span style={{ width: 7, height: 7, borderRadius: 99, background: c, display: "inline-block" }} />
      <span className="font-medium">{dev.name}</span>
      {dev.team && <span className="text-muted">{dev.team}</span>}
    </span>
  );
}

export function TeamDot({ team }: { team: string }) {
  return <span style={{ width: 8, height: 8, borderRadius: 99, background: teamColor(team), display: "inline-block" }} />;
}

export function CypherTrace({ trace }: { trace?: Trace }) {
  const [open, setOpen] = useState(false);
  if (!trace?.length) return null;
  const total = trace.reduce((a, t) => a + t.ms, 0);
  return (
    <div className="card overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-4 py-2.5 text-sm">
        <span className="font-medium">
          <span className="text-accent font-mono mr-2">{"</>"}</span>Show Cypher
          <span className="text-muted font-normal ml-2">
            {trace.length} queries · {total.toFixed(0)} ms in FalkorDB
          </span>
        </span>
        <span className="text-muted">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="border-t border-line max-h-[420px] overflow-auto">
          {trace.map((t, i) => (
            <div key={i} className="px-4 py-3 border-b border-line last:border-0">
              <div className="flex justify-between text-xs mb-1.5">
                <span className="font-mono text-accent">{t.name}</span>
                <span className="text-muted">
                  {t.ms} ms · {t.rows} rows
                </span>
              </div>
              <pre className="text-[11.5px] leading-relaxed whitespace-pre-wrap font-mono text-fg/85">{t.cypher}</pre>
              {Object.keys(t.params || {}).length > 0 && (
                <pre className="text-[11px] mt-1 text-muted whitespace-pre-wrap font-mono">params {JSON.stringify(t.params)}</pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="text-muted text-sm py-10 text-center">{children}</div>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-muted text-sm py-6">
      <span className="inline-block w-3 h-3 rounded-full border-2 border-accent border-t-transparent animate-spin" />
      {label || "Asking the graph…"}
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <div className="card px-4 py-3 text-sm" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>{error}</div>;
}

export function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="px-3">
      <div className="text-lg font-semibold tabular-nums leading-tight">{value}</div>
      <div className="text-[11px] text-muted uppercase tracking-wide">{label}</div>
      {hint && <div className="text-[10px] text-muted">{hint}</div>}
    </div>
  );
}

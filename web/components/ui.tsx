"use client";

import { useState } from "react";
import type { Dev, Trace } from "@/lib/api";
import { teamColor } from "@/lib/teams";

export function DevBadge({ dev, small }: { dev: Dev | { name: string; team?: string }; small?: boolean }) {
  const c = teamColor(dev.team);
  return (
    <span className="chip" style={{ borderColor: `${c}55`, background: `${c}0d`, fontSize: small ? "0.75rem" : undefined }}>
      <span style={{ width: 7, height: 7, borderRadius: 99, background: c, display: "inline-block" }} />
      <span className="font-semibold text-fg">{dev.name}</span>
      {dev.team && <span className="text-subtle">{dev.team}</span>}
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
          <span className="text-primary font-mono mr-2">{"</>"}</span>Show Cypher
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
              <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono text-fg/85">{t.cypher}</pre>
              {Object.keys(t.params || {}).length > 0 && (
                <pre className="text-xs mt-1 text-muted whitespace-pre-wrap font-mono">params {JSON.stringify(t.params)}</pre>
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

export function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="px-4 first:pl-0">
      <div className="text-xl font-bold tabular-nums leading-tight">{value}</div>
      <div className="text-xs text-subtle">{label}</div>
    </div>
  );
}

/** Every page opens the same way: one title, one sentence. */
export function PageHeader({ title, sub, right }: { title: string; sub: string; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end gap-4 mb-6">
      <div className="max-w-3xl">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">{title}</h1>
        <p className="text-base text-muted mt-1.5">{sub}</p>
      </div>
      {right && <div className="ml-auto">{right}</div>}
    </div>
  );
}

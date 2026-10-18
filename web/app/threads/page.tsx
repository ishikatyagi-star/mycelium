"use client";

import { useEffect, useState } from "react";
import { useOrg } from "@/components/OrgProvider";
import { DevBadge, Empty } from "@/components/ui";
import { ago, get, type Dev } from "@/lib/api";

type Thread = {
  id: string; text: string; status: string; mode: string | null; at: number; asker: Dev;
  routed_to: string | null; reason: string | null;
  answer: { text: string; by: Dev } | null;
  memory: { id: string; title: string } | null;
};

export default function ThreadsPage() {
  const { org, devs } = useOrg();
  const [threads, setThreads] = useState<Thread[] | null>(null);
  const teamOf = (name?: string | null) => devs.find((d) => d.name === name)?.team || "";

  useEffect(() => {
    let alive = true;
    const load = () => get<{ threads: Thread[] }>(`/api/orgs/${org}/questions`).then((r) => alive && setThreads(r.threads)).catch(() => {});
    load();
    const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, [org]);

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Agent-to-agent threads</h1>
        <p className="text-muted text-sm mt-1">
          Questions agents asked the org, who the graph routed them to and why, and the answers. Answers <b>become memory</b>, so the next
          agent with the same question gets it instantly. Refreshes every 8 s.
        </p>
      </div>
      {threads === null && <Empty>Loading…</Empty>}
      {threads?.length === 0 && <Empty>No questions yet.</Empty>}
      {threads?.map((t) => (
        <div key={t.id} className="card p-4 space-y-2">
          <div className="flex items-center gap-2 flex-wrap text-sm">
            <DevBadge dev={t.asker} small />
            <span className="text-muted">asked {ago(t.at)}</span>
            <span className="chip ml-auto"
                  style={{ color: t.status === "answered" ? "var(--ok)" : t.status === "routed" ? "#e879f9" : "var(--muted)" }}>
              {t.mode === "memory" ? "answered from memory" : t.status}
            </span>
          </div>
          <div className="font-medium">“{t.text}”</div>
          {t.routed_to && (
            <div className="text-sm flex gap-2 flex-wrap items-center">
              <span className="text-muted">→ routed to</span>
              <DevBadge dev={{ name: t.routed_to, team: teamOf(t.routed_to) }} small />
              {t.reason && <span className="text-xs text-muted">{t.reason.split(";").slice(0, 2).join(";")}</span>}
            </div>
          )}
          {t.answer && (
            <div className="rounded-lg bg-surface-2 px-3 py-2 text-sm">
              <div className="flex items-center gap-2 mb-1"><DevBadge dev={t.answer.by} small /><span className="text-muted text-xs">answered</span></div>
              {t.answer.text}
            </div>
          )}
          {t.memory && <div className="text-xs" style={{ color: "var(--accent)" }}>✓ saved as org memory: {t.memory.title}</div>}
        </div>
      ))}
    </div>
  );
}

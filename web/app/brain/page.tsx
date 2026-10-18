"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useOrg } from "@/components/OrgProvider";
import { CypherTrace, DevBadge, Empty, Spinner } from "@/components/ui";
import { effort, get, tokens, type Dev, type Trace } from "@/lib/api";
import { teamColor } from "@/lib/teams";

type Brain = {
  experts: { dev: Dev; pagerank: number; helped: number }[];
  at_risk: { solution_id: string; title: string; owner: Dev; effort_minutes: number; attempts: number }[];
  savings: { team: string; tokens_saved: number; reuses: number }[];
  help_flows: { from_team: string; to_team: string; count: number }[];
  trace: Trace;
};
type Expert = { dev: Dev; score: number; pagerank: number; evidence: { solution_id: string; title: string; similarity: number }[] };

export default function BrainPage() {
  const { org } = useOrg();
  const [b, setB] = useState<Brain | null>(null);
  const [topic, setTopic] = useState("");
  const [who, setWho] = useState<{ experts: Expert[]; trace: Trace } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setB(null);
    get<Brain>(`/api/orgs/${org}/brain`).then(setB).catch(() => {});
  }, [org]);

  const ask = async (t = topic) => {
    setTopic(t);
    setBusy(true);
    try {
      setWho(await get(`/api/orgs/${org}/who_knows?topic=${encodeURIComponent(t)}`));
    } finally {
      setBusy(false);
    }
  };

  const maxPr = Math.max(...(b?.experts.map((e) => e.pagerank) || [1]), 0.0001);
  const maxSave = Math.max(...(b?.savings.map((s) => s.tokens_saved) || [1]), 1);

  return (
    <div className="space-y-5">
      <div className="max-w-4xl">
        <h1 className="text-2xl font-semibold">Company brain</h1>
        <p className="text-muted text-sm mt-1">
          Who actually knows what (PageRank over <span className="font-mono">CREDITS</span> edges, written every time someone reuses your fix or
          your answer helps them), which hard-won knowledge would be lost if one person left, and how knowledge flows between teams.
        </p>
      </div>

      <div className="card p-4 space-y-3">
        <h2 className="font-semibold">Who knows…?</h2>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(); }}>
          <input className="input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="a topic, e.g. kafka consumer lag" />
          <button className="btn btn-primary shrink-0" disabled={topic.length < 3}>Find experts</button>
        </form>
        <div className="flex gap-2 flex-wrap">
          {["kafka consumer group rebalancing", "token refresh and JWT", "idempotent webhooks", "arm64 docker builds"].map((t) => (
            <button key={t} className="chip hover:border-accent" onClick={() => ask(t)}>{t}</button>
          ))}
        </div>
        {busy && <Spinner />}
        {who && (
          <div className="space-y-2">
            {who.experts.length === 0 && <Empty>No one in the graph has worked on this yet.</Empty>}
            {who.experts.map((e) => (
              <div key={e.dev.name} className="flex items-start gap-3 text-sm">
                <DevBadge dev={e.dev} small />
                <span className="font-mono text-xs text-muted w-14 shrink-0">{e.score}</span>
                <span className="text-muted">{e.evidence.map((x) => x.title).join(" · ")}</span>
              </div>
            ))}
            <CypherTrace trace={who.trace} />
          </div>
        )}
      </div>

      {!b ? <Spinner label="Running PageRank…" /> : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <section className="card p-4">
            <h2 className="font-semibold mb-3">Experts by authority <span className="text-xs text-muted font-normal">algo.pageRank(&apos;Dev&apos;,&apos;CREDITS&apos;)</span></h2>
            <div className="space-y-2">
              {b.experts.map((e) => (
                <div key={e.dev.name} className="flex items-center gap-3 text-sm">
                  <div className="w-36 shrink-0"><DevBadge dev={e.dev} small /></div>
                  <div className="flex-1 h-2 rounded bg-surface-2 overflow-hidden">
                    <div className="h-full rounded" style={{ width: `${(e.pagerank / maxPr) * 100}%`, background: teamColor(e.dev.team) }} />
                  </div>
                  <span className="text-xs text-muted w-20 text-right">helped {Math.round(e.helped)}×</span>
                </div>
              ))}
            </div>
          </section>

          <section className="card p-4">
            <h2 className="font-semibold mb-1">Knowledge at risk</h2>
            <p className="text-xs text-muted mb-3">Hard-won fixes (4h+) that nobody else has ever reused. If the owner leaves, this is gone.</p>
            <div className="space-y-2">
              {b.at_risk.length === 0 && <Empty>None. Every hard-won fix has spread.</Empty>}
              {b.at_risk.map((r) => (
                <div key={r.solution_id} className="text-sm flex items-start justify-between gap-3">
                  <div>
                    <Link href={`/lineage/${r.solution_id}`} className="hover:underline">{r.title}</Link>
                    <div className="text-xs text-muted">{effort(r.effort_minutes, r.attempts)}</div>
                  </div>
                  <DevBadge dev={r.owner} small />
                </div>
              ))}
            </div>
          </section>

          <section className="card p-4">
            <h2 className="font-semibold mb-3">Tokens saved by reuse, per team</h2>
            <div className="space-y-2">
              {b.savings.map((s) => (
                <div key={s.team} className="flex items-center gap-3 text-sm">
                  <span className="w-20 shrink-0">{s.team}</span>
                  <div className="flex-1 h-5 rounded bg-surface-2 overflow-hidden">
                    <div className="h-full rounded" style={{ width: `${(s.tokens_saved / maxSave) * 100}%`, background: teamColor(s.team) }} />
                  </div>
                  <span className="text-xs w-28 text-right tabular-nums">~{tokens(s.tokens_saved)} · {s.reuses} reuses</span>
                </div>
              ))}
            </div>
          </section>

          <section className="card p-4">
            <h2 className="font-semibold mb-3">Help flows between teams</h2>
            {b.help_flows.length === 0 && <Empty>No cross-team help yet.</Empty>}
            <div className="space-y-2">
              {b.help_flows.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="chip" style={{ borderColor: teamColor(f.from_team) }}>{f.from_team}</span>
                  <span className="flex-1 h-px" style={{ background: `linear-gradient(90deg, ${teamColor(f.from_team)}, ${teamColor(f.to_team)})` }} />
                  <span className="text-xs text-muted">helped ×{Math.round(f.count)}</span>
                  <span className="flex-1 h-px" style={{ background: teamColor(f.to_team) }} />
                  <span className="chip" style={{ borderColor: teamColor(f.to_team) }}>{f.to_team}</span>
                </div>
              ))}
            </div>
          </section>
          <div className="lg:col-span-2"><CypherTrace trace={b.trace} /></div>
        </div>
      )}
    </div>
  );
}

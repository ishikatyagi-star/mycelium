"use client";

import { useState } from "react";
import CompareVisual from "@/components/CompareVisual";
import MemoryCard from "@/components/MemoryCard";
import { useOrg } from "@/components/OrgProvider";
import { CypherTrace, ErrorNote, Spinner } from "@/components/ui";
import { post, type Memory, type Trace } from "@/lib/api";

const PRESETS: Record<string, string[]> = {
  graphhq: [
    "access token expired returns 401, refresh it and retry the request",
    "postgres too many connections, raise max_connections",
    "kafka consumers get kicked out of the group, should we raise session.timeout.ms",
    "dedupe a CSV of customers by email column in pandas",
    "build linux/arm64 docker images in CI using buildx and qemu",
  ],
  mycelium: ["railway deploy fails after moving the service to another region"],
};

export default function ComparePage() {
  const { org, persona } = useOrg();
  const presets = PRESETS[org] || PRESETS.graphhq;
  const [q, setQ] = useState("");
  const [asked, setAsked] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<{ vector_only: Memory[]; mycelium: Memory[]; trace: Trace } | null>(null);

  const run = async (text = q) => {
    setQ(text);
    setBusy(true);
    setErr(null);
    try {
      setRes(await post(`/api/orgs/${org}/compare`, { query: text, as_dev: persona, k: 3 }));
      setAsked(text);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const vTop = res?.vector_only[0];

  return (
    <div className="space-y-5">
      <div className="max-w-4xl" data-tour="compare">
        <h1 className="text-2xl font-semibold">Vector-only vs Mycelium</h1>
        <p className="text-muted text-sm mt-1">
          Same question, same embeddings, same FalkorDB vector index. The left column stops at similarity. The right column lets the graph
          follow <span className="font-mono">SUPERSEDES</span> past fixes that later broke, attach dead ends, enforce visibility and rank
          hard-won fixes first. Benchmark: stale-fix trap <b>0/12 vs 12/12</b>.
        </p>
      </div>
      <form className="flex gap-2 max-w-4xl" onSubmit={(e) => { e.preventDefault(); run(); }}>
        <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Describe a problem…" />
        <button className="btn btn-primary shrink-0" disabled={busy || q.length < 3}>Compare</button>
      </form>
      <div className="flex flex-wrap gap-2">
        {presets.map((p) => <button key={p} className="chip hover:border-accent" onClick={() => run(p)}>{p}</button>)}
      </div>
      {busy && <Spinner />}
      <ErrorNote error={err} />
      {res && (
        <>
          {vTop && vTop.solution.status !== "active" && (
            <div className="card px-4 py-3 text-sm" style={{ borderColor: "var(--danger)" }}>
              ⚠ Vector-only&apos;s #1 answer is a <b style={{ color: "var(--danger)" }}>{vTop.solution.status}</b> fix: “{vTop.solution.title}”.
              An agent would apply the fix that already failed. Mycelium returns its replacement instead.
            </div>
          )}
          <CompareVisual query={asked} vector={res.vector_only} graph={res.mycelium} />
          <h2 className="font-semibold pt-2">The full answers</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <section className="space-y-3">
              <h2 className="font-semibold text-muted">Vector-only <span className="text-xs font-normal">(nearest past problem → its solution)</span></h2>
              {res.vector_only.map((m, i) => <MemoryCard key={m.solution.id} m={m} rank={i + 1} tone={i === 0 && m.solution.status !== "active" ? "bad" : undefined} />)}
            </section>
            <section className="space-y-3">
              <h2 className="font-semibold" style={{ color: "var(--accent)" }}>Mycelium <span className="text-xs font-normal text-muted">(vector + graph)</span></h2>
              {res.mycelium.map((m, i) => <MemoryCard key={m.solution.id} m={m} rank={i + 1} tone={i === 0 ? "good" : undefined} />)}
            </section>
          </div>
          <CypherTrace trace={res.trace} />
        </>
      )}
    </div>
  );
}

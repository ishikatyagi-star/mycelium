"use client";

import { useState } from "react";
import CompareVisual from "@/components/CompareVisual";
import MemoryCard from "@/components/MemoryCard";
import { useOrg } from "@/components/OrgProvider";
import { CypherTrace, ErrorNote, PageHeader, Spinner } from "@/components/ui";
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
      <div data-tour="compare">
        <PageHeader title="Vector search vs graph" sub="Same question, same index. Only the graph knows the top match already failed." />
      </div>
      <form className="flex gap-2 max-w-4xl" onSubmit={(e) => { e.preventDefault(); run(); }}>
        <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Describe a problem, or pick an example below" aria-label="Problem to compare" />
        <button className="btn btn-primary shrink-0" disabled={busy || q.length < 3}>Compare</button>
      </form>
      <div className="flex flex-wrap gap-2">
        {presets.map((p) => <button key={p} className="chip hover:border-[var(--primary)] !text-fg !whitespace-normal text-left" onClick={() => run(p)}>{p}</button>)}
      </div>
      {busy && <Spinner />}
      <ErrorNote error={err} />
      {res && (
        <>
          {vTop && vTop.solution.status !== "active" && (
            <div className="rounded-xl px-4 py-3 font-medium" style={{ background: "var(--bad-soft)", color: "var(--bad)" }}>
              Vector search&apos;s #1 answer already failed in production.
            </div>
          )}
          <CompareVisual query={asked} vector={res.vector_only} graph={res.mycelium} />
          <h2 className="text-lg font-bold pt-4">Full answers</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <section className="space-y-3">
              <h2 className="font-bold text-muted">Vector search</h2>
              {res.vector_only.map((m, i) => <MemoryCard key={m.solution.id} m={m} rank={i + 1} tone={i === 0 && m.solution.status !== "active" ? "bad" : undefined} />)}
            </section>
            <section className="space-y-3">
              <h2 className="font-bold" style={{ color: "var(--primary)" }}>Mycelium (vector + graph)</h2>
              {res.mycelium.map((m, i) => <MemoryCard key={m.solution.id} m={m} rank={i + 1} tone={i === 0 ? "good" : undefined} />)}
            </section>
          </div>
          <CypherTrace trace={res.trace} />
        </>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import MemoryCard from "@/components/MemoryCard";
import { useOrg } from "@/components/OrgProvider";
import PathGraph from "@/components/PathGraph";
import { CypherTrace, DevBadge, Empty, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { post, type Dev, type Memory, type Path, type Trace } from "@/lib/api";

type AskRes = {
  question_id: string;
  mode: "memory" | "routed" | "not_found";
  answer: Memory | null;
  also?: Memory[];
  routed_to: { kind: string; id: string; dev: Dev; reason: string; score: number } | null;
  candidates: { kind: string; id: string; dev: Dev; reason: string; score: number }[];
  path: Path;
  message?: string;
  trace: Trace;
};

const PRESETS: Record<string, { recall: string[]; ask: string[] }> = {
  graphhq: {
    recall: [
      "mobile app randomly logs users out when several API calls refresh the token at the same time",
      "stripe sends duplicate webhook events and we charge twice",
      "kafka consumers keep getting kicked out of the group during big batches",
      "photo uploads fail with SignatureDoesNotMatch on some phones",
    ],
    ask: [
      "Is anyone rotating the token-service signing keys right now? Our app caches the JWKS.",
      "Is the ledger events schema about to change? My ETL parses the amount field.",
      "What is the retention on the ledger.events Kafka topic?",
    ],
  },
  mycelium: {
    recall: [
      "railway deploy fails after moving the service to another region",
      "mcp server dies with connection closed when launched from another folder",
      "api container keeps restarting, workers die, 1GB memory",
    ],
    ask: ["Who knows how the hooks inject context into Claude Code?"],
  },
};

export default function AskPage() {
  const { org, persona, devs } = useOrg();
  const [mode, setMode] = useState<"recall" | "ask">("recall");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [recall, setRecall] = useState<{ results: Memory[]; trace: Trace } | null>(null);
  const [ask, setAsk] = useState<AskRes | null>(null);
  const me = devs.find((d) => d.name === persona);
  const presets = PRESETS[org] || PRESETS.graphhq;

  const run = async (text = q, m = mode) => {
    if (text.trim().length < 3) return;
    setQ(text);
    setMode(m);
    setBusy(true);
    setErr(null);
    setRecall(null);
    setAsk(null);
    try {
      if (m === "recall") setRecall(await post(`/api/orgs/${org}/recall`, { query: text, as_dev: persona, k: 5 }));
      else setAsk(await post(`/api/orgs/${org}/ask`, { question: text, as_dev: persona }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <PageHeader title="Ask the org" sub="Search everything the company has solved, or ask a question and let the graph find who knows." />

      <div className="card p-4 space-y-3">
        <div className="flex gap-1 p-1 bg-surface-2 rounded-xl w-fit text-sm">
          {(["recall", "ask"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)} className={`px-3 py-1.5 rounded-lg ${mode === m ? "bg-surface font-medium shadow-sm" : "text-muted"}`}>
              {m === "recall" ? "Search memory" : "Ask a person or agent"}
            </button>
          ))}
        </div>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); run(); }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder={mode === "recall" ? "Describe the problem you're facing…" : "Ask anything: the graph finds who knows"} />
          <button className="btn btn-primary shrink-0" disabled={busy}>{mode === "recall" ? "Recall" : "Ask"}</button>
        </form>
        <div className="flex flex-wrap gap-2">
          {(mode === "recall" ? presets.recall : presets.ask).map((p) => (
            <button key={p} className="chip hover:border-[var(--primary)] !text-fg !whitespace-normal text-left" onClick={() => run(p)}>{p}</button>
          ))}
        </div>
      </div>

      {busy && <Spinner />}
      <ErrorNote error={err} />

      {recall && (
        <div className="space-y-3">
          {recall.results.length === 0 ? (
            <Empty>Nothing in org memory matches. That&apos;s an honest &quot;not in graph&quot;: try Ask the org.</Empty>
          ) : (
            recall.results.map((m, i) => <MemoryCard key={m.solution.id} m={m} rank={i + 1} />)
          )}
          <CypherTrace trace={recall.trace} />
        </div>
      )}

      {ask && (
        <div className="space-y-3">
          {ask.mode === "memory" && ask.answer && (
            <>
              <div className="font-semibold" style={{ color: "var(--good)" }}>Answered from memory. Nobody had to be interrupted.</div>
              <MemoryCard m={ask.answer} tone="good" />
            </>
          )}
          {ask.mode === "routed" && ask.routed_to && (
            <div className="card p-4 space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold">Not in memory yet. Sent to</span>
                <DevBadge dev={ask.routed_to.dev} />
                <span className="text-muted text-sm">
                  {ask.routed_to.kind === "session" ? "via their live agent session" : "via their inbox"} · score {ask.routed_to.score}
                </span>
              </div>
              <div className="text-sm"><span className="text-muted">Why:</span> {ask.routed_to.reason}</div>
              <PathGraph path={ask.path} height={260} />
              {ask.candidates.length > 1 && (
                <div className="text-sm">
                  <div className="text-muted mb-1">Other candidates the graph considered:</div>
                  {ask.candidates.slice(1).map((c) => (
                    <div key={c.id} className="flex items-center gap-2 py-0.5 flex-wrap">
                      <DevBadge dev={c.dev} small /> <span className="text-muted text-xs">{c.score} · {c.reason.slice(0, 110)}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="text-sm text-muted">The answer will appear in <a className="underline" href="/threads">Threads</a>.</div>
            </div>
          )}
          {ask.mode === "not_found" && <Empty>{ask.message}</Empty>}
          <CypherTrace trace={ask.trace} />
        </div>
      )}
    </div>
  );
}

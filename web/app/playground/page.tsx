"use client";

import { AlertTriangle, Check, Folder, Network, Wrench } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useOrg } from "@/components/OrgProvider";
import { useTourTarget } from "@/components/Tour";
import { DevBadge, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { ago, effort, get, post, tokens, type Dev, type Memory } from "@/lib/api";
import { teamColor } from "@/lib/teams";

type Scenario = {
  session_id: string; title: string; problem: string; query: string; started_at: number; project: string;
  components: string[]; dev: Dev & { role?: string }; transcript: { role: "user" | "agent"; text: string }[];
};
type Step = { key: string; title: string; detail: string; cypher?: string | null; ms?: number | null; data: any }; // eslint-disable-line @typescript-eslint/no-explicit-any
type Staged = {
  steps: Step[]; memory: Memory | null; also: Memory[];
  scratch: { effort_minutes: number; attempts: number; tokens: number; dead_ends: string[]; author: Dev } | null;
};
type Msg = { role: "user" | "agent" | "system"; text: string; kind?: "found" | "attempt" | "fail" | "impl" };

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function Markdown({ text }: { text: string }) {
  const parts = text.split(/```[a-zA-Z]*\n?/);
  return (
    <div className="space-y-2">
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <pre key={i} className="text-[11.5px] font-mono bg-bg rounded-lg p-3 overflow-auto whitespace-pre border border-line">{p.trim()}</pre>
        ) : (
          <p key={i} className="whitespace-pre-wrap leading-relaxed"
             dangerouslySetInnerHTML={{ __html: p.trim().replace(/&/g, "&amp;").replace(/</g, "&lt;")
               .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|\s)_([^_]+?)_(?=[\s.,!?]|$)/g, "$1<i>$2</i>").replace(/`([^`]+)`/g, "<code>$1</code>") }} />
        ),
      )}
    </div>
  );
}

export default function PlaygroundPage() {
  const { persona } = useOrg();
  const [list, setList] = useState<Scenario[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [mode, setMode] = useState<null | "scratch" | "memory">(null);
  const [extra, setExtra] = useState<Msg[]>([]);
  const [staged, setStaged] = useState<Staged | null>(null);
  const [stepAt, setStepAt] = useState(-1);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [spent, setSpent] = useState({ tokens: 0, minutes: 0 });
  const runId = useRef(0);
  const chatBox = useRef<HTMLDivElement>(null);

  useEffect(() => {
    get<{ scenarios: Scenario[] }>("/api/orgs/graphhq/playground").then((r) => {
      setList(r.scenarios);
      const mine = r.scenarios.find((s) => s.dev.name === persona);
      setSel((cur) => cur || (mine || r.scenarios[0])?.session_id || null);
    }).catch((e) => setErr(String(e)));
  }, [persona]);

  const s = list?.find((x) => x.session_id === sel) || null;

  const reset = useCallback((sid: string) => {
    runId.current++;
    setSel(sid);
    setMode(null);
    setExtra([]);
    setStaged(null);
    setStepAt(-1);
    setSpent({ tokens: 0, minutes: 0 });
    setErr(null);
  }, []);

  useEffect(() => {
    const el = chatBox.current; // scroll the chat itself, never the page
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [extra.length, busy]);

  const fetchStaged = async () => {
    if (!s) return null;
    if (staged) return staged;
    const r = await post<Staged>(`/api/orgs/graphhq/playground/${s.session_id}/recall`, {});
    setStaged(r);
    return r;
  };

  const askMemory = async () => {
    if (!s) return;
    const id = ++runId.current;
    setMode("memory");
    setBusy(true);
    setErr(null);
    setStepAt(-1);
    setExtra((e) => [...e, { role: "user", text: "Before you start, check whether anyone at Graph HQ has solved this already." }]);
    try {
      const r = await fetchStaged();
      if (!r || id !== runId.current) return;
      for (let i = 0; i < r.steps.length; i++) {
        if (id !== runId.current) return;
        setStepAt(i);
        await sleep(i === 1 ? 1600 : 1200);
      }
      setStepAt(r.steps.length);
      const m = r.memory;
      if (m) {
        const dead = [...m.skipped.map((k) => `“${k.title}” ${k.reason}`), ...m.lessons.filter((l) => l.kind === "dead_end").map((l) => l.text)];
        setExtra((e) => [...e, {
          role: "agent", kind: "found",
          text: `**${m.author.name}** (${m.author.team}) already solved this, ${ago(m.solution.created_at)}: **${m.solution.title}**. It took them ${effort(m.solution.effort_minutes, m.solution.attempts)}.`
            + (dead.length ? `\n\nWhat not to do:\n${dead.slice(0, 3).map((d) => `• ${d}`).join("\n")}` : "")
            + `\n\nImplement it?`,
        }]);
      } else {
        setExtra((e) => [...e, { role: "agent", text: "Nothing in the org's memory matches this. I'll solve it, and save what I learn so the next agent doesn't have to." }]);
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      if (id === runId.current) setBusy(false);
    }
  };

  const fromScratch = async () => {
    if (!s) return;
    const id = ++runId.current;
    setMode("scratch");
    setBusy(true);
    setErr(null);
    setExtra((e) => [...e, { role: "user", text: "Go ahead and solve it." }]);
    try {
      const r = await fetchStaged();
      if (!r?.scratch || id !== runId.current) return;
      const sc = r.scratch;
      const attempts = sc.dead_ends.length ? sc.dead_ends : ["First approach didn't hold up under load"];
      const perTok = Math.round(sc.tokens / (attempts.length + 1));
      const perMin = Math.round(sc.effort_minutes / (attempts.length + 1));
      for (let i = 0; i < attempts.length; i++) {
        if (id !== runId.current) return;
        setExtra((e) => [...e, { role: "agent", kind: "attempt", text: `Attempt ${i + 1}: ${attempts[i]}` }]);
        for (let k = 1; k <= 10; k++) {
          await sleep(90);
          setSpent((p) => ({ tokens: p.tokens + perTok / 10, minutes: p.minutes + perMin / 10 }));
        }
        setExtra((e) => [...e, { role: "agent", kind: "fail", text: "Didn't work. Trying something else…" }]);
        await sleep(500);
      }
      setSpent({ tokens: sc.tokens, minutes: sc.effort_minutes });
      setExtra((e) => [...e, {
        role: "system",
        text: `${Math.max(0, sc.attempts - attempts.length)} more attempts later, it works. That's what this cost **${sc.author.name}** the first time: **${effort(sc.effort_minutes, sc.attempts)}, ~${tokens(sc.tokens)} tokens**. The answer was already in memory.`,
      }]);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      if (id === runId.current) setBusy(false);
    }
  };

  const implement = async () => {
    if (!s || !staged?.memory) return;
    setBusy(true);
    setExtra((e) => [...e, { role: "user", text: "Yes, implement it." }]);
    try {
      const r = await post<{ text: string }>(`/api/orgs/graphhq/playground/${s.session_id}/implement`, { solution_id: staged.memory.solution.id });
      setExtra((e) => [...e, { role: "agent", kind: "impl", text: r.text }]);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // the tour's "how the memory is found" step runs Ask Mycelium first if the viewer hasn't yet
  const tourAt = useTourTarget();
  useEffect(() => { if (tourAt === "pipeline" && s && mode !== "memory" && !busy) { setExtra([]); askMemory(); } }, [tourAt, s?.session_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const m = staged?.memory;
  const lastAgent = s?.transcript.filter((t) => t.role === "agent").at(-1)?.text;

  return (
    <div className="space-y-4">
      <PageHeader title="Playground" sub="Each agent below is about to solve something Graph HQ already solved. Pick one and decide." />
      <ErrorNote error={err} />
      <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] xl:grid-cols-[260px_minmax(0,1fr)_440px] gap-4 items-start">
        {/* engineers */}
        <aside className="card p-2 space-y-1" data-tour="scenarios">
          <div className="eyebrow px-2 pt-1 pb-2">Agents waiting</div>
          {!list && <Spinner label="Loading Graph HQ…" />}
          {list?.map((x) => (
            <button key={x.session_id} onClick={() => reset(x.session_id)}
                    className={`w-full text-left rounded-xl p-2.5 transition ${x.session_id === sel ? "bg-surface-2 ring-1 ring-accent" : "hover:bg-surface-2"}`}>
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-full grid place-items-center text-xs font-semibold text-black shrink-0"
                      style={{ background: teamColor(x.dev.team) }}>{x.dev.name[0]}</span>
                <div className="min-w-0">
                  <div className="text-sm font-medium">{x.dev.name} <span className="text-muted font-normal">· {x.dev.team}</span></div>
                  <div className="text-xs text-muted truncate">{x.title}</div>
                </div>
              </div>
            </button>
          ))}
        </aside>

        {/* chat */}
        <section className="card flex flex-col min-h-[560px]" data-tour="chat">
          {s && (
            <>
              <div className="border-b border-line px-4 py-3 flex items-center gap-3 flex-wrap">
                <DevBadge dev={s.dev} />
                <span className="text-sm text-muted">{s.dev.role} · {s.project}</span>
                <span className="text-xs font-mono text-muted">{s.components.join(", ")}</span>
                <span className="ml-auto text-xs text-muted">Claude Code session · {ago(s.started_at)}</span>
              </div>
              <div ref={chatBox} className="flex-1 overflow-auto p-4 space-y-3 max-h-[560px]">
                {[...s.transcript.map((t) => ({ ...t } as Msg)), ...extra].map((t, i) => (
                  <div key={i} className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
                      t.role === "user" ? "bg-[var(--primary-soft)]" : t.role === "system" ? "border border-dashed border-[var(--border-strong)] text-muted" :
                      t.kind === "found" || t.kind === "impl" ? "border" : t.kind === "fail" ? "" : "bg-surface border border-line"}`}
                         style={t.kind === "found" || t.kind === "impl" ? { borderColor: "var(--good)", background: "var(--good-soft)" }
                           : t.kind === "fail" ? { color: "var(--danger)" } : undefined}>
                      <div className="text-xs font-semibold text-subtle mb-1">
                        {t.role === "user" ? s.dev.name : t.role === "system" ? "Mycelium" : `${s.dev.name}'s agent`}
                        {t.kind === "found" && " · via Mycelium"}
                      </div>
                      <Markdown text={t.text} />
                    </div>
                  </div>
                ))}
                {busy && <Spinner label={mode === "memory" ? "Asking the org's memory…" : "Working…"} />}
              </div>
              <div className="border-t border-line p-4 space-y-3" data-tour="decision">
                {mode === null && (
                  <>
                    <div className="rounded-xl px-4 py-3 flex items-center gap-2 font-medium" style={{ background: "var(--warn-soft)", color: "var(--warn)" }}>
                      <AlertTriangle size={18} aria-hidden /> Someone at Graph HQ may have solved this before.
                    </div>
                    <div className="grid sm:grid-cols-2 gap-2">
                      <button className="btn justify-center !min-h-[48px]" onClick={fromScratch}><Wrench size={17} aria-hidden /> Solve from scratch</button>
                      <button className="btn btn-primary justify-center !min-h-[48px]" onClick={askMemory}><Network size={17} aria-hidden /> Ask Mycelium first</button>
                    </div>
                  </>
                )}
                {mode === "scratch" && (
                  <div className="flex items-center gap-3 flex-wrap text-sm">
                    <span className="font-bold tabular-nums" style={{ color: "var(--bad)" }}>~{tokens(spent.tokens)} tokens</span>
                    <span className="font-bold tabular-nums" style={{ color: "var(--bad)" }}>{effort(Math.round(spent.minutes))}</span>
                    {!busy && <button className="btn btn-primary ml-auto" onClick={() => { setExtra([]); askMemory(); }}><Network size={16} aria-hidden /> Now ask Mycelium first</button>}
                  </div>
                )}
                {mode === "memory" && !busy && m && !extra.some((x) => x.kind === "impl") && (
                  <div className="flex gap-2 flex-wrap">
                    <button className="btn btn-primary" onClick={implement}><Check size={16} aria-hidden /> Implement this</button>
                    <button className="btn" onClick={() => s && reset(s.session_id)}>Start over</button>
                  </div>
                )}
                {mode === "memory" && !busy && extra.some((x) => x.kind === "impl") && (
                  <div className="text-sm text-muted">Done. {m?.author.name} gets the credit. <button className="underline font-medium" onClick={() => s && reset(s.session_id)}>Start over</button></div>
                )}
              </div>
            </>
          )}
        </section>

        {/* pipeline */}
        <section className="card p-4 space-y-4 lg:col-span-2 xl:col-span-1" data-tour="pipeline">
          <div>
            <h2 className="font-bold">How the memory is found</h2>
            <p className="text-sm text-muted">Each step is a real FalkorDB query.</p>
          </div>
          {mode !== "memory" ? (
            <div className="text-sm text-muted space-y-3">
              {mode === "scratch" && staged?.scratch ? (
                <ScratchCompare scratch={staged.scratch} />
              ) : (
                <>
                  <ol className="space-y-2.5">
                    {["Find similar past problems", "Skip fixes that later broke", "Bring back who solved it, and the dead ends", "Hand the fix to the agent, with credit"].map((t, i) => (
                      <li key={t} className="flex items-center gap-3 text-fg">
                        <span className="w-6 h-6 rounded-full grid place-items-center text-xs font-bold shrink-0" style={{ background: "var(--primary-soft)", color: "var(--primary)" }}>{i + 1}</span>{t}
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </div>
          ) : (
            <>
              <MemoryPath s={s} m={m || null} at={stepAt} />
              <div className="space-y-2">
                {(staged?.steps || []).map((st, i) => (
                  <StepCard key={st.key} step={st} index={i} state={i < stepAt ? "done" : i === stepAt ? "running" : "pending"} />
                ))}
                {!staged && <Spinner />}
              </div>
              {stepAt >= (staged?.steps.length ?? 99) && staged?.scratch && <ScratchCompare scratch={staged.scratch} withMemory />}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function MemoryPath({ s, m, at }: { s: Scenario | null; m: Memory | null; at: number }) {
  const nodes: { label: string; sub: string; color: string; show: number; bad?: boolean }[] = [
    { label: `${s?.dev.name}'s problem`, sub: s?.dev.team || "", color: teamColor(s?.dev.team), show: 0 },
    { label: "Similar past task", sub: m ? `similarity ${m.similarity.toFixed(2)}` : "", color: "#64748b", show: 1 },
    ...(m?.skipped.length ? [{ label: "Stale fix", sub: "skipped", color: "#dc2626", show: 2, bad: true }] : []),
    { label: "Current fix", sub: m ? effort(m.solution.effort_minutes, m.solution.attempts) : "", color: "#15803d", show: 2 },
    { label: m ? m.author.name : "Author", sub: m ? `${m.author.team} · ${m.project?.name ?? ""}` : "", color: teamColor(m?.author.team), show: 3 },
  ];
  return (
    <div className="rounded-xl border border-line bg-bg p-3">
      <div className="flex flex-wrap items-center gap-y-2 gap-x-1">
        {nodes.map((n, i) => {
          const on = at >= n.show;
          return (
            <div key={i} className="flex items-center gap-1">
              {i > 0 && <span className="w-6 h-0.5 rounded transition-all duration-500" style={{ background: on ? n.color : "var(--border)" }} />}
              <div className="rounded-lg px-2 py-1.5 text-center transition-all duration-500 border"
                   style={{ borderColor: on ? n.color : "var(--border)", opacity: on ? 1 : 0.35, transform: on ? "scale(1)" : "scale(0.95)",
                            textDecoration: n.bad && on ? "line-through" : undefined }}>
                <div className="text-xs font-bold whitespace-nowrap" style={{ color: on ? n.color : undefined }}>{n.label}</div>
                <div className="text-xs text-subtle whitespace-nowrap">{n.sub}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StepCard({ step, index, state }: { step: Step; index: number; state: "pending" | "running" | "done" }) {
  const [open, setOpen] = useState(false);
  if (state === "pending") {
    return <div className="rounded-xl border border-line px-3 py-2 text-sm text-muted opacity-50">{index + 1}. {step.title}</div>;
  }
  const d = step.data || {};
  return (
    <div className="rounded-xl border px-3 py-2.5 text-sm space-y-2 transition-all"
         style={{ borderColor: state === "running" ? "var(--accent)" : "var(--border)" }}>
      <div className="flex items-center gap-2">
        {state === "running" ? <span className="inline-block w-3 h-3 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          : <Check size={16} style={{ color: "var(--good)" }} aria-hidden />}
        <span className="font-medium">{index + 1}. {step.title}</span>
        {step.ms != null && <span className="ml-auto text-xs text-subtle font-mono">{step.ms} ms</span>}
      </div>
      <p className="text-xs text-muted">{step.detail}</p>
      {step.key === "vector" && d.candidates && (
        <div className="space-y-1">
          {d.candidates.map((c: { solution_id: string; title: string; similarity: number; status: string; author: Dev }) => (
            <div key={c.solution_id} className="text-xs">
              <div className="flex justify-between gap-2">
                <span className="truncate" style={{ color: c.status !== "active" ? "var(--danger)" : undefined }}>
                  {c.status !== "active" && <AlertTriangle size={12} className="inline mr-1" aria-hidden />}{c.title}
                </span>
                <span className="font-mono text-muted shrink-0">{c.similarity.toFixed(2)}</span>
              </div>
              <div className="h-1.5 rounded bg-surface-2 overflow-hidden">
                <div className="h-full rounded" style={{ width: `${Math.max(5, (c.similarity - 0.5) * 200)}%`,
                  background: c.status !== "active" ? "var(--danger)" : teamColor(c.author?.team) }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {step.key === "walk" && (
        d.skipped?.length ? d.skipped.map((k: { id: string; title: string; reason: string }) => (
          <div key={k.id} className="text-xs" style={{ color: "var(--danger)" }}>
            <s>{k.title}</s> <span className="text-muted">→ skipped: {k.reason}</span>
          </div>
        )) : <div className="text-xs text-muted">No later failures on record: the fix is current.</div>
      )}
      {step.key === "expand" && d.author && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <DevBadge dev={d.author} small /> {d.project && <span className="chip"><Folder size={12} aria-hidden /> {d.project.name}</span>}
          </div>
          {d.lessons?.slice(0, 4).map((l: { text: string; kind: string }, i: number) => (
            <div key={i} className="text-xs flex gap-2">
              <span className="uppercase font-bold text-[11px] mt-0.5 w-16 shrink-0"
                    style={{ color: l.kind === "dead_end" ? "var(--danger)" : l.kind === "pitfall" ? "var(--warn)" : "var(--ok)" }}>
                {l.kind.replace("_", " ")}
              </span>
              <span>{l.text}</span>
            </div>
          ))}
        </div>
      )}
      {step.key === "rank" && d.score != null && (
        <div className="text-xs text-muted">score {d.score} · similarity {d.similarity}</div>
      )}
      {step.cypher && (
        <div>
          <button className="text-xs font-semibold font-mono" style={{ color: "var(--primary)" }} onClick={() => setOpen(!open)}>
            {open ? "hide" : "show"} Cypher
          </button>
          {open && <pre className="text-xs font-mono whitespace-pre-wrap text-muted mt-1">{step.cypher}</pre>}
        </div>
      )}
    </div>
  );
}

function ScratchCompare({ scratch, withMemory }: { scratch: NonNullable<Staged["scratch"]>; withMemory?: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-sm">
      <div className="rounded-xl border p-3" style={{ borderColor: "var(--danger)" }}>
        <div className="eyebrow">From scratch</div>
        <div className="font-bold text-lg mt-1" style={{ color: "var(--bad)" }}>{effort(scratch.effort_minutes, scratch.attempts)}</div>
        <div className="text-xs text-muted">~{tokens(scratch.tokens)} tokens, {scratch.dead_ends.length} dead ends repeated</div>
        <div className="text-xs text-subtle mt-1">what it cost {scratch.author.name} the first time</div>
      </div>
      <div className="rounded-xl border p-3" style={{ borderColor: "var(--good)", opacity: withMemory ? 1 : 0.6 }}>
        <div className="eyebrow">With Mycelium</div>
        <div className="font-bold text-lg mt-1" style={{ color: "var(--good)" }}>~1 second</div>
        <div className="text-xs text-muted">0 dead ends, fix credited</div>
        <div className="text-xs text-subtle mt-1">~{tokens(Math.round(scratch.tokens * 0.8))} tokens saved (est.)</div>
      </div>
    </div>
  );
}

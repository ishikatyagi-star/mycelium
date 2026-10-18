"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useOrg } from "@/components/OrgProvider";
import { useTour } from "@/components/Tour";
import { get, tokens, type Overview } from "@/lib/api";
import { teamColor } from "@/lib/teams";

const TEAM_BLURB: Record<string, string> = {
  Identity: "Login, tokens, user profiles",
  Payments: "Checkout, webhooks, the ledger",
  Data: "Event pipeline, warehouse, reporting",
  Mobile: "The mobile app, push, offline sync",
  Platform: "CI, Kubernetes, observability",
};

export default function StoryPage() {
  const tour = useTour();
  const { setOrg, setPersona } = useOrg();
  const [ov, setOv] = useState<Overview | null>(null);
  useEffect(() => {
    get<Overview>("/api/orgs/graphhq/overview").then(setOv).catch(() => {});
  }, []);
  const pick = (dev: string) => {
    setOrg("graphhq");
    setPersona(dev);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-16 pb-10">
      {/* hero */}
      <section className="pt-8 text-center space-y-5" data-tour="hero">
        <div className="chip mx-auto" style={{ color: "var(--accent)" }}>Graph Hacks 2026 · built on FalkorDB</div>
        <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight leading-tight max-w-4xl mx-auto">
          Your company&apos;s AI agents keep re-solving <span style={{ color: "var(--accent)" }}>last quarter&apos;s</span> problems,
          and can&apos;t see <span style={{ color: "var(--accent-2)" }}>each other</span>.
        </h1>
        <p className="text-lg text-muted max-w-3xl mx-auto">
          <b className="text-fg">Mycelium</b> connects every AI agent in a company through one shared context graph. Agents recall what
          anyone solved before, see what other teams are working on right now, and talk to each other&apos;s agents.
        </p>
        <div className="flex flex-wrap gap-3 justify-center">
          <Link href="/playground" className="btn btn-primary !px-5 !py-2.5">Try the playground →</Link>
          <button className="btn !px-5 !py-2.5" onClick={() => tour.start()}>▶ Take the 2-minute tour</button>
          <Link href="/live" className="btn !px-5 !py-2.5">Watch the company live</Link>
        </div>
        {ov && (
          <div className="flex flex-wrap justify-center gap-6 text-sm text-muted pt-2">
            <span><b className="text-fg">{ov.counts.live_sessions}</b> agents live right now</span>
            <span><b className="text-fg">{ov.counts.solutions}</b> memories</span>
            <span><b className="text-fg">{ov.counts.sessions}</b> agent sessions</span>
            <span><b className="text-fg">~{tokens(ov.counts.tokens_saved)}</b> tokens saved by reuse</span>
          </div>
        )}
      </section>

      {/* problem */}
      <section className="space-y-5">
        <h2 className="text-2xl font-semibold">The problem: knowledge is split across time and across teams</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="card p-5 space-y-3">
            <div className="text-xs uppercase tracking-wider text-muted">Across time: history repeats</div>
            <p className="leading-relaxed">
              Ten weeks ago <b>Yash</b> (Payments) spent <b>3 working days and 14 attempts</b> on a token-refresh race that logged users out.
              Retrying on 401 made it worse. He found the real fix, and it lives in his chat history.
            </p>
            <p className="leading-relaxed">
              Today <b>Neha</b> (Mobile) hits the same bug. Her agent has never heard of Yash&apos;s three days, and proposes the
              <span style={{ color: "var(--danger)" }}> exact fix that already failed</span>. Nobody updated the docs; nobody remembers.
            </p>
            <div className="text-sm text-muted">Cost: the same days, the same ~210k tokens, the same dead ends, again.</div>
          </div>
          <div className="card p-5 space-y-3">
            <div className="text-xs uppercase tracking-wider text-muted">Across teams: right now, in parallel</div>
            <p className="leading-relaxed">
              <b>Meera</b>&apos;s agent (Identity) is rotating the token-signing keys while <b>Tom</b>&apos;s mobile app caches the old ones.
              <b> Kabir</b>&apos;s agent (Data) renames a field that three other teams parse.
            </p>
            <p className="leading-relaxed">
              Every agent is an island: duplicate work goes unnoticed, breaking changes go unannounced, and the agent that has the
              answer is on another team.
            </p>
            <div className="text-sm text-muted">Cost: incidents, duplicated effort, and people interrupting people.</div>
          </div>
        </div>
      </section>

      {/* org */}
      <section className="space-y-5" data-tour="org">
        <div>
          <h2 className="text-2xl font-semibold">Meet Graph HQ, our demo company</h2>
          <p className="text-muted mt-1 max-w-3xl">
            A fictional engineering org: 14 engineers in 5 teams, owning 17 services that depend on each other, with about 4 months
            of AI-agent history across 5 projects. Each engineer works with an AI coding agent. Click anyone to see their agent in the playground.
          </p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {(ov?.teams || []).map((t) => (
            <div key={t.name} className="card p-4 space-y-3" style={{ borderTop: `3px solid ${teamColor(t.name)}` }}>
              <div>
                <div className="font-semibold" style={{ color: teamColor(t.name) }}>{t.name}</div>
                <div className="text-xs text-muted">{TEAM_BLURB[t.name]}</div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {t.devs.map((d) => (
                  <Link key={d} href="/playground" onClick={() => pick(d)} className="chip hover:border-accent">
                    <span className="w-5 h-5 rounded-full grid place-items-center text-[10px] font-semibold text-black"
                          style={{ background: teamColor(t.name) }}>{d[0]}</span>{d}
                  </Link>
                ))}
              </div>
              <div className="text-[11px] font-mono text-muted leading-relaxed">{t.components.join(" · ")}</div>
            </div>
          ))}
        </div>
      </section>

      {/* how */}
      <section className="space-y-5">
        <h2 className="text-2xl font-semibold">How Mycelium solves it</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            ["1", "Every agent session becomes a node", "When an engineer's agent starts a task, Mycelium records it in the graph: who, which team, which services it touches, which project. That one node is both memory and presence.", "/live", "See live agents"],
            ["2", "Before solving: ask the org's memory", "A vector search finds similar past problems; the graph then walks past fixes that later broke, brings back the dead ends, ranks hard-won fixes first and credits the author.", "/playground", "Try it in the playground"],
            ["3", "While working: agents coordinate", "Overlapping work is detected across teams. Questions are routed to whoever is live on the relevant service. Changes ripple over DEPENDS_ON to exactly the agents affected.", "/live", "Announce a change"],
            ["4", "Knowledge compounds", "Answers become memory. Fixes build on fixes across projects. PageRank shows who really knows what, and which hard-won knowledge only one person holds.", "/brain", "Open the company brain"],
          ].map(([n, title, body, href, cta]) => (
            <div key={n} className="card p-5 flex flex-col gap-3">
              <div className="w-8 h-8 rounded-full grid place-items-center font-semibold text-black" style={{ background: "var(--accent)" }}>{n}</div>
              <div className="font-semibold">{title}</div>
              <p className="text-sm text-muted leading-relaxed flex-1">{body}</p>
              <Link href={href} className="text-sm" style={{ color: "var(--accent)" }}>{cta} →</Link>
            </div>
          ))}
        </div>
        <div className="card p-4 text-sm text-muted">
          It works inside the tools engineers already use: an <b className="text-fg">MCP server</b> plus <b className="text-fg">Claude Code hooks</b>
          inject relevant memories, questions for you and change warnings straight into the agent&apos;s context.
        </div>
      </section>

      {/* why graph */}
      <section className="space-y-5">
        <h2 className="text-2xl font-semibold">Why it has to be a graph</h2>
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-left">
              <tr><th className="p-3">The agent needs to know…</th><th className="p-3">A vector store</th><th className="p-3">Mycelium on FalkorDB</th></tr>
            </thead>
            <tbody>
              {[
                ["Has anyone solved this before?", "✓ finds similar text", "✓ vector index on every past task"],
                ["…and is that fix still good?", "✗ returns the broken one", "✓ walks SUPERSEDES past failures"],
                ["What did they try that didn't work?", "✗", "✓ dead-end lessons linked to the fix"],
                ["Who is working on this right now?", "✗", "✓ live sessions TOUCHES services"],
                ["Who breaks if I change this service?", "✗", "✓ DEPENDS_ON up to 3 hops → live agents"],
                ["Who really knows this area?", "✗", "✓ PageRank over who credits whom"],
              ].map(([q, v, g]) => (
                <tr key={q} className="border-t border-line">
                  <td className="p-3">{q}</td>
                  <td className="p-3" style={{ color: v.startsWith("✗") ? "var(--danger)" : undefined }}>{v}</td>
                  <td className="p-3" style={{ color: "var(--accent)" }}>{g}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* proof */}
      <section className="space-y-5">
        <h2 className="text-2xl font-semibold">Proof, not promises</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            ["12/12 vs 0/12", "Stale-fix trap: Mycelium returns the current fix; vector-only returns the broken one every time."],
            ["8/8 vs 4/8", "Questions routed to the right person, who is live on the relevant service right now."],
            ["1.0 / 1.0", "Precision / recall of which live agents get warned when a service changes."],
            ["50 agents, 0 errors", "Concurrent agents running the full loop against one graph; hybrid recall ~3 ms p50."],
          ].map(([big, small]) => (
            <div key={big} className="card p-5">
              <div className="text-2xl font-semibold" style={{ color: "var(--accent)" }}>{big}</div>
              <div className="text-sm text-muted mt-2">{small}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted">Benchmark on our synthetic org; cases and caveats in the repo&apos;s eval/results.md.</p>
      </section>

      <section className="card p-8 text-center space-y-4">
        <h2 className="text-2xl font-semibold">See it for yourself</h2>
        <p className="text-muted">Pick an engineer, read their agent&apos;s chat, and watch Mycelium fetch the memory of a past agent.</p>
        <div className="flex flex-wrap gap-3 justify-center">
          <Link href="/playground" className="btn btn-primary !px-5 !py-2.5">Open the playground →</Link>
          <button className="btn !px-5 !py-2.5" onClick={() => tour.start()}>▶ Take the tour</button>
        </div>
      </section>
    </div>
  );
}

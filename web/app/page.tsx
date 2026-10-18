"use client";

import { ArrowRight, Compass, Database, GitBranch, Radio, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useOrg } from "@/components/OrgProvider";
import { useTour } from "@/components/Tour";
import { get, tokens, type Overview } from "@/lib/api";
import { teamColor } from "@/lib/teams";

export default function OverviewPage() {
  const tour = useTour();
  const { setOrg, setPersona } = useOrg();
  const [ov, setOv] = useState<Overview | null>(null);
  useEffect(() => {
    get<Overview>("/api/orgs/graphhq/overview").then(setOv).catch(() => {});
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-20 pb-8">
      {/* hero */}
      <section className="pt-10 text-center" data-tour="hero">
        <div className="eyebrow">Shared memory for AI agents · built on FalkorDB</div>
        <h1 className="mt-4 text-4xl sm:text-6xl font-extrabold tracking-tight leading-[1.08] max-w-4xl mx-auto">
          Your AI agents keep solving problems your company already solved.
        </h1>
        <p className="mt-5 text-lg sm:text-xl text-muted max-w-2xl mx-auto">
          Mycelium gives every agent one shared memory, so a problem solved once is never solved twice.
        </p>
        <div className="mt-8 flex flex-wrap gap-3 justify-center">
          <Link href="/playground" className="btn btn-primary !px-6 !min-h-[48px] !text-base">
            See it work <ArrowRight size={18} aria-hidden />
          </Link>
          <button className="btn !px-6 !min-h-[48px] !text-base" onClick={() => tour.start()}>
            <Compass size={18} aria-hidden /> 2-minute tour
          </button>
        </div>
      </section>

      {/* problem */}
      <section>
        <div className="eyebrow mb-4">The problem</div>
        <div className="grid md:grid-cols-2 gap-5">
          <div className="card p-7">
            <div className="text-5xl font-extrabold tracking-tight" style={{ color: "var(--bad)" }}>3 days</div>
            <p className="mt-3 text-lg leading-relaxed">
              Yash spent 3 days fixing a login bug. Ten weeks later, Neha&apos;s agent is about to repeat the fix that <b>already failed</b>.
            </p>
            <p className="mt-2 text-muted">Agents start every session blank.</p>
          </div>
          <div className="card p-7">
            <div className="text-5xl font-extrabold tracking-tight" style={{ color: "var(--bad)" }}>0 warning</div>
            <p className="mt-3 text-lg leading-relaxed">
              Meera&apos;s agent is rotating the keys Tom&apos;s app depends on. <b>Neither agent knows</b> about the other.
            </p>
            <p className="mt-2 text-muted">Agents can&apos;t see each other.</p>
          </div>
        </div>
      </section>

      {/* how */}
      <section>
        <div className="eyebrow mb-4">How Mycelium fixes it</div>
        <div className="grid md:grid-cols-3 gap-5">
          {[
            { icon: Database, title: "Remember", body: "Every agent session, fix and dead end goes into one graph.", href: "/live", cta: "Live org" },
            { icon: Search, title: "Recall", body: "Before solving, an agent checks what the company already knows, skipping fixes that broke.", href: "/playground", cta: "Playground" },
            { icon: Radio, title: "Coordinate", body: "Questions and breaking changes reach exactly the agents they affect.", href: "/live", cta: "Live org" },
          ].map(({ icon: Icon, title, body, href, cta }) => (
            <Link key={title} href={href} className="card p-6 group hover:border-[var(--primary)] transition-colors">
              <div className="w-10 h-10 rounded-xl grid place-items-center" style={{ background: "var(--primary-soft)", color: "var(--primary)" }}>
                <Icon size={20} aria-hidden />
              </div>
              <h3 className="mt-4 text-lg font-bold">{title}</h3>
              <p className="mt-1.5 text-muted">{body}</p>
              <div className="mt-4 text-sm font-semibold flex items-center gap-1" style={{ color: "var(--primary)" }}>
                {cta} <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" aria-hidden />
              </div>
            </Link>
          ))}
        </div>
        <Link href="/compare" className="mt-5 card px-6 py-4 flex items-center gap-3 hover:border-[var(--primary)] transition-colors">
          <GitBranch size={20} style={{ color: "var(--primary)" }} aria-hidden />
          <span className="font-semibold">Why a graph?</span>
          <span className="text-muted">A vector search finds look-alikes. Only a graph knows a fix was replaced.</span>
          <ArrowRight size={16} className="ml-auto text-subtle" aria-hidden />
        </Link>
      </section>

      {/* org */}
      <section data-tour="org">
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <div className="eyebrow">Meet the demo company</div>
            <h2 className="text-2xl font-bold mt-1">Graph HQ</h2>
          </div>
          <p className="text-muted sm:ml-4">14 engineers, 5 teams, 17 services, 4 months of agent history. Pick someone to see their agent.</p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {(ov?.teams || []).map((t) => (
            <div key={t.name} className="card p-4">
              <div className="font-bold" style={{ color: teamColor(t.name) }}>{t.name}</div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {t.devs.map((d) => (
                  <Link key={d} href="/playground" onClick={() => { setOrg("graphhq"); setPersona(d); }}
                        className="chip hover:border-[var(--primary)] !text-fg">
                    <span className="w-5 h-5 rounded-full grid place-items-center text-[11px] font-bold text-white"
                          style={{ background: teamColor(t.name) }}>{d[0]}</span>{d}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* proof */}
      <section data-tour="proof">
        <div className="eyebrow mb-4">Measured, not claimed</div>
        <div className="card grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-line">
          {[
            ["12 / 12", "returns the current fix", "vector-only: 0 / 12"],
            ["8 / 8", "questions reach the right person", "vector-only: 4 / 8"],
            ["100%", "of affected agents warned of a change", "and nobody else"],
            ["50 agents", "running at once, 0 errors", `${ov ? `~${tokens(ov.counts.tokens_saved)}` : "…"} tokens saved so far`],
          ].map(([big, label, sub]) => (
            <div key={big} className="p-6">
              <div className="text-3xl font-extrabold tracking-tight" style={{ color: "var(--primary)" }}>{big}</div>
              <div className="mt-1 font-medium">{label}</div>
              <div className="text-sm text-subtle">{sub}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="text-center">
        <h2 className="text-3xl font-bold">Watch an agent ask before it solves.</h2>
        <Link href="/playground" className="btn btn-primary !px-6 !min-h-[48px] !text-base mt-6">
          Open the playground <ArrowRight size={18} aria-hidden />
        </Link>
      </section>
    </div>
  );
}

"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, Suspense, useCallback, useContext, useEffect, useState } from "react";

type Step = { path: string; target: string; title: string; body: string };

// The guided story: each step points at the exact place in the product where something happens.
export const STEPS: Step[] = [
  { path: "/", target: "hero", title: "The problem in one line",
    body: "Every engineer at a company now works with an AI agent. Each agent starts blank: it can't see what other agents solved last month, or what they're changing right now." },
  { path: "/", target: "org", title: "Meet Graph HQ (our demo company)",
    body: "A fictional 14-person engineering org: 5 teams owning 17 services, with about 4 months of agent history. Everything you'll see is stored as one graph in FalkorDB." },
  { path: "/playground", target: "scenarios", title: "Engineers whose agents are mid-task",
    body: "Pick an engineer. Their AI agent has been chatting with them and is about to start fixing something. It doesn't know that someone else at Graph HQ already solved it." },
  { path: "/playground", target: "chat", title: "The conversation so far",
    body: "Read the agent's plan. Often it's exactly the fix that already failed for someone else months ago." },
  { path: "/playground", target: "decision", title: "The decision: from scratch, or ask the org?",
    body: "Without Mycelium the agent starts from scratch. With Mycelium it checks the org's memory first. Try both: the scratch path replays what it actually cost the first time." },
  { path: "/playground", target: "pipeline", title: "How the memory is fetched",
    body: "Step by step: a vector search finds similar past problems, the graph walks past fixes that later broke, brings back who solved it and the dead ends, then ranks and credits. Each step shows the real Cypher query." },
  { path: "/live", target: "live-graph", title: "The org, live",
    body: "Teams own services; arrows are DEPENDS_ON. Every glowing dot is an agent running right now, attached to what it touches. Questions travel between agents as particles." },
  { path: "/live", target: "notice", title: "Change something, see who's affected",
    body: "Announce a change to a service. Mycelium walks DEPENDS_ON up to 3 hops and warns only the live agents whose work depends on it." },
  { path: "/live", target: "feed", title: "Agents talking to agents",
    body: "Agents ask the org; the graph routes each question to whoever is live on the relevant service (or owns it, or solved it before). Answers become memory." },
  { path: "/compare", target: "compare", title: "Why it has to be a graph",
    body: "Same question, same vector index. Vector-only hands back the fix that caused the outage; the graph knows it was superseded. Benchmark: 0/12 vs 12/12." },
  { path: "/brain", target: "experts", title: "The company brain",
    body: "Who actually knows what (PageRank over who credits whom), which hard-won fixes only one person has ever touched, and how help flows between teams." },
];

type Ctx = { active: boolean; step: number; start: () => void; stop: () => void; go: (i: number) => void };
const TourContext = createContext<Ctx | null>(null);

export function TourProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);
  const router = useRouter();
  const go = useCallback((i: number) => {
    if (i < 0 || i >= STEPS.length) {
      setActive(false);
      return;
    }
    setStep(i);
    setActive(true);
    if (window.location.pathname !== STEPS[i].path) router.push(STEPS[i].path);
  }, [router]);
  const start = useCallback(() => go(0), [go]);
  const stop = useCallback(() => setActive(false), []);
  return (
    <TourContext.Provider value={{ active, step, start, stop, go }}>
      {children}
      <Suspense fallback={null}>{active && <Overlay />}</Suspense>
    </TourContext.Provider>
  );
}

export function useTour() {
  const c = useContext(TourContext);
  if (!c) throw new Error("useTour outside TourProvider");
  return c;
}

function Overlay() {
  const { step, go, stop } = useTour();
  const path = usePathname();
  const s = STEPS[step];
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    let raf = 0;
    let scrolled = false;
    const find = () => {
      const el = path === s.path ? document.querySelector(`[data-tour="${s.target}"]`) : null;
      if (el) {
        if (!scrolled) {
          el.scrollIntoView({ block: "center", behavior: "smooth" });
          scrolled = true;
        }
        setRect(el.getBoundingClientRect());
      } else setRect(null);
      raf = window.setTimeout(find, 250) as unknown as number;
    };
    find();
    return () => clearTimeout(raf);
  }, [path, s.path, s.target]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") stop();
      if (e.key === "ArrowRight") go(step + 1);
      if (e.key === "ArrowLeft") go(step - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, stop, step]);

  const pad = 8;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const cardW = Math.min(380, vw - 32);
  let left = 16, top = vh - 260;
  if (rect) {
    const below = rect.bottom + 14 + 220 < vh;
    top = below ? rect.bottom + 14 : Math.max(16, rect.top - 230);
    left = Math.min(Math.max(16, rect.left), vw - cardW - 16);
    if (rect.height > vh * 0.6) { top = Math.max(16, rect.top + 16); left = Math.min(rect.right - cardW - 16, vw - cardW - 16); }
  }

  return (
    <div className="fixed inset-0 z-[60] pointer-events-none">
      {rect ? (
        <div className="absolute rounded-xl transition-all duration-300"
             style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2,
                      boxShadow: "0 0 0 9999px rgba(0,0,0,0.55), 0 0 0 2px var(--accent)" }} />
      ) : (
        <div className="absolute inset-0 bg-black/40" />
      )}
      <div className="absolute card p-4 shadow-2xl pointer-events-auto transition-all duration-300"
           style={{ left, top, width: cardW, borderColor: "var(--accent)" }}>
        <div className="text-[11px] uppercase tracking-wider text-accent font-semibold">Step {step + 1} of {STEPS.length}</div>
        <h3 className="font-semibold mt-1">{s.title}</h3>
        <p className="text-sm text-muted mt-1.5 leading-relaxed">{s.body}</p>
        <div className="flex items-center justify-between mt-3">
          <button className="text-xs text-muted hover:text-fg" onClick={stop}>Skip tour</button>
          <div className="flex gap-2">
            {step > 0 && <button className="btn !py-1 !px-2.5 !text-xs" onClick={() => go(step - 1)}>Back</button>}
            <button className="btn btn-primary !py-1 !px-3 !text-xs" onClick={() => go(step + 1)}>
              {step === STEPS.length - 1 ? "Finish" : "Next →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, Suspense, useCallback, useContext, useEffect, useState } from "react";

type Step = { path: string; target: string; title: string; body: string };

// The guided story: each step points at the exact place in the product where something happens.
export const STEPS: Step[] = [
  { path: "/", target: "hero", title: "The problem",
    body: "Every engineer now works with an AI agent, and each agent starts blank." },
  { path: "/", target: "org", title: "Graph HQ, our demo company",
    body: "14 engineers in 5 teams. Their agents' history lives in one graph in FalkorDB." },
  { path: "/playground", target: "scenarios", title: "Agents about to repeat work",
    body: "Each of these agents is about to solve something a teammate already solved." },
  { path: "/playground", target: "chat", title: "What the agent plans to do",
    body: "Read its plan. Often it's the exact fix that already failed for someone else." },
  { path: "/playground", target: "decision", title: "Your choice",
    body: "Solve from scratch and see what it costs, or ask Mycelium first." },
  { path: "/playground", target: "pipeline", title: "How the memory is found",
    body: "Find similar problems, skip fixes that broke, bring back who solved it. Each step is a real query." },
  { path: "/live", target: "live-graph", title: "The company, live",
    body: "Each dot is an agent working right now, attached to the services it touches." },
  { path: "/live", target: "notice", title: "Change something",
    body: "Mycelium warns only the agents whose work depends on what changed." },
  { path: "/live", target: "feed", title: "Agents asking agents",
    body: "Questions go to whoever is working on that service now. Answers become memory." },
  { path: "/compare", target: "compare", title: "Why it needs a graph",
    body: "A vector search returns the closest match, even one that already failed. The graph knows it was replaced." },
  { path: "/brain", target: "experts", title: "Who knows what",
    body: "See who others rely on, and which hard-won fixes only one person holds." },
];

type Ctx = { active: boolean; step: number; seen: boolean; start: () => void; stop: () => void; go: (i: number) => void };
const TourContext = createContext<Ctx | null>(null);

export function TourProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);
  const [seen, setSeen] = useState(true); // assume seen until we can read storage (avoids a flash)
  const router = useRouter();
  useEffect(() => {
    try { setSeen(localStorage.getItem("myc.toured") === "1"); } catch { setSeen(false); }
  }, []);
  const go = useCallback((i: number) => {
    if (i < 0 || i >= STEPS.length) {
      setActive(false);
      return;
    }
    setStep(i);
    setActive(true);
    if (window.location.pathname !== STEPS[i].path) router.push(STEPS[i].path);
  }, [router]);
  const start = useCallback(() => {
    setSeen(true);
    try { localStorage.setItem("myc.toured", "1"); } catch {}
    go(0);
  }, [go]);
  const stop = useCallback(() => setActive(false), []);
  return (
    <TourContext.Provider value={{ active, step, seen, start, stop, go }}>
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
                      boxShadow: "0 0 0 9999px rgba(15,23,42,0.45), 0 0 0 3px var(--primary)" }} />
      ) : (
        <div className="absolute inset-0 bg-black/40" />
      )}
      <div className="absolute card p-4 shadow-2xl pointer-events-auto transition-all duration-300"
           style={{ left, top, width: cardW, borderColor: "var(--accent)" }}>
        <div className="eyebrow" style={{ color: "var(--primary)" }}>Step {step + 1} of {STEPS.length}</div>
        <h3 className="text-lg font-bold mt-1">{s.title}</h3>
        <p className="text-muted mt-1.5">{s.body}</p>
        <div className="flex items-center justify-between mt-3">
          <button className="text-sm text-muted hover:text-fg" onClick={stop}>Skip</button>
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

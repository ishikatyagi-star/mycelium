"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API, ago, get, tokens, type GLink, type GNode, type LiveSession } from "@/lib/api";
import { teamColor } from "@/lib/teams";
import { fitTo } from "./fit";
import ForceGraph, { useCssVar, useSize } from "./ForceGraph";
import NoticeModal from "./NoticeModal";
import { useOrg } from "./OrgProvider";
import { DevBadge } from "./ui";

/* eslint-disable @typescript-eslint/no-explicit-any */
type FeedItem = { id: number; at: number; kind: string; text: React.ReactNode; color: string };
type Effect = { nodes: string[]; color: string; until: number };
type TempLink = { source: string; target: string; type: string; color: string; until: number };

const EVENT_TYPES = ["session_started", "session_ended", "overlap", "memory_saved", "reuse", "question_asked",
  "question_routed", "answer", "notice", "handoff"];

export default function LiveOrg() {
  const { org, overview, refreshOverview } = useOrg();
  const [setEl, size] = useSize<HTMLDivElement>();
  const fgRef = useRef<any>(null);
  const nodeMap = useRef(new Map<string, any>());
  const [graph, setGraph] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] });
  const [live, setLive] = useState<LiveSession[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [effects, setEffects] = useState<Effect[]>([]);
  const [temp, setTemp] = useState<TempLink[]>([]);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [connected, setConnected] = useState(false);
  const askers = useRef(new Map<string, string>());
  const seq = useRef(0);
  const label = useCssVar("--graph-label", "#e4eee9");
  const linkColor = useCssVar("--graph-link", "rgba(228,238,233,.13)");
  const bg = useCssVar("--graph-bg", "#070b0a");

  const load = useCallback(async () => {
    try {
      const [g, l] = await Promise.all([
        get<{ nodes: GNode[]; links: GLink[] }>(`/api/orgs/${org}/graph?view=org`),
        get<{ sessions: LiveSession[] }>(`/api/orgs/${org}/live`),
      ]);
      setLive(l.sessions);
      const keep = g.nodes.filter((n) => n.label !== "Dev");
      const ids = new Set(keep.map((n) => n.id));
      const nodes = keep.map((n) => {
        const old = nodeMap.current.get(n.id);
        const merged = old ? Object.assign(old, n) : { ...n };
        nodeMap.current.set(n.id, merged);
        return merged;
      });
      for (const k of [...nodeMap.current.keys()]) if (!ids.has(k)) nodeMap.current.delete(k);
      const links = g.links.filter((x) => ids.has(x.source as string) && ids.has(x.target as string)).map((x) => ({ ...x }));
      setGraph({ nodes, links });
    } catch {}
  }, [org]);

  useEffect(() => {
    nodeMap.current.clear();
    setFeed([]);
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load]);

  const push = useCallback((kind: string, text: React.ReactNode, color: string) => {
    setFeed((f) => [{ id: ++seq.current, at: Date.now() / 1000, kind, text, color }, ...f].slice(0, 60));
  }, []);
  const pulse = useCallback((nodes: string[], color: string, ms = 6000) => {
    setEffects((e) => [...e.filter((x) => x.until > Date.now()), { nodes, color, until: Date.now() + ms }]);
  }, []);
  const flow = useCallback((links: Omit<TempLink, "until">[], ms = 7000) => {
    setTemp((t) => [...t.filter((x) => x.until > Date.now()), ...links.map((l) => ({ ...l, until: Date.now() + ms }))]);
  }, []);

  const liveRef = useRef(live);
  liveRef.current = live;
  const sessionOf = (dev?: string) => {
    const s = liveRef.current.find((x) => x.dev.name === dev);
    return s ? `Session:${s.id}` : null;
  };

  // live event stream (API event bus -> SSE)
  useEffect(() => {
    const es = new EventSource(`${API}/api/orgs/${org}/events`);
    let reloadTimer: ReturnType<typeof setTimeout> | null = null;
    const reloadSoon = () => {
      if (reloadTimer) clearTimeout(reloadTimer);
      reloadTimer = setTimeout(() => { load(); refreshOverview(); }, 1200);
    };
    es.addEventListener("hello", () => setConnected(true));
    es.onerror = () => setConnected(false);
    const on = (type: string, fn: (d: any) => void) => es.addEventListener(type, (e) => fn(JSON.parse((e as MessageEvent).data)));
    on("session_started", (d) => {
      push("session", <><DevBadge dev={d.dev} small /> started <i>{d.task}</i></>, "var(--accent-2)");
      reloadSoon();
    });
    on("session_ended", () => reloadSoon());
    on("overlap", (d) => {
      push("overlap", <><DevBadge dev={d.a.dev} small /> and <DevBadge dev={d.b.dev} small /> are working on the same thing: <i>{d.task}</i></>, "var(--warn)");
      pulse([`Session:${d.a.session_id}`, `Session:${d.b.session_id}`], "#fbbf24");
      flow([{ source: `Session:${d.a.session_id}`, target: `Session:${d.b.session_id}`, type: "OVERLAPS", color: "#fbbf24" }]);
    });
    on("memory_saved", (d) => push("memory", <><DevBadge dev={d.dev || { name: "?" }} small /> saved memory <b>{d.title}</b></>, "var(--accent)"));
    on("reuse", (d) => {
      push("reuse", <><DevBadge dev={d.by} small /> reused <DevBadge dev={d.author} small />’s <b>{d.title}</b> · ~{tokens(d.tokens_saved)} tokens saved</>, "var(--accent)");
      const s = sessionOf(d.by?.name);
      if (s) pulse([s], "#34d399");
    });
    on("question_asked", (d) => {
      askers.current.set(d.question_id, d.asker?.name);
      push("ask", <><DevBadge dev={d.asker} small /> asked the org: <i>“{d.text}”</i></>, "#e879f9");
    });
    on("question_routed", (d) => {
      const asker = askers.current.get(d.question_id);
      const src = sessionOf(asker);
      const dst = d.to.kind === "session" ? `Session:${d.to.id}` : sessionOf(d.to.dev?.name);
      push("route", <>→ routed to <DevBadge dev={d.to.dev} small /> <span className="text-muted">because {d.reason?.split(";")[0]}</span></>, "#e879f9");
      if (dst) pulse([dst], "#e879f9", 8000);
      if (src && dst) flow([{ source: src, target: dst, type: "ASKS", color: "#e879f9" }], 8000);
    });
    on("answer", (d) => {
      push("answer", <><DevBadge dev={d.by} small /> answered: <i>“{d.text}”</i></>, "#e879f9");
      const s = sessionOf(d.by?.name);
      if (s) pulse([s], "#e879f9");
    });
    on("notice", (d) => {
      const targets = (d.delivered_to || []).map((x: any) => `Session:${x.session_id}`);
      push("notice", <><DevBadge dev={d.by} small /> changed <b>{d.component}</b>: <i>{d.text}</i> → warned {targets.length} live agent{targets.length === 1 ? "" : "s"}</>, "var(--danger)");
      pulse([`Component:${d.component}`, ...targets], "#f87171", 8000);
      flow(targets.map((t: string) => ({ source: `Component:${d.component}`, target: t, type: "NOTICE", color: "#f87171" })), 8000);
    });
    on("handoff", (d) => push("handoff", <><DevBadge dev={d.from} small /> handed off <i>{d.task}</i></>, "var(--accent-2)"));
    return () => {
      es.close();
      if (reloadTimer) clearTimeout(reloadTimer);
    };
  }, [org, load, push, pulse, flow, refreshOverview]);

  // expire effects
  useEffect(() => {
    const t = setInterval(() => {
      setEffects((e) => (e.some((x) => x.until < Date.now()) ? e.filter((x) => x.until > Date.now()) : e));
      setTemp((t2) => (t2.some((x) => x.until < Date.now()) ? t2.filter((x) => x.until > Date.now()) : t2));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  const data = useMemo(() => {
    const ids = new Set(graph.nodes.map((n) => n.id));
    const extra = temp.filter((t) => ids.has(t.source) && ids.has(t.target)).map((t) => ({ ...t, temp: true }));
    return { nodes: graph.nodes, links: [...graph.links, ...extra] };
  }, [graph, temp]);

  const glow = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of effects) for (const n of e.nodes) m.set(n, e.color);
    return m;
  }, [effects]);

  // layout tuning, applied by FGInner once the graph instance exists
  const configure = useCallback((fg: any) => {
    fg.d3Force("charge")?.strength((n: any) => (n.label === "Team" ? -500 : -190));
    fg.d3Force("link")?.distance((l: any) => (l.type === "OWNS" ? 60 : l.type === "TOUCHES" ? 28 : 90));
  }, []);


  const nodeCount = graph.nodes.filter((n) => n.label === "Session").length;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-4">
      <div className="card relative overflow-hidden" style={{ minHeight: 640, background: bg }}>
        <div className="absolute top-3 left-4 z-10 pointer-events-none">
          <h1 className="text-xl font-semibold">The {org} org, live</h1>
          <p className="text-sm text-muted max-w-md">
            Teams own components (arrows: <span className="font-mono text-xs">DEPENDS_ON</span>). Glowing dots are AI agents running
            right now, attached to what they touch. Every interaction below is a FalkorDB query.
          </p>
        </div>
        <div className="absolute top-3 right-4 z-10 flex items-center gap-2">
          <span className="chip">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: connected ? "var(--ok)" : "var(--danger)" }} />
            {connected ? "live stream" : "connecting…"}
          </span>
          <button className="btn" onClick={() => fgRef.current && fitTo(fgRef.current, graph.nodes, size.width, size.height, 70)}>Fit</button>
          <button className="btn btn-primary" onClick={() => setNoticeOpen(true)}>Announce a change</button>
        </div>
        <div className="absolute bottom-3 left-4 z-10 flex flex-wrap gap-2 text-xs pointer-events-none">
          {(overview?.teams || []).map((t) => (
            <span key={t.name} className="chip"><span style={{ width: 8, height: 8, borderRadius: 99, background: teamColor(t.name) }} />{t.name}</span>
          ))}
          <span className="chip">● {nodeCount} live agents</span>
        </div>
        <div ref={setEl} className="absolute inset-0">
          <ForceGraph
            fgRef={fgRef}
            width={size.width}
            height={size.height}
            graphData={data}
            backgroundColor="rgba(0,0,0,0)"
            cooldownTime={4000}
            linkColor={(l: any) => (l.temp ? l.color : l.type === "TOUCHES" ? teamColor(nodeMap.current.get(typeof l.source === "object" ? l.source.id : l.source)?.team) + "88" : linkColor)}
            linkWidth={(l: any) => (l.temp ? 2.5 : l.type === "DEPENDS_ON" ? 1.2 : l.type === "TOUCHES" ? 1.4 : 0.6)}
            linkLineDash={(l: any) => (l.type === "OVERLAPS" ? [3, 3] : l.type === "OWNS" ? [1, 3] : null)}
            linkDirectionalArrowLength={(l: any) => (l.type === "DEPENDS_ON" ? 3.5 : 0)}
            linkDirectionalArrowRelPos={0.92}
            linkDirectionalParticles={(l: any) => (l.temp ? 4 : 0)}
            linkDirectionalParticleWidth={3.5}
            linkDirectionalParticleSpeed={0.012}
            linkDirectionalParticleColor={(l: any) => l.color}
            nodeLabel={(n: any) => (n.label === "Session" ? `${n.dev} (${n.team}): ${n.name}` : `${n.label}: ${n.name}`)}
            nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, scale: number) => {
              const g = glow.get(n.id);
              const t = Date.now() / 1000;
              if (n.label === "Team") {
                const c = teamColor(n.name);
                ctx.beginPath();
                ctx.arc(n.x, n.y, 13, 0, 2 * Math.PI);
                ctx.fillStyle = c + "22";
                ctx.fill();
                ctx.lineWidth = 1.5;
                ctx.strokeStyle = c;
                ctx.stroke();
                ctx.font = `600 ${13 / Math.max(scale, 0.8)}px ui-sans-serif, system-ui`;
                ctx.fillStyle = c;
                ctx.textAlign = "center";
                ctx.fillText(n.name, n.x, n.y + 4 / Math.max(scale, 0.8));
                return;
              }
              if (n.label === "Component") {
                const c = teamColor(n.team);
                if (g) {
                  ctx.beginPath();
                  ctx.arc(n.x, n.y, 9 + 4 * Math.sin(t * 6), 0, 2 * Math.PI);
                  ctx.fillStyle = g + "44";
                  ctx.fill();
                }
                ctx.beginPath();
                ctx.arc(n.x, n.y, 5.5, 0, 2 * Math.PI);
                ctx.fillStyle = c;
                ctx.fill();
                if (scale > 0.7) {
                  ctx.font = `${10 / Math.max(scale, 1)}px ui-monospace, monospace`;
                  ctx.fillStyle = label;
                  ctx.globalAlpha = 0.8;
                  ctx.textAlign = "center";
                  ctx.fillText(n.name, n.x, n.y + 14 / Math.max(scale, 1));
                  ctx.globalAlpha = 1;
                }
                return;
              }
              // live agent session
              const c = teamColor(n.team);
              const r = 4.5;
              const halo = g || c;
              ctx.beginPath();
              ctx.arc(n.x, n.y, r + (g ? 7 : 3) + (g ? 3 : 1.2) * Math.sin(t * (g ? 7 : 2.5) + n.x), 0, 2 * Math.PI);
              ctx.fillStyle = halo + (g ? "55" : "26");
              ctx.fill();
              ctx.beginPath();
              ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
              ctx.fillStyle = "#ffffff";
              ctx.fill();
              ctx.lineWidth = 2;
              ctx.strokeStyle = c;
              ctx.stroke();
              if (scale > 0.6) {
                ctx.font = `600 ${10 / Math.max(scale, 1)}px ui-sans-serif, system-ui`;
                ctx.fillStyle = c;
                ctx.textAlign = "center";
                ctx.fillText(n.dev || "agent", n.x, n.y - 9 / Math.max(scale, 1));
              }
            }}
            autoPauseRedraw={false}
            configure={configure}
          />
        </div>
      </div>

      <aside className="space-y-4 min-w-0">
        <div className="card p-4">
          <h2 className="font-semibold mb-2 flex items-center justify-between">
            Activity <span className="text-xs text-muted font-normal">real-time event stream</span>
          </h2>
          <div className="space-y-2 max-h-[340px] overflow-auto pr-1">
            {feed.length === 0 && <div className="text-sm text-muted py-4">Waiting for agents to do something… (the fleet acts every ~15 s)</div>}
            {feed.map((f) => (
              <div key={f.id} className="feed-item text-[13px] leading-relaxed border-l-2 pl-2.5" style={{ borderColor: f.color }}>
                <div>{f.text}</div>
                <div className="text-[10px] text-muted">{ago(f.at)}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-4">
          <h2 className="font-semibold mb-2">Live agents <span className="text-muted font-normal text-sm">({live.length})</span></h2>
          <div className="space-y-2.5 max-h-[300px] overflow-auto pr-1">
            {live.map((s) => (
              <div key={s.id} className="text-[13px]">
                <div className="flex items-center gap-2 flex-wrap">
                  <DevBadge dev={s.dev} small />
                  <span className="text-[11px] text-muted">{s.agent} · {ago(s.started_at)}</span>
                </div>
                <div className="mt-0.5">{s.task}</div>
                <div className="text-[11px] text-muted font-mono">{s.components.join(", ")}</div>
                {s.overlaps.length > 0 && (
                  <div className="text-[11px]" style={{ color: "var(--warn)" }}>
                    overlaps with {s.overlaps.map((o) => o.dev.name).join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </aside>
      {noticeOpen && <NoticeModal onClose={() => setNoticeOpen(false)} />}
    </div>
  );
}

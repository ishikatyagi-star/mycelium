"use client";

import { useMemo, useRef } from "react";
import type { Path } from "@/lib/api";
import { LABEL_COLOR, teamColor } from "@/lib/teams";
import ForceGraph, { useCssVar, useSize } from "./ForceGraph";

/** Small graph that shows the exact path the graph walked to produce an answer. */
export default function PathGraph({ path, height = 240 }: { path: Path; height?: number }) {
  const [setEl, size] = useSize<HTMLDivElement>();
  const label = useCssVar("--graph-label", "#e4eee9");
  const link = useCssVar("--graph-link", "rgba(228,238,233,.15)");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  // Paths are small chains/trees: a fixed layered layout (BFS depth = column) is always readable,
  // unlike a force simulation that can collapse labels on top of each other.
  const data = useMemo(() => {
    const ids = new Set(path.nodes.map((n) => n.id));
    const links = path.links.filter((l) => ids.has(l.source) && ids.has(l.target)).map((l) => ({ ...l }));
    const adj = new Map<string, string[]>();
    for (const l of links) {
      adj.set(l.source, [...(adj.get(l.source) || []), l.target]);
      adj.set(l.target, [...(adj.get(l.target) || []), l.source]);
    }
    const depth = new Map<string, number>();
    const start = path.nodes.find((n) => n.label === "Question" || n.label === "Task")?.id || path.nodes[0]?.id;
    const queue = start ? [start] : [];
    if (start) depth.set(start, 0);
    while (queue.length) {
      const cur = queue.shift()!;
      for (const nb of adj.get(cur) || []) if (!depth.has(nb)) { depth.set(nb, depth.get(cur)! + 1); queue.push(nb); }
    }
    const cols = new Map<number, string[]>();
    for (const n of path.nodes) {
      const d = depth.get(n.id) ?? 0;
      cols.set(d, [...(cols.get(d) || []), n.id]);
    }
    const nodes = path.nodes.map((n) => {
      const d = depth.get(n.id) ?? 0;
      const col = cols.get(d)!;
      const i = col.indexOf(n.id);
      return { ...n, fx: d * 215, fy: (i - (col.length - 1) / 2) * 30 };
    });
    return { nodes, links };
  }, [path]);
  return (
    <div ref={setEl} style={{ height }} className="rounded-xl overflow-hidden border border-line bg-bg">
      <ForceGraph
        fgRef={fgRef}
        width={size.width}
        height={height}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={1}
        fitPad={28}
        linkColor={() => link}
        linkWidth={1.4}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={0.9}
        linkLabel={(l: { type: string }) => l.type}
        linkCanvasObjectMode={() => "after"}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        linkCanvasObject={(l: any, ctx: CanvasRenderingContext2D, scale: number) => {
          if (scale < 1.2 || typeof l.source !== "object") return;
          const x = (l.source.x + l.target.x) / 2, y = (l.source.y + l.target.y) / 2;
          ctx.font = `${9 / scale * 1.6}px ui-monospace, monospace`;
          ctx.fillStyle = label;
          ctx.globalAlpha = 0.55;
          ctx.textAlign = "center";
          ctx.fillText(l.type, x, y);
          ctx.globalAlpha = 1;
        }}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, scale: number) => {
          const color = n.team ? teamColor(n.team) : LABEL_COLOR[n.label] || "#94a3b8";
          const r = n.label === "Team" ? 7 : n.label === "Dev" ? 6 : 5;
          ctx.beginPath();
          ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
          const name = String(n.name);
          const text = n.label === "Session" ? "agent session" : ["Component", "Dev", "Team", "Project"].includes(n.label)
            ? name : `${n.label}: ${name.length > 24 ? name.slice(0, 23) + "…" : name}`;
          ctx.font = `${Math.max(9, 11 / scale)}px ui-sans-serif, system-ui`;
          ctx.fillStyle = label;
          ctx.textAlign = "center";
          ctx.fillText(text, n.x, n.y + r + 10 / scale);
        }}
      />
    </div>
  );
}

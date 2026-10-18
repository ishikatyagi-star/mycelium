"use client";

import { useCallback, useMemo, useRef } from "react";
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const configure = useCallback((fg: any) => {
    fg.d3Force("charge")?.strength(-420);
    fg.d3Force("link")?.distance(95);
  }, []);
  const data = useMemo(
    () => ({
      nodes: path.nodes.map((n) => ({ ...n })),
      links: path.links.filter((l) => path.nodes.some((n) => n.id === l.source) && path.nodes.some((n) => n.id === l.target)).map((l) => ({ ...l })),
    }),
    [path],
  );
  return (
    <div ref={setEl} style={{ height }} className="rounded-xl overflow-hidden border border-line bg-bg">
      <ForceGraph
        fgRef={fgRef}
        width={size.width}
        height={height}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={120}
        configure={configure}
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
          const text = `${n.label}: ${String(n.name).slice(0, 38)}`;
          ctx.font = `${11 / scale}px ui-sans-serif, system-ui`;
          ctx.fillStyle = label;
          ctx.textAlign = "center";
          ctx.fillText(text, n.x, n.y + r + 10 / scale);
        }}
      />
    </div>
  );
}

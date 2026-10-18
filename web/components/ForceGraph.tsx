"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

// react-force-graph-2d touches `window` at import time: load it on the client only.
// Pass `fgRef` (not `ref`) to reach the graph instance.
const ForceGraph = dynamic(() => import("./FGInner"), { ssr: false });
export default ForceGraph;

export function useCssVar(name: string, fallback: string) {
  const [v, setV] = useState(fallback);
  useEffect(() => {
    const read = () => setV(getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback);
    read();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", read);
    return () => mq.removeEventListener("change", read);
  }, [name, fallback]);
  return v;
}

export function useSize<T extends HTMLElement>() {
  const [el, setEl] = useState<T | null>(null);
  const [size, setSize] = useState({ width: 600, height: 400 });
  useEffect(() => {
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ width: e.contentRect.width, height: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, size] as const;
}

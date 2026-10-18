"use client";

import { useEffect, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { fitTo } from "./fit";

/* eslint-disable @typescript-eslint/no-explicit-any */
// Loaded only on the client (see ForceGraph.tsx). Because next/dynamic does not forward refs, the instance is
// handed back through `fgRef`, and layout tuning (`configure`) + auto-fit happen here, where the ref is real.
export default function FGInner({ fgRef, configure, autoFit = true, fitPad = 70, onEngineStop, ...props }: any) {
  const ref = useRef<any>(null);
  const userMoved = useRef(false);
  const n = props.graphData?.nodes?.length ?? 0;
  useEffect(() => {
    if (fgRef) fgRef.current = ref.current;
  });
  useEffect(() => {
    if (ref.current && configure && n) {
      configure(ref.current);
      ref.current.d3ReheatSimulation();
    }
  }, [configure, n]);
  // a live graph rarely "stops", so also fit shortly after the data changes (unless the user took over)
  const sizeRef = useRef({ w: props.width, h: props.height, nodes: props.graphData?.nodes || [] });
  sizeRef.current = { w: props.width, h: props.height, nodes: props.graphData?.nodes || [] };
  useEffect(() => {
    if (!autoFit || !n) return;
    const fit = () => {
      if (!userMoved.current && ref.current) fitTo(ref.current, sizeRef.current.nodes, sizeRef.current.w, sizeRef.current.h, fitPad);
    };
    const ts = [1200, 3500, 7000].map((ms) => setTimeout(fit, ms));
    return () => ts.forEach(clearTimeout);
  }, [autoFit, n, fitPad]);
  return (
    <div onWheel={() => (userMoved.current = true)} onPointerDown={() => (userMoved.current = true)}>
    <ForceGraph2D
      ref={ref}
      {...props}
      onEngineStop={() => {
        // keep the whole org in view whenever the layout settles, until the user pans/zooms themselves
        if (autoFit && !userMoved.current && ref.current) fitTo(ref.current, props.graphData?.nodes || [], props.width, props.height, fitPad);
        onEngineStop?.();
      }}
    />
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { fitTo } from "./fit";

/* eslint-disable @typescript-eslint/no-explicit-any */
// Loaded only on the client (see ForceGraph.tsx). Because next/dynamic does not forward refs, the instance is
// handed back through `fgRef`, and layout tuning (`configure`) + auto-fit happen here, where the ref is real.
export default function FGInner({ fgRef, configure, autoFit = true, onEngineStop, ...props }: any) {
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
  return (
    <div onWheel={() => (userMoved.current = true)} onPointerDown={() => (userMoved.current = true)}>
    <ForceGraph2D
      ref={ref}
      {...props}
      onEngineStop={() => {
        // keep the whole org in view whenever the layout settles, until the user pans/zooms themselves
        if (autoFit && !userMoved.current && ref.current) fitTo(ref.current, props.graphData?.nodes || [], props.width, props.height, 70);
        onEngineStop?.();
      }}
    />
    </div>
  );
}

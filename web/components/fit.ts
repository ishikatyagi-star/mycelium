/* eslint-disable @typescript-eslint/no-explicit-any */
/** Center and zoom on the nodes' bounding box (computed from the simulation's own node objects). */
export function fitTo(fg: any, nodes: any[], width = 600, height = 400, pad = 60, ms = 600) {
  const pts = nodes.filter((n) => Number.isFinite(n.x) && Number.isFinite(n.y));
  if (pts.length < 2) return;
  // still collapsed at the origin (simulation not spread yet): don't zoom into a dot
  if (Math.max(...pts.map((n) => Math.abs(n.x))) < 5) return;
  const xs = pts.map((n) => n.x), ys = pts.map((n) => n.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const k = 0.85 * Math.min((width - pad * 2) / Math.max(x1 - x0, 1), (height - pad * 2) / Math.max(y1 - y0, 1), 4);
  fg.centerAt((x0 + x1) / 2, (y0 + y1) / 2, ms);
  fg.zoom(Math.max(k, 0.2), ms);
}


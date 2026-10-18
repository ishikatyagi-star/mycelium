"use client";

import { useState } from "react";
import { post, type Dev, type Path, type Trace } from "@/lib/api";
import { useOrg } from "./OrgProvider";
import PathGraph from "./PathGraph";
import { CypherTrace, DevBadge, ErrorNote, Spinner } from "./ui";

type Impact = {
  notice_id: string;
  component: string;
  impact: { session_id: string; dev: Dev; component: string; depth: number; path: Path }[];
  team_deliveries: { team: string; component: string }[];
  trace: Trace;
};

const PRESETS: Record<string, [string, string]> = {
  acme: ["token-service", "Signing keys rotate today 14:00 UTC; clients must refetch JWKS on an unknown kid"],
  mycelium: ["api", "Recall responses now include a `skipped` list for superseded fixes"],
};

export default function NoticeModal({ onClose }: { onClose: () => void }) {
  const { org, overview, persona } = useOrg();
  const comps = (overview?.teams || []).flatMap((t) => t.components).sort();
  const [component, setComponent] = useState(PRESETS[org]?.[0] || comps[0] || "");
  const [text, setText] = useState(PRESETS[org]?.[1] || "");
  const [res, setRes] = useState<Impact | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const send = async () => {
    setBusy(true);
    setErr(null);
    try {
      setRes(await post<Impact>(`/api/orgs/${org}/notices`, { component, text, as_dev: persona }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-start justify-center p-4 overflow-auto" onClick={onClose}>
      <div className="card w-full max-w-2xl p-5 space-y-4 mt-10" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-lg font-semibold">Announce a change</h2>
            <p className="text-sm text-muted">
              As <b>{persona}</b>. Mycelium walks <span className="font-mono">DEPENDS_ON</span> up to 3 hops and warns only the live agents
              whose work depends on this component.
            </p>
          </div>
          <button className="text-muted text-xl leading-none" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-[200px_1fr] gap-3">
          <select className="input" value={component} onChange={(e) => setComponent(e.target.value)}>
            {comps.map((c) => <option key={c}>{c}</option>)}
          </select>
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="What changed?" />
        </div>
        <button className="btn btn-primary" disabled={busy || text.length < 5} onClick={send}>Send to affected agents</button>
        {busy && <Spinner label="Walking DEPENDS_ON…" />}
        <ErrorNote error={err} />
        {res && (
          <div className="space-y-3">
            <div className="text-sm">
              <b>{res.impact.length}</b> live agent{res.impact.length === 1 ? "" : "s"} warned
              {res.team_deliveries.length > 0 && <> · team inboxes: {[...new Set(res.team_deliveries.map((t) => t.team))].join(", ")}</>}
            </div>
            {res.impact.map((d) => (
              <div key={d.session_id} className="flex items-center gap-2 text-sm flex-wrap">
                <DevBadge dev={d.dev} small />
                <span className="text-muted">live on</span> <span className="font-mono">{d.component}</span>
                <span className="chip">{d.depth === 0 ? "same component" : `${d.depth} hop${d.depth > 1 ? "s" : ""} downstream`}</span>
                <span className="text-xs text-muted font-mono">{d.path.nodes.filter((n) => n.label === "Component").map((n) => n.name).join(" → ")}</span>
              </div>
            ))}
            {res.impact[0] && <PathGraph path={{ nodes: res.impact.flatMap((d) => d.path.nodes).filter((n, i, a) => a.findIndex((x) => x.id === n.id) === i), links: res.impact.flatMap((d) => d.path.links) }} height={260} />}
            <CypherTrace trace={res.trace} />
          </div>
        )}
      </div>
    </div>
  );
}

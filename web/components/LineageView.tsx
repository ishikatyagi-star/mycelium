"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useOrg } from "@/components/OrgProvider";
import PathGraph from "@/components/PathGraph";
import { CypherTrace, DevBadge, Empty, Spinner } from "@/components/ui";
import { ago, get, type Dev, type Path, type Trace } from "@/lib/api";

type Lineage = {
  chain: { id: string; title: string; status: string; project: string | null; author: Dev; created_at: number }[];
  edges: { from_id: string; to_id: string; rel: string }[];
  path: Path;
  trace: Trace;
};

export default function LineageView() {
  const { id } = useParams<{ id: string }>();
  const { org } = useOrg();
  const [l, setL] = useState<Lineage | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    setL(null);
    get<Lineage>(`/api/orgs/${org}/lineage/${id}`).then(setL).catch(() => setErr(true));
  }, [org, id]);

  const relOf = (a: string, b: string) => l?.edges.find((e) => (e.from_id === b && e.to_id === a))?.rel;

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">How this knowledge evolved</h1>
        <p className="text-muted text-sm mt-1">
          <span className="font-mono">BUILDS_ON</span> and <span className="font-mono">SUPERSEDES</span> chains across projects, people and
          teams. Knowledge compounds instead of being rewritten from scratch.
        </p>
      </div>
      {err && <Empty>Unknown solution in this org.</Empty>}
      {!l && !err && <Spinner />}
      {l && (
        <>
          {l.chain.length <= 1 && <Empty>This solution stands alone: nothing builds on it yet.</Empty>}
          <ol className="relative border-l-2 border-line ml-3 space-y-5">
            {l.chain.map((c, i) => {
              const rel = i > 0 ? relOf(l.chain[i - 1].id, c.id) : null;
              return (
                <li key={c.id} className="ml-5">
                  <span className="absolute -left-[9px] w-4 h-4 rounded-full border-2 border-bg"
                        style={{ background: c.status === "active" ? "var(--accent)" : "var(--danger)" }} />
                  {rel && <div className="text-[11px] font-mono text-muted mb-1">↑ {rel === "SUPERSEDES" ? "supersedes (replaced) the one above" : "builds on the one above"}</div>}
                  <div className={`card p-3 ${c.id === id ? "ring-1 ring-accent" : ""}`}>
                    <div className="font-medium">{c.title}</div>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap text-xs">
                      <DevBadge dev={c.author} small />
                      {c.project && <span className="chip">📁 {c.project}</span>}
                      <span className="chip">{ago(c.created_at)}</span>
                      {c.status !== "active" && <span className="chip" style={{ color: "var(--danger)" }}>{c.status}</span>}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          {l.path.links.length > 0 && <PathGraph path={l.path} height={260} />}
          <CypherTrace trace={l.trace} />
        </>
      )}
    </div>
  );
}

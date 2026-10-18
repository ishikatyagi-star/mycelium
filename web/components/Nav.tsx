"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { tokens } from "@/lib/api";
import { useOrg } from "./OrgProvider";
import { Stat } from "./ui";

const LINKS = [
  ["/", "Live org"],
  ["/ask", "Ask & recall"],
  ["/compare", "Vector vs Mycelium"],
  ["/threads", "Agent threads"],
  ["/brain", "Company brain"],
] as const;

export default function Nav() {
  const path = usePathname();
  const { org, setOrg, orgs, overview, persona, setPersona, devs } = useOrg();
  const c = overview?.counts;
  return (
    <header className="border-b border-line bg-surface/80 backdrop-blur sticky top-0 z-30">
      <div className="max-w-[1500px] mx-auto px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Link href="/" className="flex items-center gap-2 font-semibold text-lg tracking-tight">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
            <circle cx="12" cy="12" r="3" fill="var(--accent)" />
            <circle cx="4" cy="6" r="2" fill="var(--accent-2)" />
            <circle cx="20" cy="7" r="2" fill="var(--accent-2)" />
            <circle cx="6" cy="20" r="2" fill="var(--accent-2)" />
            <circle cx="19" cy="19" r="2" fill="var(--accent-2)" />
            <path d="M12 12L4 6M12 12l8-5M12 12l-6 8M12 12l7 7" stroke="var(--accent)" strokeWidth="1.2" />
          </svg>
          Mycelium
        </Link>
        <nav className="flex flex-wrap gap-1 text-sm">
          {LINKS.map(([href, label]) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded-lg ${active ? "bg-surface-2 text-fg font-medium" : "text-muted hover:text-fg"}`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-1 ml-auto divide-x divide-line">
          <Stat label="live agents" value={c?.live_sessions ?? "–"} />
          <Stat label="memories" value={c?.solutions ?? "–"} />
          <Stat label="sessions" value={c?.sessions ?? "–"} />
          <Stat label="tokens saved" value={c ? tokens(c.tokens_saved) : "–"} />
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label className="text-muted text-xs">org</label>
          <select className="input !w-auto !py-1.5" value={org} onChange={(e) => setOrg(e.target.value)}>
            {orgs.map((o) => (
              <option key={o} value={o}>{o === "mycelium" ? "mycelium (our build)" : o}</option>
            ))}
          </select>
          <label className="text-muted text-xs">as</label>
          <select className="input !w-auto !py-1.5" value={persona} onChange={(e) => setPersona(e.target.value)}>
            {devs.map((d) => (
              <option key={d.name} value={d.name}>{d.name} · {d.team}</option>
            ))}
          </select>
        </div>
      </div>
    </header>
  );
}

"use client";

import { Compass } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useOrg } from "./OrgProvider";
import { useTour } from "./Tour";

const LINKS = [
  ["/", "Overview"],
  ["/playground", "Playground"],
  ["/live", "Live org"],
  ["/compare", "Vector vs graph"],
  ["/ask", "Ask"],
  ["/threads", "Threads"],
  ["/brain", "Brain"],
] as const;

export const ORG_NAMES: Record<string, string> = { graphhq: "Graph HQ (demo)", mycelium: "Mycelium (our build)" };

export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 12L4 6M12 12l8-5M12 12l-6 8M12 12l7 7" stroke="var(--primary)" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="12" r="3.2" fill="var(--primary)" />
      <circle cx="4" cy="6" r="2" fill="#0d9488" />
      <circle cx="20" cy="7" r="2" fill="#0d9488" />
      <circle cx="6" cy="20" r="2" fill="#0d9488" />
      <circle cx="19" cy="19" r="2" fill="#0d9488" />
    </svg>
  );
}

export default function Nav() {
  const path = usePathname();
  const { org, setOrg, orgs, persona, setPersona, devs } = useOrg();
  const tour = useTour();
  return (
    <header className="border-b border-line bg-surface/90 backdrop-blur sticky top-0 z-30">
      <div className="max-w-[1400px] mx-auto px-5 sm:px-8 h-16 flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg tracking-tight shrink-0">
          <Logo /> Mycelium
        </Link>
        <nav className="hidden md:flex items-center gap-1 text-sm">
          {LINKS.map(([href, label]) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <Link key={href} href={href}
                    className={`px-3 py-2 rounded-lg transition-colors ${active ? "text-fg font-semibold bg-surface-2" : "text-muted hover:text-fg"}`}>
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <label className="sr-only" htmlFor="org">Organization</label>
          <select id="org" className="input !w-auto !min-h-[36px] !py-1 !text-sm" value={org} onChange={(e) => setOrg(e.target.value)}>
            {orgs.map((o) => <option key={o} value={o}>{ORG_NAMES[o] || o}</option>)}
          </select>
          <label className="sr-only" htmlFor="persona">Viewing as</label>
          <select id="persona" className="input !w-auto !min-h-[36px] !py-1 !text-sm hidden lg:block" value={persona}
                  onChange={(e) => setPersona(e.target.value)} title="Viewing as">
            {devs.map((d) => <option key={d.name} value={d.name}>as {d.name} · {d.team}</option>)}
          </select>
          <button className="btn !min-h-[36px] !py-1" onClick={() => tour.start()}>
            <Compass size={16} aria-hidden /> Tour
          </button>
        </div>
      </div>
      <nav className="md:hidden flex gap-1 overflow-x-auto px-5 pb-2 text-sm">
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href} className={`px-3 py-1.5 rounded-lg whitespace-nowrap ${path === href ? "bg-surface-2 font-semibold" : "text-muted"}`}>{label}</Link>
        ))}
      </nav>
    </header>
  );
}

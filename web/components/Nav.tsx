"use client";

import { Compass } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
        <div className="ml-auto">
          <button onClick={() => tour.start()}
                  className={`btn btn-primary !min-h-[44px] !px-5 !text-[15px] shadow-md relative ${tour.seen ? "" : "tour-cta"}`}>
            <Compass size={18} aria-hidden /> Start the tour
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

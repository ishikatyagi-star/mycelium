import type { Metadata } from "next";
import { Geist_Mono, Plus_Jakarta_Sans } from "next/font/google";
import { Suspense } from "react";
import Nav from "@/components/Nav";
import { OrgProvider } from "@/components/OrgProvider";
import { TourProvider } from "@/components/Tour";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({ variable: "--font-jakarta", subsets: ["latin"], weight: ["400", "500", "600", "700", "800"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Mycelium",
  description: "One shared memory graph for every AI agent in a company, on FalkorDB.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${jakarta.variable} ${geistMono.variable} h-full`}>
      <body className="min-h-full flex flex-col">
        <OrgProvider>
          <TourProvider>
            <Suspense fallback={<div className="h-16 border-b border-line bg-surface" />}>
              <Nav />
            </Suspense>
            <main className="flex-1 w-full max-w-[1400px] mx-auto px-5 sm:px-8 py-8">{children}</main>
            <footer className="text-sm text-subtle text-center py-6 border-t border-line">
              Mycelium · built on FalkorDB for Graph Hacks 2026 ·{" "}
              <a className="underline hover:text-fg" href="https://github.com/ishikatyagi-star/mycelium">GitHub</a>
            </footer>
          </TourProvider>
        </OrgProvider>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Suspense } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import Nav from "@/components/Nav";
import { OrgProvider } from "@/components/OrgProvider";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Mycelium",
  description: "One shared context graph for every AI agent in a company, on FalkorDB.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <OrgProvider>
          <Suspense fallback={<div className="h-[60px] border-b border-line" />}>
            <Nav />
          </Suspense>
          <main className="flex-1 w-full max-w-[1500px] mx-auto px-4 py-5">{children}</main>
          <footer className="text-xs text-muted text-center py-4 border-t border-line">
            Mycelium · built on FalkorDB for Graph Hacks 2026 ·{" "}
            <a className="underline" href="https://github.com/ishikatyagi-star/mycelium">GitHub</a>
          </footer>
        </OrgProvider>
      </body>
    </html>
  );
}

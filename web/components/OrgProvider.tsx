"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { get, type Overview } from "@/lib/api";

type Ctx = {
  org: string;
  setOrg: (o: string) => void;
  orgs: string[];
  overview: Overview | null;
  refreshOverview: () => void;
  persona: string;
  setPersona: (p: string) => void;
  devs: { name: string; team: string }[];
};

const OrgContext = createContext<Ctx | null>(null);

function read(key: string, fallback: string) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}
function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {}
}

export function OrgProvider({ children }: { children: React.ReactNode }) {
  const [org, setOrgState] = useState("graphhq");
  const [orgs, setOrgs] = useState<string[]>(["graphhq"]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [persona, setPersonaState] = useState("Ishika");

  useEffect(() => {
    setPersonaState(read("myc.persona", "Ishika"));
    get<{ orgs: string[] }>("/api/health")
      .then((h) => {
        const list = h.orgs.filter((o) => !o.startsWith("sandbox_") && !o.startsWith("test") && !o.startsWith("loadtest"));
        setOrgs(list);

      })
      .catch(() => {});
  }, []);

  const refreshOverview = useCallback(() => {
    get<Overview>(`/api/orgs/${org}/overview`).then(setOverview).catch(() => {});
  }, [org]);

  useEffect(() => {
    setOverview(null);
    refreshOverview();
    const t = setInterval(refreshOverview, 15000);
    return () => clearInterval(t);
  }, [refreshOverview]);

  const devs = (overview?.teams || []).flatMap((t) => t.devs.map((d) => ({ name: d, team: t.name })));

  useEffect(() => {
    if (devs.length && !devs.some((d) => d.name === persona)) setPersonaState(devs[0].name);
  }, [devs, persona]);

  const setOrg = (o: string) => {
    write("myc.org", o);
    setOrgState(o);
  };
  const setPersona = (p: string) => {
    write("myc.persona", p);
    setPersonaState(p);
  };

  return (
    <OrgContext.Provider value={{ org, setOrg, orgs, overview, refreshOverview, persona, setPersona, devs }}>
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg() {
  const c = useContext(OrgContext);
  if (!c) throw new Error("useOrg outside OrgProvider");
  return c;
}

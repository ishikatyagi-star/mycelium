import { Suspense } from "react";
import LineageView from "@/components/LineageView";
import { Spinner } from "@/components/ui";

export default function LineagePage() {
  return (
    <Suspense fallback={<Spinner label="Loading lineage…" />}>
      <LineageView />
    </Suspense>
  );
}

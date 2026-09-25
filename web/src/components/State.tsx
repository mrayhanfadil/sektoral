import { useEffect, useState } from "react";

/** Load once; `error` is a reader-facing message. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true });
  useEffect(() => {
    let live = true;
    setState({ loading: true });
    load().then(
      (data) => live && setState({ data, loading: false }),
      (error: Error) => live && setState({ error: error.message || "Data belum tersedia.", loading: false }),
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function Notice({ tone = "muted", children }: { tone?: "muted" | "error"; children: React.ReactNode }) {
  const cls = tone === "error" ? "border-err-bg bg-err-bg text-err-ink" : "border-dashed border-rule bg-canvas text-ink-soft";
  return <div role={tone === "error" ? "alert" : undefined} className={`rounded-xl border p-6 ${cls}`}>{children}</div>;
}

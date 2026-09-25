import { useCallback, useEffect, useState } from "react";
import { Info, TriangleAlert } from "lucide-react";
import { ApiError } from "../lib/api";

/** Load once; `error` is a reader-facing message, `status` the HTTP status when the API answered. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<{ data?: T; error?: string; status?: number; loading: boolean }>({ loading: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setState({ loading: true });
    load().then(
      (data) => live && setState({ data, loading: false }),
      (error: Error) => live && setState({
        error: error.message || "Data belum tersedia.",
        status: error instanceof ApiError ? error.status : undefined,
        loading: false,
      }),
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, reload };
}

const NOTICE = {
  muted: "border-rule bg-surface text-ink-soft",
  warn: "border-warn-rule/50 bg-warn-bg text-warn-ink",
  error: "border-err-ink/25 bg-err-bg text-err-ink",
} as const;

/** A ruled message region: an empty result, a caveat, or a failure. */
export function Notice({ tone = "muted", children }: { tone?: keyof typeof NOTICE; children: React.ReactNode }) {
  const Mark = tone === "muted" ? Info : TriangleAlert;
  return (
    <div role={tone === "error" ? "alert" : undefined}
      className={`flex items-start gap-3 rounded-lg border px-5 py-4 text-[15px] leading-relaxed max-sm:px-4 ${NOTICE[tone]}`}>
      <Mark aria-hidden className="mt-[5px] size-4 flex-none" strokeWidth={2.2} />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

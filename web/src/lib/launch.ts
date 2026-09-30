// Starting research from the web. Locally anyone can start a live run. On the
// public site (live_runs "token") a live run needs the owner's run token;
// everyone else still gets the run, replayed step by step from its audit
// trace, for any issuer that already has a report.
import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import { pick } from "./i18n";

const RUN_TOKEN = "sectoral.run-token";

export function readRunToken(): string {
  try { return sessionStorage.getItem(RUN_TOKEN) ?? ""; } catch { return ""; }
}
export function keepRunToken(token: string) {
  try {
    if (token) sessionStorage.setItem(RUN_TOKEN, token);
    else sessionStorage.removeItem(RUN_TOKEN);
  } catch { /* private window: ask again next time */ }
}

let configLoad: ReturnType<typeof api.config> | null = null;
export function liveRuns() {
  configLoad ??= api.config().catch(() => ({ live_runs: "open" as const, review: false }));
  return configLoad.then((c) => c.live_runs);
}

/** Where to go for ``ticker``: a live job, or the stored run's replay. */
export async function launch(ticker: string): Promise<{ path: string; replay: boolean }> {
  const mode = await liveRuns();
  const token = readRunToken();
  if (mode === "open" || (mode === "token" && token)) {
    try {
      return { path: `/jobs/${await api.submit(ticker, token || undefined)}`, replay: false };
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 403)) throw error;
      if (token) keepRunToken("");
    }
  }
  const reports = await api.reports().catch(() => []);
  if (reports.some((r) => r.ticker === ticker && (r.files.trace_json || r.files.trace))) {
    return { path: `/laporan/${ticker}/putar`, replay: true };
  }
  throw new Error(pick({
    id: `${ticker} belum diriset di situs ini. Pilih salah satu emiten yang sudah diriset untuk memutar ulang run-nya.`,
    en: `${ticker} has not been researched on this site yet. Pick an issuer that has, to replay its run.`,
  }));
}

/** The site's live-run mode ("open" until the server answers). */
export function useLiveRuns() {
  const [mode, setMode] = useState<"open" | "token" | "off">("open");
  useEffect(() => {
    let live = true;
    liveRuns().then((m) => live && setMode(m));
    return () => { live = false; };
  }, []);
  return mode;
}

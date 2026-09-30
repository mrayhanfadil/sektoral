import { useEffect, useState } from "react";
import { api, type Intel } from "./api";
import type { Lang } from "./i18n";

/**
 * The analyst result behind a stored run, for an English reader: run events
 * carry the plan in Indonesian only, and this result holds its English twins
 * (lib/agents.ts `planIn`). Nothing is loaded for Indonesian readers; a
 * report without a public trace gives null, and the plan stays Indonesian.
 */
export function useRunIntel(ticker: string | undefined, lang: Lang): Intel | null {
  const [loaded, setLoaded] = useState<{ ticker: string; intel: Intel | null } | null>(null);
  useEffect(() => {
    if (lang !== "en" || !ticker) return;
    let live = true;
    api.reportTrace(ticker).then(
      (trace) => live && setLoaded({ ticker, intel: trace.analyst }),
      () => live && setLoaded({ ticker, intel: null }),
    );
    return () => { live = false; };
  }, [ticker, lang]);
  return lang === "en" && loaded && loaded.ticker === ticker ? loaded.intel : null;
}

import { useEffect, useState } from "react";
import { api, ApiError, type Job } from "./api";

/** Poll a research job until it completes or fails. */
export function useJob(id: string, interval = 800) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const next = await api.job(id);
        if (!live) return;
        setJob(next);
        setError(null);
        if (next.state === "pending" || next.state === "running") timer = window.setTimeout(poll, interval);
      } catch (e) {
        if (!live) return;
        setError((e as Error).message);
        // A job the server does not know will not appear later.
        if (!(e instanceof ApiError && e.status === 404)) timer = window.setTimeout(poll, interval * 4);
      }
    };
    poll();
    return () => { live = false; window.clearTimeout(timer); };
  }, [id, interval]);
  return { job, error };
}

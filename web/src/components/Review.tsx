import { useMemo, useState } from "react";
import { CircleCheck, ClipboardCheck, KeyRound, TriangleAlert } from "lucide-react";
import { api, ApiError, type ReviewField, type ReviewView } from "../lib/api";
import { Chip } from "./Intel";
import { useLoad } from "./State";

const TOKEN_KEY = "sectoral.review-token";
const two = new Intl.NumberFormat("id-ID", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const show = (value: number, unit: string) => `${two.format(value).replace("-", "−")}${unit === "%" ? "%" : "x"}`;

function readToken(): string {
  try { return sessionStorage.getItem(TOKEN_KEY) ?? ""; } catch { return ""; }
}
function keepToken(token: string) {
  try { sessionStorage.setItem(TOKEN_KEY, token); } catch { /* private window: ask again next time */ }
}

type Draft = Record<string, { value: string; reason: string }>;

/** The analyst review of a report's Forecast Plan: who approved it, what they changed, or the form to do so. */
export function ReviewPanel({ ticker, onApproved }: { ticker: string; onApproved: () => void }) {
  const state = useLoad(() => api.review(ticker), [ticker]);
  const view = state.data;
  if (state.loading && !view) {
    return <div aria-hidden className="h-28 w-full animate-pulse rounded-lg bg-surface ring-1 ring-rule" />;
  }
  if (!view || view.state === "no_plan") return null;
  return (
    <section id="review" aria-labelledby="review-title" className="panel scroll-mt-20">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 px-6 py-5 max-sm:px-4">
        <div className="flex min-w-0 items-start gap-3">
          <ClipboardCheck aria-hidden className="mt-1 size-4.5 flex-none text-brand-ink" strokeWidth={2.2} />
          <div className="min-w-0">
            <h2 id="review-title" className="text-[20px]">Review asumsi analis</h2>
            <p className="text-[14px] text-ink-soft">
              Laporan terbit hanya sesudah analis menyetujui Forecast Plan yang dipakai; setiap perubahan dicatat dengan alasan.
            </p>
          </div>
        </div>
        {view.state === "approved" ? (
          <Chip tone="ok"><CircleCheck aria-hidden className="size-3.5" strokeWidth={2.4} />
            {view.decision === "approved_with_edits" ? `Disetujui, ${view.edits.length} perubahan` : "Disetujui"}
          </Chip>
        ) : (
          <Chip tone="warn"><TriangleAlert aria-hidden className="size-3.5" strokeWidth={2.4} />Menunggu review</Chip>
        )}
      </header>
      {view.state === "approved" ? <Approved view={view} /> : (
        <ReviewForm ticker={ticker} view={view} onDone={() => { state.reload(); onApproved(); }} />
      )}
    </section>
  );
}

function Approved({ view }: { view: ReviewView }) {
  const when = view.reviewed_at ? new Date(view.reviewed_at).toLocaleString("id-ID", {
    dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Jakarta" }) : "—";
  return (
    <div className="grid gap-4 border-t border-rule px-6 py-5 max-sm:px-4">
      <p className="text-[14.5px] text-ink">
        Disetujui oleh <strong className="text-ink-strong">{view.reviewer}</strong>, {when} WIB.
        {view.note && <> Catatan: {view.note}</>}
      </p>
      {view.edits.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-[14px]">
            <thead>
              <tr className="border-b border-rule text-left text-[12.5px] text-ink-soft">
                <th scope="col" className="py-2 pr-4 font-medium">Driver</th>
                <th scope="col" className="py-2 pr-4 font-medium">Tahun</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">Agent</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">Analis</th>
                <th scope="col" className="py-2 font-medium">Alasan</th>
              </tr>
            </thead>
            <tbody>
              {view.edits.map((e) => (
                <tr key={e.path} className="border-b border-rule-soft align-top">
                  <td className="py-2 pr-4 text-ink-strong">{e.label}</td>
                  <td className="data py-2 pr-4 text-ink-soft">{e.year ?? "berjalan"}</td>
                  <td className="data py-2 pr-4 text-right text-ink-soft line-through decoration-ink-faint">{show(e.from, e.unit)}</td>
                  <td className="data py-2 pr-4 text-right font-semibold text-ink-strong">{show(e.to, e.unit)}</td>
                  <td className="py-2 text-ink">{e.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ReviewForm({ ticker, view, onDone }: { ticker: string; view: ReviewView; onDone: () => void }) {
  const [draft, setDraft] = useState<Draft>({});
  const [reviewer, setReviewer] = useState("");
  const [note, setNote] = useState("");
  const [token, setToken] = useState(readToken);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const years = useMemo(() => {
    const out = new Map<string, ReviewField[]>();
    for (const f of view.fields) {
      const key = f.year == null ? "—" : String(f.year);
      out.set(key, [...(out.get(key) ?? []), f]);
    }
    return [...out.entries()];
  }, [view.fields]);

  const changed = view.fields.filter((f) => {
    const d = draft[f.path];
    return d && d.value.trim() !== "" && Number(d.value.replace(",", ".")) !== f.value;
  });
  const missingReason = changed.filter((f) => (draft[f.path]?.reason ?? "").trim().length < 10);
  const canSubmit = view.enabled && reviewer.trim().length >= 2 && token && !missingReason.length && !busy;

  const set = (path: string, key: "value" | "reason", value: string) =>
    setDraft((d) => ({ ...d, [path]: { value: d[path]?.value ?? "", reason: d[path]?.reason ?? "", [key]: value } }));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    keepToken(token);
    try {
      await api.approve(ticker, token, {
        reviewer: reviewer.trim(), note: note.trim(),
        edits: changed.map((f) => ({ path: f.path, value: Number(draft[f.path].value.replace(",", ".")),
          reason: draft[f.path].reason.trim() })),
      });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Persetujuan gagal disimpan.");
    } finally {
      setBusy(false);
    }
  }

  const label = "mb-1 block text-[12.5px] font-medium text-ink-soft";
  const input = "h-10 w-full rounded-md border border-rule bg-raised px-3 text-[14.5px] text-ink-strong placeholder:text-ink-faint focus:border-brand-ink";
  return (
    <form onSubmit={submit} className="grid gap-5 border-t border-rule px-6 py-5 max-sm:px-4 [&>*]:min-w-0">
      {view.stale && (
        <p className="rounded-md border border-warn-rule/50 bg-warn-bg/50 px-4 py-2.5 text-[14px] text-warn-ink">
          Persetujuan sebelumnya berlaku untuk rencana lama; run baru mengganti Forecast Plan sehingga perlu direview lagi.
        </p>
      )}
      <details className="group rounded-md border border-rule">
        <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-3 text-[14.5px] font-medium text-ink-strong">
          <span>Driver Forecast Plan <span className="data text-ink-soft">{view.fields.length}</span></span>
          <span className="text-[13px] font-normal text-ink-soft">
            {changed.length ? `${changed.length} diubah` : "Ubah nilai bila perlu; kosong berarti setuju"}
          </span>
        </summary>
        <div className="overflow-x-auto border-t border-rule">
          <table className="w-full min-w-[720px] border-collapse text-[14px]">
            <thead>
              <tr className="border-b border-rule text-left text-[12.5px] text-ink-soft">
                <th scope="col" className="px-4 py-2 font-medium">Driver</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Agent</th>
                <th scope="col" className="w-32 px-4 py-2 font-medium">Nilai analis</th>
                <th scope="col" className="px-4 py-2 font-medium">Alasan perubahan</th>
              </tr>
            </thead>
            {years.map(([year, rows]) => (
              <tbody key={year}>
                <tr className="bg-raised"><th scope="rowgroup" colSpan={4} className="data px-4 py-1.5 text-left text-ink-soft">{year === "—" ? "Tahun berjalan (1H aktual + H2)" : `FY${year.slice(-2)}F`}</th></tr>
                {rows.map((f) => {
                  const d = draft[f.path];
                  const edited = changed.includes(f);
                  const when = year === "—" ? "tahun berjalan" : year;
                  return (
                    <tr key={f.path} className="border-b border-rule-soft align-top">
                      <td className="px-4 py-2 text-ink-strong" title={f.rationale || undefined}>{f.label}</td>
                      <td className="data px-4 py-2 text-right text-ink">{show(f.value, f.unit)}</td>
                      <td className="px-4 py-1.5">
                        <input aria-label={`${f.label} ${when}, nilai analis`} inputMode="decimal"
                          value={d?.value ?? ""} placeholder={two.format(f.value)}
                          onChange={(e) => set(f.path, "value", e.target.value)}
                          className={`${input} h-9 font-mono tabular-nums ${edited ? "border-brand-ink" : ""}`} />
                      </td>
                      <td className="px-4 py-1.5">
                        {edited ? (
                          <input aria-label={`Alasan perubahan ${f.label} ${when}`} value={d?.reason ?? ""}
                            onChange={(e) => set(f.path, "reason", e.target.value)} placeholder="Wajib, minimal 10 karakter"
                            className={`${input} h-9 ${(d?.reason ?? "").trim().length < 10 ? "border-warn-rule" : ""}`} />
                        ) : <span className="text-[13px] text-ink-faint">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            ))}
          </table>
        </div>
      </details>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="review-name" className={label}>Nama analis</label>
          <input id="review-name" value={reviewer} onChange={(e) => setReviewer(e.target.value)} autoComplete="name" className={input} />
        </div>
        <div>
          <label htmlFor="review-token" className={label}><KeyRound aria-hidden className="mr-1 inline size-3.5" strokeWidth={2.2} />Token reviewer</label>
          <input id="review-token" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" className={input} />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="review-note" className={label}>Catatan (opsional)</label>
          <input id="review-note" value={note} onChange={(e) => setNote(e.target.value)} className={input}
            placeholder="Misalnya: driver sesuai rilis 1H dan panduan emiten" />
        </div>
      </div>

      {!view.enabled && (
        <p className="text-[14px] text-ink-soft">Review belum diaktifkan di server ini. Jalankan server dengan <code className="font-mono text-[13px]">SECTORAL_REVIEW_TOKEN</code>.</p>
      )}
      {missingReason.length > 0 && (
        <p className="text-[14px] text-warn-ink">Isi alasan untuk {missingReason.map((f) => f.label).join(", ")}.</p>
      )}
      {error && <p role="alert" className="text-[14px] text-err-ink">{error}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={!canSubmit} className="btn btn-primary disabled:cursor-not-allowed">
          {busy ? (changed.length ? "Membangun ulang laporan…" : "Menyimpan…")
            : changed.length ? `Setujui dengan ${changed.length} perubahan` : "Setujui asumsi"}
        </button>
        <span className="text-[13px] text-ink-soft">
          {changed.length ? "Laporan dibangun ulang dari rencana yang diubah, tanpa memanggil agent." : "Persetujuan dicatat di jejak audit."}
        </span>
      </div>
    </form>
  );
}

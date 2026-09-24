import type { Intel, Signal } from "../lib/api";

const VERDICT: Record<string, string> = { didukung: "pill-ok", "tidak didukung": "pill-err" };
const ORIGIN: Record<string, [string, string]> = {
  agent: ["", "sesuai rencana"],
  agent_adaptive: ["pill-live", "keputusan baru agent"],
};

function Card({ title, id, children }: { title: string; id?: string; children: React.ReactNode }) {
  return (
    <div className="card" id={id}>
      <h3 className="mb-3 text-[17px]">{title}</h3>
      {children}
    </div>
  );
}

function Citations({ ids, signals }: { ids: string[]; signals: Record<string, Signal> }) {
  const cited = ids.map((id) => signals[id]).filter(Boolean);
  if (!cited.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {cited.map((s) => (
        <span key={s.id} className={`rounded-md border px-2 py-0.5 text-[12.5px] ${s.kind === "web" ? "border-warn-rule/40 bg-warn-bg" : "border-rule-soft bg-canvas"}`}>
          {s.kind === "web" ? `Web: ${(s.label ?? "").slice(0, 70)}` : `${s.label}: ${s.display}`}
        </span>
      ))}
    </div>
  );
}

export function IntelHeadline({ intel }: { intel: Intel }) {
  const synthesis = intel.synthesis;
  return (
    <div className="card">
      <p className="text-sm font-bold text-brand-ink">Intelijen pasar {intel.name ?? intel.ticker}</p>
      <h2 className="mt-2 mb-3.5 max-w-[70ch] text-[22px] leading-snug font-black">{synthesis.headline}</h2>
      <div className="flex flex-wrap gap-2">
        {intel.peers.group && <span className="pill pill-live">Grup: {intel.peers.group}</span>}
        {intel.market_date && <span className="pill">Data pasar {intel.market_date}</span>}
        <span className={`pill ${synthesis.source === "agent" ? "pill-ok" : "pill-warn"}`}>
          {synthesis.source === "agent" ? "Kesimpulan agent tervalidasi" : "Ringkasan aturan host"}
        </span>
      </div>
    </div>
  );
}

export function IntelSections({ intel }: { intel: Intel }) {
  const signals = Object.fromEntries(intel.signals.filter((s) => s.id).map((s) => [s.id as string, s]));
  const verdicts = Object.fromEntries(intel.synthesis.hypotheses.filter((h) => h.index != null).map((h) => [h.index as number, h]));
  const peers = intel.signals.filter((s) => s.kind === "peer");
  const flagged = intel.signals.filter((s) => s.flag && s.kind !== "peer");
  const changes = intel.changes;
  const next = intel.synthesis.next_checks.filter(Boolean) as string[];
  const th = "px-2 py-2.5 text-left text-[13px] font-bold text-ink-soft";

  return (
    <>
      <Card title="Rencana & hipotesis agent">
        <p className="mb-3.5 max-w-[880px] font-bold">{intel.plan.question}</p>
        <ol className="m-0 grid max-w-[880px] gap-4 pl-5">
          {intel.plan.hypotheses.map((h, i) => {
            const v = verdicts[i];
            return (
              <li key={i}>
                <div className="flex items-start justify-between gap-2.5">
                  <span>{h}</span>
                  <span className={`pill flex-none ${VERDICT[v?.verdict ?? ""] ?? ""}`}>{v?.verdict ?? "belum dinilai"}</span>
                </div>
                {v?.reason && <p className="text-[13.5px] text-ink-soft">{v.reason}</p>}
                <Citations ids={v?.signal_ids ?? []} signals={signals} />
              </li>
            );
          })}
        </ol>
      </Card>

      {peers.length > 0 && (
        <Card title="Posisi terhadap peer">
          {intel.peers.basis && <p className="text-[13.5px] text-ink-soft">Basis: {intel.peers.basis}</p>}
          <div className="relative overflow-x-auto">
            <table className="w-full border-collapse text-sm [&_td]:border-b [&_td]:border-rule-soft [&_td]:px-2 [&_td]:py-2.5 [&_th]:border-b [&_th]:border-rule-soft">
              <thead><tr>
                <th scope="col" className={th}>Metrik</th><th scope="col" className={th}>Emiten</th>
                <th scope="col" className={th}>Peringkat <small className="font-normal">(kiri = tertinggi)</small></th>
                <th scope="col" className={th}>Median peer</th><th scope="col" className={th}><span className="sr-only">Tanda</span></th>
              </tr></thead>
              <tbody>
                {peers.map((s) => (
                  <tr key={s.id}>
                    <th scope="row" className="px-2 py-2.5 text-left font-bold whitespace-nowrap">{s.label}</th>
                    <td className="tabular-nums whitespace-nowrap">{s.display}</td>
                    <td>
                      {s.rank && s.n ? (
                        <>
                          <div role="img" aria-label={`peringkat ${s.rank} dari ${s.n}`} className="mb-0.5 flex gap-[3px]">
                            {Array.from({ length: s.n }, (_, i) => (
                              <span key={i} className={`size-2.5 rounded-[3px] ${i + 1 === s.rank ? "scale-125 bg-brand" : "bg-rule-soft"}`} />
                            ))}
                          </div>
                          <small className="text-ink-soft">{s.rank} / {s.n}</small>
                        </>
                      ) : <small className="text-ink-soft">{s.note || "n.a."}</small>}
                    </td>
                    <td className="tabular-nums whitespace-nowrap text-ink-soft">{s.median_display || "—"}</td>
                    <td>{s.flag && <span className="pill pill-warn">{s.flag}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {flagged.length > 0 && (
        <Card title="Sinyal yang perlu dicek">
          <ul className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-3 p-0">
            {flagged.map((s) => (
              <li key={s.id} className="grid content-start gap-1.5 rounded-[10px] border border-rule px-3.5 py-3">
                <div className="flex justify-between gap-2.5 text-sm"><strong>{s.label}</strong><span className="tabular-nums whitespace-nowrap">{s.display}</span></div>
                <span className="pill pill-warn justify-self-start">{s.flag}</span>
                {(s.period || s.note) && <p className="text-[13.5px] text-ink-soft">{[s.period, s.note].filter(Boolean).join(" · ")}</p>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {intel.synthesis.findings.length > 0 && (
        <Card title="Temuan">
          <div className="grid items-start gap-x-8 gap-y-6 [grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr))]">
            {intel.synthesis.findings.map((f, i) => (
              <article key={i} className="grid content-start gap-2 border-t border-rule pt-4">
                <h4 className="text-base">{f.title}</h4>
                <p className="text-[15px]">{f.interpretation}</p>
                <p className="text-[13.5px] text-ink-soft"><strong>Batas bukti. </strong>{f.caveat}</p>
                <Citations ids={f.signal_ids} signals={signals} />
              </article>
            ))}
          </div>
        </Card>
      )}

      {intel.web_news.items.length > 0 && (
        <Card title="Konteks berita web">
          <p className="text-[13.5px] text-ink-soft">
            Berita {intel.web_news.window ?? ""}. Hanya konteks naratif, bukan data Sectors; tidak ada angka sinyal yang berasal dari sini.
          </p>
          <ul className="mt-2.5 grid list-none gap-2.5 p-0 text-[14.5px]">
            {intel.web_news.items.map((item) => (
              <li key={item.url}>
                <a href={item.url ?? undefined} target="_blank" rel="noopener noreferrer" className="font-medium">{item.title}</a>
                <span className="text-[13.5px] text-ink-soft"> {item.date}, {item.domain}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid items-start gap-6 min-[881px]:grid-cols-[1fr_1.2fr] [&>*]:min-w-0">
        <Card title="Sejak riset terakhir">
          {changes.first_run ? (
            <p className="text-ink-soft">Riset pertama untuk emiten ini. Hasilnya disimpan sebagai memori untuk dibandingkan pada riset berikutnya.</p>
          ) : (
            <>
              <p className="text-[13.5px] text-ink-soft">
                Dibanding riset {String(changes.previous_run_at ?? "").slice(0, 16).replace("T", " ")} (data pasar {changes.previous_market_date ?? "—"}).
              </p>
              {changes.items.length ? (
                <ul className="mt-2 grid gap-1 pl-[18px] text-[14.5px]">
                  {changes.items.map((c, i) => <li key={i} className={c.kind === "new_flag" ? "text-warn-ink" : ""}>{c.text}</li>)}
                </ul>
              ) : (
                <p>{changes.same_market_date ? "Data pasar belum berubah sejak riset terakhir; tidak ada sinyal yang bergeser." : "Tidak ada sinyal yang bergeser."}</p>
              )}
            </>
          )}
          {next.length > 0 && (
            <>
              <h4 className="mt-[18px] mb-1.5 text-sm">Pemeriksaan lanjutan yang disarankan agent</h4>
              <ul className="m-0 pl-[18px] text-[14.5px]">{next.map((t) => <li key={t}>{t}</li>)}</ul>
            </>
          )}
        </Card>
        <Card title="Keputusan tool agent">
          <ol className="m-0 grid gap-3 pl-5">
            {intel.steps.map((s, i) => {
              const [cls, label] = ORIGIN[s.origin ?? ""] ?? ["", "dilengkapi host"];
              return (
                <li key={i}>
                  <div className="flex flex-wrap items-baseline gap-2">
                    <code className="rounded-[5px] bg-brand-50 px-1.5 py-px font-mono text-xs text-brand-ink">{s.tool}</code>
                    <span className={`pill px-2 py-px text-xs ${cls}`}>{label}</span>
                  </div>
                  {s.why && <p className="text-[13.5px]">{s.why}</p>}
                  {s.summary && <p className="text-[13.5px] text-ink-soft">{s.summary}</p>}
                </li>
              );
            })}
          </ol>
        </Card>
      </div>
    </>
  );
}

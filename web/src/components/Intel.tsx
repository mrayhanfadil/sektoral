import { CornerDownRight, ExternalLink } from "lucide-react";
import type { Intel, Signal } from "../lib/api";
import { STATUS_WORD, type Status } from "../lib/agents";
import { VERDICT_WORD, verdictCode, type VerdictCode } from "../lib/codes";
import { twin, useLang, type Bi, type Lang } from "../lib/i18n";

/** Section anchors, shared with the trace page's index so labels match headings. Pipeline order. */
export const INTEL_SECTIONS: [string, Bi][] = [
  ["rencana", { id: "Rencana & hipotesis", en: "Plan & hypotheses" }],
  ["keputusan-tool", { id: "Keputusan tool", en: "Tool decisions" }],
  ["sinyal", { id: "Sinyal yang perlu dicek", en: "Signals to check" }],
  ["posisi-peer", { id: "Posisi terhadap peer", en: "Position against peers" }],
  ["temuan-agent", { id: "Temuan agent", en: "Agent findings" }],
  ["berita-web", { id: "Konteks berita web", en: "Web News context" }],
  ["perubahan", { id: "Sejak riset terakhir", en: "Since the last run" }],
];
const TITLE = Object.fromEntries(INTEL_SECTIONS);

/* ------------------------------------------------------------------ */
/* Primitives shared with the trace page: ruled sections, chips, words. */

const CHIP = {
  neutral: "border-rule bg-raised text-ink-soft",
  ok: "border-ok-ink/25 bg-ok-bg text-ok-ink",
  warn: "border-warn-rule/50 bg-warn-bg text-warn-ink",
  err: "border-err-ink/25 bg-err-bg text-err-ink",
  brand: "border-brand-ink/25 bg-brand-50 text-brand-ink",
  dashed: "border-dashed border-rule-strong bg-transparent text-ink-soft",
} as const;
export type ChipTone = keyof typeof CHIP;

export function Chip({ tone = "neutral", mono, children, className = "" }:
  { tone?: ChipTone; mono?: boolean; children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center gap-1.5 rounded-[5px] border px-1.5 py-px text-[12.5px] leading-5 font-medium ${
      mono ? "font-mono text-[12px]" : ""} ${CHIP[tone]} ${className}`}>
      {children}
    </span>
  );
}

const WORD_TONE: Record<Status, string> = {
  idle: "text-ink-faint", run: "text-brand-ink", ok: "text-done", warn: "text-warn-ink", error: "text-err-ink",
};

/** A status: dot plus word. The bare status code reads in mono; a sentence in Roboto. */
export function StatusWord({ status, children }: { status: Status; children?: React.ReactNode }) {
  const { t } = useLang();
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap ${children ? "text-[12.5px] font-medium" : "data"} ${WORD_TONE[status]}`}>
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {children ?? t(STATUS_WORD[status])}
    </span>
  );
}

export function asStatus(value: string | null | undefined): Status {
  return value === "ok" || value === "warn" || value === "error" || value === "run" ? value : "idle";
}

/** A ruled section of a console panel. Its id feeds the trace index. */
export function Section({ id, title, count, aside, children }:
  { id: string; title: string; count?: number; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`}
      className="scroll-mt-20 border-t border-rule px-6 py-6 max-lg:scroll-mt-[116px] max-sm:px-4 max-sm:py-5">
      <div className="mb-3.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h3 id={`${id}-title`} className="flex items-baseline gap-2 text-[16.5px]">
          {title}
          {count != null && <span className="data font-normal text-ink-faint">{count}</span>}
        </h3>
        {aside && <div className="flex flex-wrap items-center gap-2">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

/** A small label heading inside a section. */
export function SubHead({ children }: { children: React.ReactNode }) {
  return <h4 className="mb-2 text-[13.5px] font-medium text-ink-soft">{children}</h4>;
}

/** What a section shows when the run recorded nothing for it. */
export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-md border border-dashed border-rule px-4 py-3 text-[14.5px] text-ink-soft">{children}</p>;
}

export function Source({ url, children }: { url: string | null | undefined; children?: React.ReactNode }) {
  const { t } = useLang();
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="font-sans">
      {children ?? t({ id: "sumber", en: "source" })}
      <ExternalLink aria-hidden className="ml-1 inline size-3 align-[-1px]" strokeWidth={2.2} />
      <span className="sr-only">{t({ id: "(tab baru)", en: "(new tab)" })}</span>
    </a>
  );
}

/* ------------------------------------------------------------------ */

/** Chip tone of a hypothesis verdict, by its code (`verdict_code`, else the Indonesian label). */
const VERDICT: Partial<Record<VerdictCode, ChipTone>> = { supported: "ok", not_supported: "err" };
const ORIGIN: Record<string, [ChipTone, Bi]> = {
  agent: ["neutral", { id: "sesuai rencana", en: "as planned" }],
  agent_adaptive: ["brand", { id: "keputusan baru agent", en: "new agent decision" }],
};

function Card({ id, count, children }: { id: string; count?: number; children: React.ReactNode }) {
  const { t } = useLang();
  return <Section id={id} title={t(TITLE[id])} count={count}>{children}</Section>;
}

/** A signal's host-written words in the reader's language (lib/i18n.ts `twin`). */
function signalText(s: Signal, lang: Lang) {
  return {
    label: twin(s, "label", lang), display: twin(s, "display", lang), flag: twin(s, "flag", lang),
    note: twin(s, "note", lang), period: twin(s, "period", lang),
  };
}

function Citations({ ids, signals }: { ids: string[]; signals: Record<string, Signal> }) {
  const { t, lang } = useLang();
  const cited = ids.map((id) => signals[id]).filter(Boolean);
  if (!cited.length) return null;
  return (
    <ul aria-label={t({ id: "Sinyal yang dikutip", en: "Cited signals" })} className="mt-2 flex list-none flex-wrap gap-1.5 p-0">
      {cited.map((s) => {
        const text = signalText(s, lang);
        return (
          <li key={s.id} className="max-w-full">
            {s.kind === "web" ? (
              <Chip tone="warn"><span className="truncate">Web: {(text.label ?? "").slice(0, 70)}</span></Chip>
            ) : (
              <Chip>
                <span className="text-ink">{text.label}</span>
                <span className="font-mono text-[12px] font-semibold text-ink-strong">{text.display}</span>
              </Chip>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** The analyst agent's result on one surface: headline, then ruled sections. */
export function IntelPanel({ intel }: { intel: Intel }) {
  return (
    <div className="panel overflow-clip">
      <header className="px-6 py-6 max-sm:px-4 max-sm:py-5">
        <IntelHeadline intel={intel} />
      </header>
      <IntelSections intel={intel} />
    </div>
  );
}

/** Headline and provenance chips. `as="p"` when the page already has an h2 for the agent. */
export function IntelHeadline({ intel, as: Tag = "h2" }: { intel: Intel; as?: "h2" | "p" }) {
  const { t, lang } = useLang();
  const synthesis = intel.synthesis;
  const byAgent = synthesis.source === "agent";
  return (
    <>
      <Tag className="mb-3.5 max-w-[72ch] text-[21px] leading-snug font-bold text-ink-strong text-balance max-sm:text-[19px]">
        {twin(synthesis, "headline", lang)}
      </Tag>
      <div className="flex flex-wrap gap-2">
        <Chip>{intel.name ?? intel.ticker}</Chip>
        {intel.peers.group && <Chip tone="brand">{t({ id: "Grup", en: "Group" })}: {twin(intel.peers, "group", lang)}</Chip>}
        {intel.market_date && <Chip mono>{t({ id: "Data pasar", en: "Market data" })} {intel.market_date}</Chip>}
        <Chip tone={byAgent ? "ok" : "warn"}>{byAgent ? t({ id: "Kesimpulan agent tervalidasi", en: "Validated agent conclusion" }) : t({ id: "Ringkasan aturan host", en: "Host-rule summary" })}</Chip>
        {intel.status && intel.status !== "ok" && <Chip tone="warn">Status: {intel.status === "partial" ? t({ id: "parsial", en: "partial" }) : intel.status}</Chip>}
      </div>
    </>
  );
}

const th = "px-2 py-2 text-left text-[12.5px] font-medium text-ink-soft";

function hypothesisText(text: string | null, i: number): [string, string] {
  const match = (text ?? "").match(/^\s*(H\d+)\s*[:.]\s*/);
  return match ? [match[1], (text ?? "").slice(match[0].length)] : [`H${i + 1}`, text ?? ""];
}

export function IntelSections({ intel }: { intel: Intel }) {
  const { t, lang } = useLang();
  const signals = Object.fromEntries(intel.signals.filter((s) => s.id).map((s) => [s.id as string, s]));
  const verdicts = Object.fromEntries(intel.synthesis.hypotheses.filter((h) => h.index != null).map((h) => [h.index as number, h]));
  const peers = intel.signals.filter((s) => s.kind === "peer");
  const flagged = intel.signals.filter((s) => s.flag && s.kind !== "peer");
  const changes = intel.changes;
  // Agent text in the reader's language: each `_en` twin where the agent wrote one (lib/i18n.ts `twin`).
  const hypotheses = twin(intel.plan, "hypotheses", lang);
  const next = twin(intel.synthesis, "next_checks", lang).filter(Boolean) as string[];

  return (
    <>
      <Card id="rencana">
        <p className="mb-1 max-w-[80ch] text-[16.5px] leading-snug font-bold text-ink-strong">{twin(intel.plan, "question", lang)}</p>
        {intel.plan.source && (
          <p className="mb-4 text-[13px] text-ink-soft">
            {t({ id: "Disusun oleh", en: "Written by" })}{" "}
            {intel.plan.source === "agent" ? t({ id: "agent perencana", en: "the planning agent" }) : <span className="font-mono">{intel.plan.source}</span>}
          </p>
        )}
        <ol className="m-0 grid max-w-[920px] list-none divide-y divide-rule-soft p-0">
          {hypotheses.map((h, i) => {
            const v = verdicts[i];
            const code = v ? verdictCode(v.verdict_code, v.verdict) : undefined;
            const reason = v ? twin(v, "reason", lang) : null;
            const [label, text] = hypothesisText(h, i);
            return (
              <li key={i} className="grid grid-cols-[36px_minmax(0,1fr)] gap-x-3 py-3 first:pt-0 last:pb-0">
                <span className="data pt-[3px] font-semibold text-brand-ink">{label}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
                    <p className="min-w-0 flex-1 basis-[280px] text-[15px]">{text}</p>
                    <Chip tone={v?.verdict || code ? (code && VERDICT[code]) ?? "neutral" : "dashed"} className="flex-none">
                      {code ? t(VERDICT_WORD[code]) : v?.verdict ? v.verdict : t({ id: "belum dinilai", en: "not assessed" })}
                    </Chip>
                  </div>
                  {reason && <p className="mt-1 text-[13.5px] text-ink-soft">{reason}</p>}
                  <Citations ids={v?.signal_ids ?? []} signals={signals} />
                </div>
              </li>
            );
          })}
        </ol>
      </Card>

      {intel.steps.length > 0 && (
        <Card id="keputusan-tool" count={intel.steps.length}>
          <ol className="m-0 grid list-none divide-y divide-rule-soft p-0">
            {intel.steps.map((s, i) => {
              const [tone, label] = ORIGIN[s.origin ?? ""] ?? ["dashed", { id: "dilengkapi host", en: "filled in by host" }];
              const status = asStatus(s.status);
              return (
                <li key={i} className="grid grid-cols-[28px_minmax(0,1fr)] gap-x-3 py-3 first:pt-0 last:pb-0">
                  <span className="data pt-[3px] text-ink-faint">{String(i + 1).padStart(2, "0")}</span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                      <code className="font-mono text-[13.5px] font-semibold text-brand-ink">{s.tool}</code>
                      <Chip tone={tone}>{t(label)}</Chip>
                      <span className="ml-auto">
                        {status === "idle" && s.status ? <StatusWord status="idle"><code className="font-mono text-[12px]">{s.status}</code></StatusWord> : status !== "idle" && <StatusWord status={status} />}
                      </span>
                    </div>
                    {s.why && <p className="mt-1 text-[14.5px]">{twin(s, "why", lang)}</p>}
                    {s.summary && (
                      <p className="mt-1 flex items-start gap-1.5 text-[13.5px] text-ink-soft">
                        <CornerDownRight aria-hidden className="mt-[3px] size-3.5 flex-none text-ink-faint" strokeWidth={2.2} />
                        <span className="min-w-0"><span className="sr-only">{t({ id: "Hasil: ", en: "Result: " })}</span>{twin(s, "summary", lang)}</span>
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </Card>
      )}

      {flagged.length > 0 && (
        <Card id="sinyal" count={flagged.length}>
          <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[14px] [&_td]:border-t [&_td]:border-rule-soft [&_td]:px-2 [&_td]:py-2.5 [&_td]:align-top">
            <thead><tr>
              <th scope="col" className={th}>{t({ id: "Sinyal", en: "Signal" })}</th>
              <th scope="col" className={`${th} text-right`}>{t({ id: "Nilai", en: "Value" })}</th>
              <th scope="col" className={`${th} max-sm:hidden`}>{t({ id: "Tanda", en: "Flag" })}</th>
              <th scope="col" className={`${th} max-md:hidden`}>{t({ id: "Periode dan catatan", en: "Period and note" })}</th>
            </tr></thead>
            <tbody>
              {flagged.map((signal) => {
                const s = signalText(signal, lang);
                return (
                  <tr key={signal.id}>
                    <th scope="row" className="border-t border-rule-soft px-2 py-2.5 text-left align-top font-medium text-ink-strong">
                      {s.label}
                      <span className="mt-1 block sm:hidden"><Chip tone="warn">{s.flag}</Chip></span>
                      <span className="mt-1 block text-[13px] font-normal text-ink-soft md:hidden">{[s.period, s.note].filter(Boolean).join("; ")}</span>
                    </th>
                    <td className="text-right font-mono text-[13.5px] tabular-nums text-ink-strong sm:whitespace-nowrap">{s.display}</td>
                    <td className="max-sm:hidden"><Chip tone="warn">{s.flag}</Chip></td>
                    <td className="text-[13.5px] text-ink-soft max-md:hidden">{[s.period, s.note].filter(Boolean).join("; ") || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        </Card>
      )}

      {peers.length > 0 && (
        <Card id="posisi-peer" count={peers.length}>
          {intel.peers.basis && <p className="mb-3 text-[13.5px] text-ink-soft">{t({ id: "Basis", en: "Basis" })}: {twin(intel.peers, "basis", lang)}</p>}
          <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[14px] [&_td]:border-t [&_td]:border-rule-soft [&_td]:px-2 [&_td]:py-2.5 [&_td]:align-top">
            <thead><tr>
              <th scope="col" className={th}>{t({ id: "Metrik", en: "Metric" })}</th>
              <th scope="col" className={`${th} text-right`}>{t({ id: "Emiten", en: "Issuer" })}</th>
              <th scope="col" className={th}>
                {t({ id: "Peringkat", en: "Rank" })} <span className="font-normal max-sm:sr-only">{t({ id: "(kiri = tertinggi)", en: "(left = highest)" })}</span>
              </th>
              <th scope="col" className={`${th} text-right max-md:hidden`}>{t({ id: "Median peer", en: "Peer median" })}</th>
              <th scope="col" className={`${th} max-md:hidden`}><span className="sr-only">{t({ id: "Tanda", en: "Flag" })}</span></th>
            </tr></thead>
            <tbody>
              {peers.map((signal) => {
                const s = { ...signal, ...signalText(signal, lang) };
                return (
                  <tr key={s.id}>
                    <th scope="row" className="border-t border-rule-soft px-2 py-2.5 text-left align-top font-medium text-ink-strong">
                      {s.label}
                      <span className="mt-0.5 block text-[12.5px] font-normal text-ink-soft md:hidden">
                        {t({ id: "Median peer", en: "Peer median" })} <span className="font-mono">{s.median_display || "—"}</span>
                      </span>
                      {s.flag && <span className="mt-1 block md:hidden"><Chip tone="warn">{s.flag}</Chip></span>}
                    </th>
                    <td className="text-right font-mono text-[13.5px] tabular-nums text-ink-strong sm:whitespace-nowrap">{s.display}</td>
                    <td>
                      {s.rank && s.n ? (
                        <>
                          <div role="img" aria-label={t({ id: `peringkat ${s.rank} dari ${s.n}`, en: `rank ${s.rank} of ${s.n}` })} className="mt-1 mb-1 flex gap-[2px] sm:gap-[3px]">
                            {Array.from({ length: s.n }, (_, i) => (
                              <span key={i} className={`size-2 rounded-[2px] sm:size-2.5 ${i + 1 === s.rank ? "scale-125 bg-brand" : "bg-rule"}`} />
                            ))}
                          </div>
                          <span className="data text-ink-soft">{s.rank} / {s.n}</span>
                        </>
                      ) : <span className="text-[13px] text-ink-soft">{s.note || "n.a."}</span>}
                    </td>
                    <td className="text-right font-mono text-[13.5px] whitespace-nowrap tabular-nums text-ink-soft max-md:hidden">{s.median_display || "—"}</td>
                    <td className="max-md:hidden">{s.flag && <Chip tone="warn">{s.flag}</Chip>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        </Card>
      )}

      {intel.synthesis.findings.length > 0 && (
        <Card id="temuan-agent" count={intel.synthesis.findings.length}>
          <div className="grid items-start gap-x-8 gap-y-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr))]">
            {intel.synthesis.findings.map((f, i) => (
              <article key={i} className="grid content-start gap-1.5 border-t border-rule-soft pt-3.5">
                <h4 className="text-[15.5px]">{twin(f, "title", lang)}</h4>
                <p className="text-[15px]">{twin(f, "interpretation", lang)}</p>
                <p className="text-[13.5px] text-ink-soft"><span className="font-medium text-ink">{t({ id: "Batas bukti. ", en: "Evidence limit. " })}</span>{twin(f, "caveat", lang)}</p>
                <Citations ids={f.signal_ids} signals={signals} />
              </article>
            ))}
          </div>
        </Card>
      )}

      {intel.web_news.items.length > 0 && (
        <Card id="berita-web" count={intel.web_news.items.length}>
          <p className="mb-3 text-[13.5px] text-ink-soft">
            {t({ id: "Berita", en: "News" })} {intel.web_news.window ? <span className="font-mono">{intel.web_news.window}</span> : ""}.{" "}
            {t({
              id: "Hanya konteks naratif, bukan data Sectors; tidak ada angka sinyal yang berasal dari sini.",
              en: "Narrative context only, not Sectors data; no signal figure comes from here.",
            })}
          </p>
          <ul className="m-0 grid list-none divide-y divide-rule-soft p-0 text-[14.5px]">
            {intel.web_news.items.map((item, i) => (
              <li key={item.url ?? i} className="grid gap-x-4 gap-y-0.5 py-2 first:pt-0 sm:grid-cols-[96px_minmax(0,1fr)]">
                <time dateTime={item.date ?? undefined} title={item.date ?? undefined} className="data pt-[3px] text-ink-soft">{item.date?.slice(0, 10)}</time>
                <span className="min-w-0">
                  {item.url ? <Source url={item.url}>{item.title}</Source> : item.title}
                  {item.domain && <span className="ml-2 font-mono text-[12px] text-ink-faint">{item.domain}</span>}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card id="perubahan">
        {changes.first_run ? (
          <p className="text-ink-soft">
            {t({
              id: "Riset pertama untuk emiten ini. Hasilnya disimpan sebagai memori untuk dibandingkan pada riset berikutnya.",
              en: "First run for this issuer. Its results are kept as Run Memory for comparison with the next run.",
            })}
          </p>
        ) : (
          <>
            <p className="text-[13.5px] text-ink-soft">
              {t({ id: "Dibanding riset", en: "Compared with the run of" })}{" "}
              <span className="font-mono">{String(changes.previous_run_at ?? "").slice(0, 16).replace("T", " ")}</span>{" "}
              ({t({ id: "data pasar", en: "market data" })} <span className="font-mono">{changes.previous_market_date ?? "—"}</span>).
            </p>
            {changes.items.length ? (
              <ul className="mt-2 grid gap-1 pl-[18px] text-[14.5px]">
                {changes.items.map((c, i) => <li key={i} className={c.kind === "new_flag" ? "text-warn-ink" : ""}>{twin(c, "text", lang)}</li>)}
              </ul>
            ) : (
              <p className="mt-1">
                {changes.same_market_date
                  ? t({ id: "Data pasar belum berubah sejak riset terakhir; tidak ada sinyal yang bergeser.", en: "Market data unchanged since the last run; no signal moved." })
                  : t({ id: "Tidak ada sinyal yang bergeser.", en: "No signal moved." })}
              </p>
            )}
          </>
        )}
        {next.length > 0 && (
          <div className="mt-5">
            <SubHead>{t({ id: "Pemeriksaan lanjutan yang disarankan agent", en: "Follow-up checks suggested by the agent" })}</SubHead>
            <ul className="m-0 grid gap-1 pl-[18px] text-[14.5px]">{next.map((check) => <li key={check}>{check}</li>)}</ul>
          </div>
        )}
      </Card>
    </>
  );
}

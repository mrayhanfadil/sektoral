import { useMemo, useState } from "react";
import { CircleCheck, ClipboardCheck, Eye, KeyRound, TriangleAlert } from "lucide-react";
import { api, ApiError, type PreviewKind, type ReviewAttestation, type ReviewField, type ReviewView } from "../lib/api";
import { getLang, LOCALE, twin, useLang, type Bi, type Lang } from "../lib/i18n";
import { Chip } from "./Intel";
import { CHECK_LABELS, ReviewAttestationForm } from "./ReviewAttestationForm";
import { useLoad } from "./State";

const TOKEN_KEY = "sectoral.review-token";
const twoFormat = (locale: string) => new Intl.NumberFormat(locale, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const two: Bi<Intl.NumberFormat> = { id: twoFormat(LOCALE.id), en: twoFormat(LOCALE.en) };
const show = (value: number, unit: string, lang: Lang = getLang()) =>
  `${two[lang].format(value).replace("-", "−")}${unit === "%" ? "%" : "x"}`;

export function readReviewToken(): string {
  try { return sessionStorage.getItem(TOKEN_KEY) ?? ""; } catch { return ""; }
}
export function keepReviewToken(token: string) {
  try { sessionStorage.setItem(TOKEN_KEY, token); } catch { /* private window: ask again next time */ }
}

type Draft = Record<string, { value: string; reason: string }>;
const PUBLIC_DISCLOSURE_LABELS: Record<string, Bi> = {
  author_role: { id: "Peran penulis", en: "Author role" },
  issuer_relationship: { id: "Hubungan dengan emiten", en: "Relationship with the issuer" },
  economic_or_ownership_conflicts: { id: "Konflik ekonomi atau kepemilikan", en: "Economic or ownership conflicts" },
  scope_limitations: { id: "Cakupan dan batasan review", en: "Review scope and limitations" },
  rating_or_scenario_policy: { id: "Kebijakan rating atau label skenario", en: "Rating or scenario-label policy" },
};

/** "1 perubahan" / "1 change", "3 changes". */
const changes = (n: number): Bi => ({ id: `${n} perubahan`, en: `${n} ${n === 1 ? "change" : "changes"}` });

/** The analyst review of a report's Forecast Plan: who approved it, what they changed, or the form to do so. */
export function ReviewPanel({ ticker, reviewToken, bundleKinds = [], onApproved }: {
  ticker: string; reviewToken?: string;
  /** Artifact kinds the run manifest lists (`html`, `pdf_en`, ...); English previews show only when listed. */
  bundleKinds?: string[];
  onApproved: () => void;
}) {
  const { t } = useLang();
  const state = useLoad(() => api.review(ticker, reviewToken), [ticker, reviewToken]);
  const view = state.data;
  if (state.loading && !view) {
    return <div aria-hidden className="h-28 w-full animate-pulse rounded-lg bg-surface ring-1 ring-rule" />;
  }
  if (!view || view.state === "no_plan" || (view.state === "pending" && !view.fields)) return null;
  return (
    <section id="review" aria-labelledby="review-title" className="panel scroll-mt-20">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 px-6 py-5 max-sm:px-4">
        <div className="flex min-w-0 items-start gap-3">
          <ClipboardCheck aria-hidden className="mt-1 size-4.5 flex-none text-brand-ink" strokeWidth={2.2} />
          <div className="min-w-0">
            <h2 id="review-title" className="text-[20px]">{t({ id: "Review dan attestation publikasi", en: "Publication review and attestation" })}</h2>
            <p className="text-[14px] text-ink-soft">
              {t({
                id: "Publication Bundle hanya dapat diterbitkan sesudah reviewer menguji bukti, model, sensitivitas, dan disclosure untuk versi yang dibekukan.",
                en: "A Publication Bundle can be published only after a reviewer has tested the evidence, model, sensitivities and disclosures for the frozen version.",
              })}
            </p>
          </div>
        </div>
        {view.state === "approved" ? (
          <Chip tone="ok"><CircleCheck aria-hidden className="size-3.5" strokeWidth={2.4} />
            {view.edits.length
              ? `${t({ id: "Disetujui", en: "Approved" })}, ${t(changes(view.edits.length))}`
              : t({ id: "Disetujui", en: "Approved" })}
          </Chip>
        ) : (
          <Chip tone="warn"><TriangleAlert aria-hidden className="size-3.5" strokeWidth={2.4} />{t({ id: "Menunggu review", en: "Awaiting review" })}</Chip>
        )}
      </header>
      {view.state === "approved" ? <Approved view={view} /> : (
        <ReviewForm ticker={ticker} view={view} bundleKinds={bundleKinds} onDone={() => { state.reload(); onApproved(); }} />
      )}
    </section>
  );
}

const stamp = (at: string | null | undefined, lang: Lang = getLang()) => at ? new Date(at).toLocaleString(LOCALE[lang], {
  dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Jakarta" }) + " WIB" : "—";

function Approved({ view }: { view: ReviewView }) {
  const { t, lang } = useLang();
  const when = stamp(view.reviewed_at).replace(/ WIB$/, "");
  const history = view.history ?? [];
  const attestation = view.attestation;
  const checklist = attestation?.checklist ?? {};
  return (
    <div className="grid gap-4 border-t border-rule px-6 py-5 max-sm:px-4">
      <p className="text-[14.5px] text-ink">
        {t({ id: "Disetujui oleh", en: "Approved by" })} <strong className="text-ink-strong">{view.reviewer}</strong>
        {view.reviewer_role ? ` · ${view.reviewer_role}` : ""}, {when} WIB.
        {view.identity_source === "authenticated_registry"
          ? t({ id: " Identitas diverifikasi oleh registry reviewer.", en: " Identity verified by the reviewer registry." })
          : t({ id: " Identitas ini belum terverifikasi untuk publikasi.", en: " This identity is not yet verified for publication." })}
        {view.note && <> {t({ id: "Catatan", en: "Note" })}: {view.note}</>}
      </p>
      {attestation && (
        <details className="rounded-md border border-rule bg-raised/40">
          <summary className="cursor-pointer px-4 py-3 text-[14px] font-medium text-ink-strong">
            {t({ id: "Cakupan review", en: "Review scope" })} · {Object.keys(checklist).length} {t({ id: "area", en: "areas" })} · publication {view.publication_id?.slice(0, 10) ?? "—"}
          </summary>
          <div className="grid gap-4 border-t border-rule p-4">
            <div className="grid gap-2">
              {Object.entries(checklist).map(([key, item]) => (
                <div key={key} className="grid gap-0.5 border-b border-rule-soft pb-2 last:border-0">
                  <p className="m-0 text-[13.5px] font-medium text-ink-strong">
                    {CHECK_LABELS[key] ? t(CHECK_LABELS[key]) : key} · {item.status}
                    {item.period ? ` · ${item.period}` : ""}
                  </p>
                  <p className="m-0 text-[13px] text-ink">{item.note}</p>
                  {item.source_ids.length > 0 && <p className="m-0 text-[12px] text-ink-soft">{t({ id: "Sumber", en: "Sources" })}: {item.source_ids.join(", ")}</p>}
                  {item.items && <ol className="m-0 grid gap-1.5 pl-5 text-[13px] text-ink">
                    {item.items.map((assumption) => <li key={assumption.assumption_id}>
                      <strong>{assumption.description}</strong> {assumption.value_sensitivity}
                      {assumption.source_ids.length > 0 && <span className="block text-[12px] text-ink-soft">{t({ id: "Sumber", en: "Sources" })}: {assumption.source_ids.join(", ")}</span>}
                    </li>)}
                  </ol>}
                </div>
              ))}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(attestation.disclosures).filter(([key]) => key !== "reviewer_role").map(([key, value]) => {
                const display = typeof value === "string" ? value : `${value.status}: ${value.details}`;
                return <div key={key} className="rounded-md border border-rule-soft bg-surface px-3 py-2">
                  <p className="m-0 text-[12px] text-ink-soft">{PUBLIC_DISCLOSURE_LABELS[key] ? t(PUBLIC_DISCLOSURE_LABELS[key]) : key}</p>
                  <p className="m-0 mt-0.5 text-[13px] text-ink">{display}</p>
                </div>;
              })}
            </div>
            {attestation.objections.length > 0 && <div>
              <p className="m-0 mb-1 text-[13px] font-medium text-ink-strong">{t({ id: "Keberatan dan disposisi", en: "Objections and dispositions" })}</p>
              <ul className="m-0 grid gap-1 pl-5 text-[13px] text-ink">
                {attestation.objections.map((item, index) => <li key={index}>
                  {item.objection} · {item.disposition}: {item.response}
                </li>)}
              </ul>
            </div>}
            {attestation.required_edits.length > 0 && <div>
              <p className="m-0 mb-1 text-[13px] font-medium text-ink-strong">Required edits</p>
              <ul className="m-0 grid gap-1 pl-5 text-[13px] text-ink">
                {attestation.required_edits.map((item, index) => <li key={index}>{item.description} · {item.status}</li>)}
              </ul>
            </div>}
          </div>
        </details>
      )}
      {view.edits.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-[14px]">
            <thead>
              <tr className="border-b border-rule text-left text-[12.5px] text-ink-soft">
                <th scope="col" className="py-2 pr-4 font-medium">Driver</th>
                <th scope="col" className="py-2 pr-4 font-medium">{t({ id: "Tahun", en: "Year" })}</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">Agent</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">{t({ id: "Analis", en: "Analyst" })}</th>
                <th scope="col" className="py-2 pr-4 font-medium">{t({ id: "Alasan", en: "Reason" })}</th>
                <th scope="col" className="py-2 font-medium">{t({ id: "Diubah oleh", en: "Changed by" })}</th>
              </tr>
            </thead>
            <tbody>
              {view.edits.map((e) => (
                <tr key={e.path} className="border-b border-rule-soft align-top">
                  <td className="py-2 pr-4 text-ink-strong">{twin(e, "label", lang)}</td>
                  <td className="data py-2 pr-4 text-ink-soft">{e.year ?? t({ id: "berjalan", en: "current" })}</td>
                  <td className="data py-2 pr-4 text-right text-ink-soft line-through decoration-ink-faint">{show(e.from, e.unit)}</td>
                  <td className="data py-2 pr-4 text-right font-semibold text-ink-strong">{show(e.to, e.unit)}</td>
                  <td className="py-2 pr-4 text-ink">{e.reason}</td>
                  <td className="py-2 text-[13px] whitespace-nowrap text-ink-soft">{e.reviewer ?? view.reviewer}<br />{stamp(e.reviewed_at ?? view.reviewed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {history.length > 0 && (
        <details className="text-[14px]">
          <summary className="cursor-pointer text-ink-soft">{t({ id: "Persetujuan sebelumnya", en: "Earlier approvals" })} <span className="data">{history.length}</span></summary>
          <ol className="m-0 mt-2 grid list-none gap-1.5 border-l border-rule pl-4">
            {history.map((h, i) => (
              <li key={`${h.reviewed_at}-${i}`} className="text-ink-soft">
                <span className="text-ink-strong">{h.reviewer ?? "—"}</span>, {stamp(h.reviewed_at)}:{" "}
                {h.edits
                  ? `${t({ id: "disetujui dengan", en: "approved with" })} ${t(changes(h.edits))}`
                  : t({ id: "disetujui tanpa perubahan", en: "approved without changes" })}
                {h.note && <>. {h.note}</>}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

/** Bundle files a reviewer can open: [preview kind, button, manifest kind]. English only when the bundle lists it. */
const PREVIEWS: [PreviewKind, Bi, string][] = [
  ["pdf", { id: "Buka PDF", en: "Open PDF" }, "pdf"],
  ["html", { id: "Buka HTML", en: "Open HTML" }, "html"],
  ["trace", { id: "Buka jejak HTML", en: "Open HTML trace" }, "trace_html"],
  ["pdf_en", { id: "Buka PDF Inggris", en: "Open English PDF" }, "pdf_en"],
  ["html_en", { id: "Buka HTML Inggris", en: "Open English HTML" }, "html_en"],
];
const ENGLISH_KINDS: ReadonlySet<string> = new Set(["html_en", "pdf_en"]);

/** What each missing bundle part is called; an unknown kind shows as sent. */
const MISSING_LABEL: Record<string, Bi> = {
  html: { id: "HTML", en: "HTML" },
  pdf: { id: "PDF", en: "PDF" },
  trace_html: { id: "jejak HTML", en: "HTML trace" },
  html_en: { id: "HTML Inggris", en: "English HTML" },
  pdf_en: { id: "PDF Inggris", en: "English PDF" },
  publication_manifest: { id: "manifest publikasi", en: "publication manifest" },
  evidence_register: { id: "register bukti", en: "evidence register" },
};

function ReviewForm({ ticker, view, bundleKinds, onDone }: {
  ticker: string; view: ReviewView; bundleKinds: string[]; onDone: () => void;
}) {
  const { t, lang } = useLang();
  const [draft, setDraft] = useState<Draft>({});
  const [note, setNote] = useState("");
  const [attestation, setAttestation] = useState<ReviewAttestation | null>(null);
  const [token, setToken] = useState(readReviewToken);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const fields = view.fields ?? [];

  const years = useMemo(() => {
    const out = new Map<string, ReviewField[]>();
    for (const f of fields) {
      const key = f.year == null ? "—" : String(f.year);
      out.set(key, [...(out.get(key) ?? []), f]);
    }
    return [...out.entries()];
  }, [fields]);

  const changed = fields.filter((f) => {
    const d = draft[f.path];
    return d && d.value.trim() !== "" && Number(d.value.replace(",", ".")) !== f.value;
  });
  const missingReason = changed.filter((f) => (draft[f.path]?.reason ?? "").trim().length < 10);
  const missingArtifacts = view.missing_artifacts ?? [];
  const missingNames: Bi = {
    id: missingArtifacts.map((k) => MISSING_LABEL[k]?.id ?? k).join(", "),
    en: missingArtifacts.map((k) => MISSING_LABEL[k]?.en ?? k).join(", "),
  };
  const missingEnglish = missingArtifacts.some((k) => ENGLISH_KINDS.has(k));
  const previews = PREVIEWS.filter(([, , artifact]) => !ENGLISH_KINDS.has(artifact) || bundleKinds.includes(artifact));
  const manifestErrors = view.manifest_errors ?? [];
  const evidenceRegisterErrors = view.evidence_register_errors ?? [];
  const reviewerRole = view.current_reviewer?.role?.toLowerCase();
  const canSubmit = view.enabled && (reviewerRole === "reviewer" || reviewerRole === "compliance") &&
    missingArtifacts.length === 0 && manifestErrors.length === 0 && evidenceRegisterErrors.length === 0 &&
    (view.available_source_ids?.length ?? 0) > 0 && Boolean(token) &&
    attestation !== null && !missingReason.length && !busy;

  const set = (path: string, key: "value" | "reason", value: string) =>
    setDraft((d) => ({ ...d, [path]: { value: d[path]?.value ?? "", reason: d[path]?.reason ?? "", [key]: value } }));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    keepReviewToken(token);
    try {
      await api.approve(ticker, token, {
        note: note.trim(), attestation,
        edits: changed.map((f) => ({ path: f.path, value: Number(draft[f.path].value.replace(",", ".")),
          reason: draft[f.path].reason.trim() })),
      });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : t({ id: "Persetujuan gagal disimpan.", en: "The approval could not be saved." }));
    } finally {
      setBusy(false);
    }
  }

  async function openArtifact(kind: PreviewKind) {
    if (!token || previewBusy) return;
    const popup = window.open("about:blank", "_blank");
    if (!popup) {
      setPreviewError(t({ id: "Izinkan tab pratinjau dibuka oleh browser, lalu coba lagi.", en: "Allow the browser to open the preview tab, then try again." }));
      return;
    }
    setPreviewBusy(kind);
    setPreviewError(null);
    try {
      keepReviewToken(token);
      const file = await api.reviewArtifact(ticker, token, kind);
      const url = URL.createObjectURL(file);
      popup.location.replace(url);
      window.setTimeout(() => URL.revokeObjectURL(url), 5 * 60 * 1000);
    } catch (err) {
      popup.close();
      setPreviewError(err instanceof Error ? err.message : t({ id: "Pratinjau tidak bisa dibuka.", en: "The preview could not be opened." }));
    } finally {
      setPreviewBusy(null);
    }
  }

  const label = "mb-1 block text-[12.5px] font-medium text-ink-soft";
  const input = "h-10 w-full rounded-md border border-rule bg-raised px-3 text-[14.5px] text-ink-strong placeholder:text-ink-faint focus:border-brand-ink";
  return (
    <form onSubmit={submit} className="grid gap-5 border-t border-rule px-6 py-5 max-sm:px-4 [&>*]:min-w-0">
      {view.stale && (
        <p className="rounded-md border border-warn-rule/50 bg-warn-bg/50 px-4 py-2.5 text-[14px] text-warn-ink">
          {t({
            id: "Persetujuan sebelumnya berlaku untuk rencana lama; run baru mengganti Forecast Plan sehingga perlu direview lagi.",
            en: "The earlier approval covers an older plan; a new run replaced the Forecast Plan, so it needs review again.",
          })}
        </p>
      )}
      {missingArtifacts.length > 0 && (
        <p role="alert" className="rounded-md border border-warn-rule/50 bg-warn-bg/50 px-4 py-2.5 text-[14px] text-warn-ink">
          {t({
            id: `Bundle belum lengkap untuk review: ${missingNames.id}. Bangun HTML, PDF, dan jejak HTML${missingEnglish ? " (serta versi Inggrisnya)" : ""} dari run yang sama, lalu muat ulang halaman ini.`,
            en: `The bundle is incomplete for review: ${missingNames.en}. Build the HTML, PDF and HTML trace${missingEnglish ? " (and their English versions)" : ""} from the same run, then reload this page.`,
          })}
        </p>
      )}
      {manifestErrors.length > 0 && (
        <div role="alert" className="rounded-md border border-warn-rule/50 bg-warn-bg/50 px-4 py-2.5 text-[14px] text-warn-ink">
          <p className="m-0 font-medium">{t({ id: "Manifest publikasi belum valid.", en: "The publication manifest is not valid yet." })}</p>
          <ul className="mb-0 mt-1 pl-5">{manifestErrors.map((problem) => <li key={problem}>{problem}</li>)}</ul>
        </div>
      )}
      {evidenceRegisterErrors.length > 0 && (
        <div role="alert" className="rounded-md border border-warn-rule/50 bg-warn-bg/50 px-4 py-2.5 text-[14px] text-warn-ink">
          <p className="m-0 font-medium">{t({ id: "Evidence Register belum terikat ke manifest.", en: "The Evidence Register is not yet bound to the manifest." })}</p>
          <ul className="mb-0 mt-1 pl-5">{evidenceRegisterErrors.map((problem) => <li key={problem}>{problem}</li>)}</ul>
        </div>
      )}
      <details className="group rounded-md border border-rule">
        <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-3 text-[14.5px] font-medium text-ink-strong">
          <span>{t({ id: "Driver Forecast Plan", en: "Forecast Plan drivers" })} <span className="data text-ink-soft">{fields.length}</span></span>
          <span className="text-[13px] font-normal text-ink-soft">
            {changed.length
              ? t({ id: `${changed.length} diubah`, en: `${changed.length} changed` })
              : t({ id: "Ubah nilai bila perlu; kosong berarti setuju", en: "Change values if needed; blank means you agree" })}
          </span>
        </summary>
        <div className="overflow-x-auto border-t border-rule">
          <table className="w-full min-w-[720px] border-collapse text-[14px]">
            <thead>
              <tr className="border-b border-rule text-left text-[12.5px] text-ink-soft">
                <th scope="col" className="px-4 py-2 font-medium">Driver</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Agent</th>
                <th scope="col" className="w-32 px-4 py-2 font-medium">{t({ id: "Nilai analis", en: "Analyst value" })}</th>
                <th scope="col" className="px-4 py-2 font-medium">{t({ id: "Alasan perubahan", en: "Reason for change" })}</th>
              </tr>
            </thead>
            {years.map(([year, rows]) => (
              <tbody key={year}>
                <tr className="bg-raised"><th scope="rowgroup" colSpan={4} className="data px-4 py-1.5 text-left text-ink-soft">{year === "—" ? t({ id: "Tahun berjalan (1H aktual + H2)", en: "Current year (1H actual + H2)" }) : `FY${year.slice(-2)}F`}</th></tr>
                {rows.map((f) => {
                  const d = draft[f.path];
                  const edited = changed.includes(f);
                  const when = year === "—" ? t({ id: "tahun berjalan", en: "current year" }) : year;
                  return (
                    <tr key={f.path} className="border-b border-rule-soft align-top">
                      <td className="px-4 py-2 text-ink-strong" title={twin(f, "rationale", lang) || undefined}>{twin(f, "label", lang)}</td>
                      <td className="data px-4 py-2 text-right text-ink">{show(f.value, f.unit)}</td>
                      <td className="px-4 py-1.5">
                        <input aria-label={`${twin(f, "label", lang)} ${when}, ${t({ id: "nilai analis", en: "analyst value" })}`} inputMode="decimal"
                          value={d?.value ?? ""} placeholder={two[lang].format(f.value)}
                          onChange={(e) => set(f.path, "value", e.target.value)}
                          className={`${input} h-9 font-mono tabular-nums ${edited ? "border-brand-ink" : ""}`} />
                      </td>
                      <td className="px-4 py-1.5">
                        {edited ? (
                          <input aria-label={t({ id: `Alasan perubahan ${f.label} ${when}`, en: `Reason for changing ${twin(f, "label", lang)} ${when}` })} value={d?.reason ?? ""}
                            onChange={(e) => set(f.path, "reason", e.target.value)} placeholder={t({ id: "Wajib, minimal 10 karakter", en: "Required, at least 10 characters" })}
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

      <div className="grid gap-2 rounded-md border border-rule bg-raised px-4 py-3">
        <p className="m-0 text-[13.5px] font-medium text-ink-strong">{t({ id: "Pratinjau bundle yang akan diterbitkan", en: "Preview the bundle to be published" })}</p>
        <div className="flex flex-wrap gap-2">
          {previews.map(([kind, label, artifact]) => (
            <button key={kind} type="button" onClick={() => openArtifact(kind)}
              disabled={!token || previewBusy !== null || missingArtifacts.includes(artifact)}
              className="btn btn-sm btn-ghost disabled:cursor-not-allowed">
              <Eye aria-hidden className="size-3.5" strokeWidth={2.1} />
              {previewBusy === kind ? t({ id: "Membuka…", en: "Opening…" }) : t(label)}
            </button>
          ))}
        </div>
        {previewError && <p role="alert" className="m-0 text-[13px] text-err-ink">{previewError}</p>}
      </div>

      {view.attestation_schema ? (
        <ReviewAttestationForm schema={view.attestation_schema} identity={view.current_reviewer}
          availableSourceIds={view.available_source_ids ?? []} draft={view.attestation_draft}
          onChange={setAttestation} />
      ) : (
        <p className="rounded-md border border-warn-rule/50 bg-warn-bg/50 px-4 py-2.5 text-[14px] text-warn-ink">
          {t({
            id: "Checklist attestation belum tersedia. Autentikasikan reviewer yang terdaftar, lalu muat ulang halaman.",
            en: "The attestation checklist is not available yet. Authenticate a registered reviewer, then reload the page.",
          })}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label htmlFor="review-token" className={label}><KeyRound aria-hidden className="mr-1 inline size-3.5" strokeWidth={2.2} />{t({ id: "Token reviewer", en: "Reviewer token" })}</label>
          <input id="review-token" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" className={input} />
          {view.current_reviewer && <p className="m-0 mt-1.5 text-[12.5px] text-ink-soft">
            {t({ id: "Terautentikasi sebagai", en: "Authenticated as" })} {view.current_reviewer.name} · {view.current_reviewer.role}.
          </p>}
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="review-note" className={label}>{t({ id: "Catatan (opsional)", en: "Note (optional)" })}</label>
          <input id="review-note" value={note} onChange={(e) => setNote(e.target.value)} className={input}
            placeholder={t({ id: "Misalnya: driver sesuai rilis 1H dan panduan emiten", en: "For example: drivers match the 1H release and issuer guidance" })} />
        </div>
      </div>

      {!view.enabled && (
        <p className="text-[14px] text-ink-soft">{t({
          id: <>Approval belum aktif. Konfigurasikan <code className="font-mono text-[13px]">SECTORAL_REVIEWERS</code> dengan token hash dan peran reviewer.</>,
          en: <>Approval is not enabled. Configure <code className="font-mono text-[13px]">SECTORAL_REVIEWERS</code> with token hashes and reviewer roles.</>,
        })}</p>
      )}
      {view.enabled && reviewerRole !== "reviewer" && reviewerRole !== "compliance" && (
        <p role="alert" className="text-[14px] text-warn-ink">{t({
          id: "Token ini tidak memiliki peran reviewer atau compliance untuk menyetujui publikasi.",
          en: "This token does not carry a reviewer or compliance role, so it cannot approve publication.",
        })}</p>
      )}
      {missingReason.length > 0 && (
        <p className="text-[14px] text-warn-ink">{t({ id: "Isi alasan untuk", en: "Give a reason for" })} {missingReason.map((f) => twin(f, "label", lang)).join(", ")}.</p>
      )}
      {error && <p role="alert" className="text-[14px] text-err-ink">{error}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={!canSubmit} className="btn btn-primary disabled:cursor-not-allowed">
          {busy ? t(changed.length ? { id: "Membangun ulang laporan…", en: "Rebuilding the report…" } : { id: "Menyimpan…", en: "Saving…" })
            : changed.length ? `${t({ id: "Bangun ulang dengan", en: "Rebuild with" })} ${t(changes(changed.length))}`
            : t({ id: "Setujui bundle publikasi", en: "Approve the Publication Bundle" })}
        </button>
        <span className="text-[13px] text-ink-soft">
          {changed.length
            ? t({ id: "Perubahan membangun ulang laporan dan mengembalikannya ke review pending.", en: "Changes rebuild the report and return it to pending review." })
            : t({ id: "Persetujuan mengikat attestation, plan, manifest, dan file yang dirender.", en: "Approval binds the attestation, plan, manifest and rendered files." })}
        </span>
      </div>
    </form>
  );
}

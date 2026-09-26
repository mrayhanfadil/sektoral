import { useEffect, useState } from "react";
import type { AttestationDraft, ReviewAttestation, ReviewAttestationSchema, ReviewView } from "../lib/api";

type AssumptionDraft = { id: string; description: string; sensitivity: string; sourceIds: string };
type CheckDraft = { status: string; note: string; sourceIds: string; period: string; assumptions: AssumptionDraft[] };
type ObjectionDraft = { objection: string; response: string; disposition: "resolved" | "accepted"; sourceIds: string };
type EditDraft = { description: string; status: "completed" | "not_required" };
type OverrideDraft = { description: string; justification: string; policyVersion: string };
type ConflictDraft = { status: "none" | "disclosed" | "unknown"; details: string };
type FormState = {
  checks: Record<string, CheckDraft>;
  disclosures: Record<string, string>;
  conflicts: Record<string, ConflictDraft>;
  objections: ObjectionDraft[];
  requiredEdits: EditDraft[];
  overrides: OverrideDraft[];
};

export const CHECK_LABELS: Record<string, string> = {
  latest_official_actual_and_period: "Hasil resmi terbaru dan periode",
  material_source_claims_and_conflicts: "Klaim sumber material dan konflik bukti",
  top_three_value_sensitive_assumptions: "Tiga asumsi paling sensitif terhadap nilai",
  interim_statement_reconciliation: "Rekonsiliasi interim dan laporan keuangan",
  model_profile_and_method_chain: "Model Profile dan Method Chain",
  scenario_consistency: "Konsistensi base, downside, dan upside",
  catalyst_and_thesis_change_tests: "Katalis dan ambang perubahan tesis",
  consensus_comparison: "Perbandingan dengan konsensus independen",
  limitations_conflicts: "Keterbatasan dan konflik",
  earnings_normalization: "Normalisasi laba",
  restatements_corporate_actions: "Restatement dan aksi korporasi",
  house_assumptions_terminal_economics: "Asumsi house dan ekonomi terminal",
  independent_validation: "Validasi model independen",
  business_quality: "Kualitas bisnis",
  liquidity_limitations: "Likuiditas dan investability",
};

const DISCLOSURE_LABELS: Record<string, string> = {
  author_role: "Peran penulis",
  reviewer_role: "Peran reviewer",
  issuer_relationship: "Hubungan dengan emiten",
  economic_or_ownership_conflicts: "Konflik ekonomi atau kepemilikan",
  scope_limitations: "Cakupan dan batasan review",
  rating_or_scenario_policy: "Kebijakan rating atau label skenario",
};

const checkKeys = Object.keys(CHECK_LABELS);
const disclosureKeys = Object.keys(DISCLOSURE_LABELS);
const conflictKeys = ["issuer_relationship", "economic_or_ownership_conflicts"];
const emptyAssumption = (): AssumptionDraft => ({ id: "", description: "", sensitivity: "", sourceIds: "" });
const emptyCheck = (key: string): CheckDraft => ({
  status: key === "consensus_comparison" ? "not_available" : "reviewed",
  note: "", sourceIds: "", period: "",
  assumptions: key === "top_three_value_sensitive_assumptions"
    ? [emptyAssumption(), emptyAssumption(), emptyAssumption()] : [],
});
const emptyForm = (): FormState => ({
  checks: Object.fromEntries(checkKeys.map((key) => [key, emptyCheck(key)])),
  disclosures: Object.fromEntries(disclosureKeys.filter((key) => !conflictKeys.includes(key)).map((key) => [key, ""])),
  conflicts: Object.fromEntries(conflictKeys.map((key) => [key, { status: "none", details: "" }])),
  objections: [], requiredEdits: [], overrides: [],
});
/** The form pre-filled from the report's draft; conflicts stay for the reviewer to declare. */
const draftForm = (draft: AttestationDraft): FormState => {
  const form = emptyForm();
  for (const key of checkKeys) {
    const item = draft.checklist[key];
    if (!item) continue;
    form.checks[key] = {
      ...form.checks[key], status: item.status, note: item.note,
      sourceIds: item.source_ids.join(","), period: item.period ?? "",
      assumptions: item.items ? item.items.map((a) => ({ id: a.assumption_id, description: a.description,
        sensitivity: a.value_sensitivity, sourceIds: a.source_ids.join(",") })) : form.checks[key].assumptions,
    };
  }
  for (const [key, value] of Object.entries(draft.disclosures)) {
    if (key in form.disclosures) form.disclosures[key] = value;
  }
  return form;
};

const sourceIds = (text: string) => [...new Set(text.split(/[\n,;]+/).map((part) => part.trim()).filter(Boolean))];

function makeAttestation(form: FormState, schema: ReviewAttestationSchema): ReviewAttestation {
  const checklist = Object.fromEntries(checkKeys.map((key) => {
    const item = form.checks[key] ?? emptyCheck(key);
    const row: ReviewAttestation["checklist"][string] = {
      status: item.status,
      note: item.note.trim(),
      source_ids: sourceIds(item.sourceIds),
    };
    if (key === "latest_official_actual_and_period") row.period = item.period.trim();
    if (key === "top_three_value_sensitive_assumptions") {
      row.items = item.assumptions.map((assumption, index) => ({
        assumption_id: assumption.id.trim() || `assumption-${index + 1}`,
        description: assumption.description.trim(),
        value_sensitivity: assumption.sensitivity.trim(),
        source_ids: sourceIds(assumption.sourceIds),
      }));
    }
    return [key, row];
  }));
  const allSourceIds = new Set<string>();
  Object.values(checklist).forEach((item) => {
    item.source_ids.forEach((id) => allSourceIds.add(id));
    item.items?.forEach((assumption) => assumption.source_ids.forEach((id) => allSourceIds.add(id)));
  });
  form.objections.forEach((item) => sourceIds(item.sourceIds).forEach((id) => allSourceIds.add(id)));
  return {
    schema_version: schema.properties.schema_version?.const ?? "sektoral.institutional-review.v1",
    disposition: "approved",
    reviewed_source_ids: [...allSourceIds],
    checklist,
    objections: form.objections.filter((item) => item.objection.trim()).map((item) => ({
      objection: item.objection.trim(), response: item.response.trim(),
      disposition: item.disposition, source_ids: sourceIds(item.sourceIds),
    })),
    required_edits: form.requiredEdits.filter((item) => item.description.trim()).map((item) => ({
      description: item.description.trim(), status: item.status,
    })),
    disclosures: { ...form.disclosures, ...form.conflicts },
    overrides: form.overrides.filter((item) => item.description.trim()).map((item) => ({
      description: item.description.trim(), justification: item.justification.trim(),
      policy_version: item.policyVersion.trim(),
    })),
  };
}

export function ReviewAttestationForm({ schema, identity, availableSourceIds, draft, onChange }: {
  schema: ReviewAttestationSchema;
  identity: ReviewView["current_reviewer"];
  availableSourceIds: NonNullable<ReviewView["available_source_ids"]>;
  draft?: AttestationDraft | null;
  onChange: (attestation: ReviewAttestation) => void;
}) {
  const [form, setForm] = useState<FormState>(() => {
    const initial = draft ? draftForm(draft) : emptyForm();
    if (identity?.role) initial.disclosures.reviewer_role = identity.role;
    return initial;
  });
  // A pre-filled form is a candidate from the start; report it once.
  useEffect(() => {
    if (draft) onChange(makeAttestation(form, schema));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const properties = schema.properties.checklist?.properties ?? {};
  const labelClass = "mb-1 block text-[12.5px] font-medium text-ink-soft";
  const inputClass = "min-h-10 w-full rounded-md border border-rule bg-raised px-3 py-2 text-[14px] text-ink-strong placeholder:text-ink-faint focus:border-brand-ink";

  const update = (next: FormState) => {
    setForm(next);
    onChange(makeAttestation(next, schema));
  };
  const setCheck = (key: string, change: Partial<CheckDraft>) => {
    update({ ...form, checks: { ...form.checks, [key]: { ...form.checks[key], ...change } } });
  };
  const sourceField = (value: string, onValue: (v: string) => void) => {
    const selected = sourceIds(value);
    const add = (id: string) => {
      if (id && !selected.includes(id)) onValue([...selected, id].join(","));
    };
    const remove = (id: string) => onValue(selected.filter((item) => item !== id).join(","));
    return (
      <div className="grid gap-1.5">
        <label className="block">
          <span className={labelClass}>Pilih ID sumber yang diperiksa</span>
          <select value="" disabled={!availableSourceIds.length}
            onChange={(event) => { add(event.target.value); event.target.value = ""; }}
            className={inputClass}>
            <option value="">{availableSourceIds.length ? "Pilih dari Evidence Register…" : "Evidence Register tidak tersedia"}</option>
            {availableSourceIds.filter((item) => !selected.includes(item.id)).map((item) => {
              const period = Array.isArray(item.period) ? item.period.join("–") : item.period;
              const label = [item.kind, item.label, period].filter(Boolean).join(" · ");
              return <option key={item.id} value={item.id} title={item.source ?? undefined}>{label}</option>;
            })}
          </select>
        </label>
        {selected.length > 0 ? (
          <ul className="m-0 flex flex-wrap gap-1.5 p-0">
            {selected.map((id) => (
              <li key={id} className="list-none">
                <button type="button" onClick={() => remove(id)} aria-label={`Hapus sumber ${id}`}
                  className="rounded border border-rule bg-surface px-2 py-1 font-mono text-[11px] text-ink">
                  {id} <span aria-hidden>×</span>
                </button>
              </li>
            ))}
          </ul>
        ) : <p className="m-0 text-[11.5px] text-ink-faint">Pilih ID yang muncul di register tersimpan.</p>}
      </div>
    );
  };

  return (
    <div className="grid gap-4 rounded-md border border-rule bg-raised/40 p-4">
      <div>
        <h3 className="m-0 text-[15px] font-semibold text-ink-strong">Attestation review</h3>
        <p className="m-0 mt-1 text-[13px] text-ink-soft">
          Checklist ini ikut diikat ke Publication Bundle. Reviewer: {identity?.name ?? "belum terautentikasi"}
          {identity?.role ? ` · ${identity.role}` : ""}.
        </p>
        {draft && (
          <p className="m-0 mt-2 rounded-md border border-warn-rule/50 bg-warn-bg/50 px-3 py-2 text-[13px] text-warn-ink">
            {draft.note}
          </p>
        )}
      </div>

      <details className="rounded-md border border-rule bg-surface">
        <summary className="cursor-pointer px-3 py-2.5 text-[14px] font-medium text-ink-strong">
          15 area review wajib diisi
        </summary>
        <div className="grid gap-3 border-t border-rule p-3">
          {checkKeys.map((key) => {
            const check = form.checks[key];
            const rule = properties[key];
            const statusRule = rule?.properties?.status;
            const statusOptions = statusRule?.enum ?? (statusRule?.const ? [statusRule.const]
              : ["reviewed", "not_available", "not_applicable"]);
            return (
              <details key={key} className="rounded-md border border-rule-soft bg-surface">
                <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-[13.5px] font-medium text-ink-strong">
                  <span>{CHECK_LABELS[key]}</span>
                  <span className="font-mono text-[11.5px] text-ink-faint">{check.status}</span>
                </summary>
                <div className="grid gap-3 border-t border-rule-soft p-3">
                  <label className="block">
                    <span className={labelClass}>Disposition</span>
                    <select value={check.status} onChange={(event) => setCheck(key, { status: event.target.value })}
                      className={inputClass}>
                      {statusOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                    </select>
                  </label>
                  <label className="block">
                    <span className={labelClass}>Temuan review (minimal 8 karakter)</span>
                    <textarea value={check.note} onChange={(event) => setCheck(key, { note: event.target.value })}
                      className={`${inputClass} min-h-20`} />
                  </label>
                  {key === "latest_official_actual_and_period" && (
                    <label className="block">
                      <span className={labelClass}>Periode hasil resmi terbaru</span>
                      <input value={check.period} onChange={(event) => setCheck(key, { period: event.target.value })}
                        className={inputClass} placeholder="1H26" />
                    </label>
                  )}
                  {sourceField(check.sourceIds, (v) => setCheck(key, { sourceIds: v }))}
                  {key === "top_three_value_sensitive_assumptions" && (
                    <div className="grid gap-3 border-t border-rule-soft pt-3">
                      <p className="m-0 text-[13px] font-medium text-ink-strong">Tiga asumsi bernilai paling sensitif</p>
                      {check.assumptions.map((assumption, index) => {
                        const patchAssumption = (change: Partial<AssumptionDraft>) => {
                          const assumptions = check.assumptions.map((item, i) => i === index ? { ...item, ...change } : item);
                          setCheck(key, { assumptions });
                        };
                        return (
                          <fieldset key={index} className="grid gap-2 rounded-md border border-rule-soft p-3">
                            <legend className="px-1 text-[12.5px] font-medium text-ink-soft">Asumsi {index + 1}</legend>
                            <input aria-label={`ID asumsi ${index + 1}`} value={assumption.id}
                              onChange={(event) => patchAssumption({ id: event.target.value })}
                              className={inputClass} placeholder="ID driver atau asumsi" />
                            <textarea aria-label={`Deskripsi asumsi ${index + 1}`} value={assumption.description}
                              onChange={(event) => patchAssumption({ description: event.target.value })}
                              className={`${inputClass} min-h-16`} placeholder="Deskripsi driver dan basisnya" />
                            <textarea aria-label={`Sensitivitas nilai asumsi ${index + 1}`} value={assumption.sensitivity}
                              onChange={(event) => patchAssumption({ sensitivity: event.target.value })}
                              className={`${inputClass} min-h-16`} placeholder="Dampak perubahan driver pada laba, kas, atau nilai" />
                            {sourceField(assumption.sourceIds,
                              (v) => patchAssumption({ sourceIds: v }))}
                          </fieldset>
                        );
                      })}
                    </div>
                  )}
                </div>
              </details>
            );
          })}
        </div>
      </details>

      <details className="rounded-md border border-rule bg-surface">
        <summary className="cursor-pointer px-3 py-2.5 text-[14px] font-medium text-ink-strong">Deklarasi dan tindak lanjut</summary>
        <div className="grid gap-4 border-t border-rule p-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {disclosureKeys.filter((key) => !conflictKeys.includes(key)).map((key) => (
              <label key={key} className="block">
                <span className={labelClass}>{DISCLOSURE_LABELS[key]}</span>
                <textarea value={form.disclosures[key] ?? ""}
                  disabled={key === "reviewer_role" && Boolean(identity?.role)}
                  onChange={(event) => update({ ...form, disclosures: { ...form.disclosures, [key]: event.target.value } })}
                  className={`${inputClass} min-h-16`} />
              </label>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {conflictKeys.map((key) => {
              const conflict = form.conflicts[key];
              const options = schema.properties.disclosures?.properties?.[key]?.properties?.status?.enum
                ?? ["none", "disclosed", "unknown"];
              return (
                <fieldset key={key} className="grid content-start gap-2 rounded-md border border-rule-soft p-3">
                  <legend className="px-1 text-[12.5px] font-medium text-ink-soft">{DISCLOSURE_LABELS[key]}</legend>
                  <select aria-label={`Status ${DISCLOSURE_LABELS[key]}`} value={conflict.status} className={inputClass}
                    onChange={(event) => update({ ...form, conflicts: { ...form.conflicts,
                      [key]: { ...conflict, status: event.target.value as ConflictDraft["status"] } } })}>
                    {options.map((option) => <option key={option} value={option}>{option}</option>)}
                  </select>
                  <textarea aria-label={`Rincian ${DISCLOSURE_LABELS[key]}`} value={conflict.details}
                    className={`${inputClass} min-h-16`}
                    onChange={(event) => update({ ...form, conflicts: { ...form.conflicts,
                      [key]: { ...conflict, details: event.target.value } } })}
                    placeholder="Jelaskan hubungan/konflik atau nyatakan tidak ada." />
                  {conflict.status === "unknown" && <p className="m-0 text-[12px] text-warn-ink">Status unknown memblokir publikasi.</p>}
                </fieldset>
              );
            })}
          </div>
          <div className="grid gap-2 border-t border-rule-soft pt-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="m-0 text-[13.5px] font-medium text-ink-strong">Keberatan reviewer</p>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => update({ ...form,
                objections: [...form.objections, { objection: "", response: "", disposition: "resolved", sourceIds: "" }] })}>
                Tambah keberatan
              </button>
            </div>
            {form.objections.map((item, index) => (
              <fieldset key={index} className="grid gap-2 rounded-md border border-rule-soft p-3">
                <legend className="px-1 text-[12.5px] font-medium text-ink-soft">Keberatan {index + 1}</legend>
                <textarea aria-label={`Keberatan ${index + 1}`} value={item.objection} className={`${inputClass} min-h-16`}
                  onChange={(event) => update({ ...form, objections: form.objections.map((row, i) => i === index ? { ...row, objection: event.target.value } : row) })} />
                <textarea aria-label={`Respons keberatan ${index + 1}`} value={item.response} className={`${inputClass} min-h-16`}
                  onChange={(event) => update({ ...form, objections: form.objections.map((row, i) => i === index ? { ...row, response: event.target.value } : row) })} />
                <select aria-label={`Disposition keberatan ${index + 1}`} value={item.disposition} className={inputClass}
                  onChange={(event) => update({ ...form, objections: form.objections.map((row, i) => i === index ? { ...row, disposition: event.target.value as ObjectionDraft["disposition"] } : row) })}>
                  <option value="resolved">resolved</option><option value="accepted">accepted</option>
                </select>
                {sourceField(item.sourceIds,
                  (v) => update({ ...form, objections: form.objections.map((row, i) => i === index ? { ...row, sourceIds: v } : row) }))}
              </fieldset>
            ))}
          </div>
          <div className="grid gap-2 border-t border-rule-soft pt-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="m-0 text-[13.5px] font-medium text-ink-strong">Required edits</p>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => update({ ...form,
                requiredEdits: [...form.requiredEdits, { description: "", status: "completed" }] })}>
                Tambah item
              </button>
            </div>
            {form.requiredEdits.map((item, index) => (
              <div key={index} className="grid gap-2 sm:grid-cols-[1fr_180px]">
                <input aria-label={`Required edit ${index + 1}`} value={item.description} className={inputClass}
                  onChange={(event) => update({ ...form, requiredEdits: form.requiredEdits.map((row, i) => i === index ? { ...row, description: event.target.value } : row) })} />
                <select aria-label={`Status required edit ${index + 1}`} value={item.status} className={inputClass}
                  onChange={(event) => update({ ...form, requiredEdits: form.requiredEdits.map((row, i) => i === index ? { ...row, status: event.target.value as EditDraft["status"] } : row) })}>
                  <option value="completed">completed</option><option value="not_required">not_required</option>
                </select>
              </div>
            ))}
          </div>
          <div className="grid gap-2 border-t border-rule-soft pt-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="m-0 text-[13.5px] font-medium text-ink-strong">Override materialitas/toleransi</p>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => update({ ...form,
                overrides: [...form.overrides, { description: "", justification: "", policyVersion: "" }] })}>
                Tambah override
              </button>
            </div>
            {form.overrides.map((item, index) => (
              <fieldset key={index} className="grid gap-2 rounded-md border border-rule-soft p-3">
                <legend className="px-1 text-[12.5px] font-medium text-ink-soft">Override {index + 1}</legend>
                <input aria-label={`Deskripsi override ${index + 1}`} value={item.description} className={inputClass}
                  onChange={(event) => update({ ...form, overrides: form.overrides.map((row, i) => i === index ? { ...row, description: event.target.value } : row) })} />
                <textarea aria-label={`Justifikasi override ${index + 1}`} value={item.justification} className={`${inputClass} min-h-16`}
                  onChange={(event) => update({ ...form, overrides: form.overrides.map((row, i) => i === index ? { ...row, justification: event.target.value } : row) })} />
                <input aria-label={`Versi policy override ${index + 1}`} value={item.policyVersion} className={inputClass}
                  onChange={(event) => update({ ...form, overrides: form.overrides.map((row, i) => i === index ? { ...row, policyVersion: event.target.value } : row) })} />
              </fieldset>
            ))}
          </div>
        </div>
      </details>
    </div>
  );
}

"""Tool: check_output_schema — FORMAT OUTPUT §7.

Validates renderer JSON contract. null = unavailable, never 0.
Model-scenario label/value/difference only when release gate passes. log_gate internal only.
"""
from __future__ import annotations


def check_output_schema(doc: dict | None) -> dict:
    doc = doc or {}
    checks: list[dict] = []

    def v(cid: str, ok: bool, msg: str, blocker: bool = True):
        checks.append({"check": cid, "status": "lolos" if ok else "gagal",
                       "blocker": blocker and not ok, "message": msg})

    meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else None
    v("S.meta", isinstance(meta, dict), "meta dict wajib" if meta else "meta hilang")
    if isinstance(meta, dict):
        for k in ("ticker", "emiten", "tanggal", "status"):
            v(f"S.meta.{k}", bool(str(meta.get(k) or "").strip()),
              f"meta.{k} wajib" if not str(meta.get(k) or "").strip() else f"meta.{k} ok")
        st = str(meta.get("status") or "")
        has_tp = meta.get("tp") is not None or meta.get("rating") is not None or \
            meta.get("upside_persen") is not None
        if st == "draft_non_distributable":
            v("S.tp_draft", not has_tp, "draft tanpa rating/tp/upside" if not has_tp
              else "draft dilarang memuat rating/tp/upside")
        else:
            v("S.tp_draft", True, "status production; TP diizinkan bila gate lolos", False)

    cover = doc.get("cover") if isinstance(doc.get("cover"), dict) else None
    v("S.cover", isinstance(cover, dict), "cover dict wajib")
    is_prod = str((meta or {}).get("status") or "") != "draft_non_distributable" \
        if isinstance(meta, dict) else False
    if isinstance(cover, dict):
        b = cover.get("bullets")
        # Draft legacy uses 4 bullets / 2 paragraf; production §7 requires 3/3.
        if is_prod:
            v("S.bullets", isinstance(b, list) and len(b) == 3, "cover.bullets 3 item")
            p = cover.get("paragraf")
            v("S.paragraf", isinstance(p, list) and len(p) == 3, "cover.paragraf 3 item")
        else:
            v("S.bullets", isinstance(b, list) and 3 <= len(b) <= 4,
              "cover.bullets 3 item (draft 3-4 ditoleransi)")
            p = cover.get("paragraf")
            v("S.paragraf", isinstance(p, list) and 2 <= len(p) <= 3,
              "cover.paragraf 2-3 item (draft ditoleransi)")

    v("S.bagian", isinstance(doc.get("bagian"), list), "bagian list wajib")
    v("S.tabel_asumsi", isinstance(doc.get("tabel_asumsi"), list), "tabel_asumsi list wajib")

    lg = doc.get("log_gate")
    # Legacy draft log_gate has {S1,S2,S3,release} with release.blocker_count;
    # spec §7 wants release.blockers list. Accept both for draft, strict for production.
    if isinstance(lg, dict) and all(k in lg for k in ("S1", "S2", "S3", "release")):
        rel = lg.get("release") or {}
        if is_prod:
            v("S.log_gate", isinstance(rel, dict) and isinstance(rel.get("blockers"), list),
              "log_gate release.blockers list wajib (production)")
        else:
            v("S.log_gate", isinstance(rel, dict) and
              (isinstance(rel.get("blockers"), list) or isinstance(rel.get("blocker_count"), int)),
              "log_gate {S1,S2,S3,release} wajib (QA internal, tak dirender)")
    else:
        v("S.log_gate", False, "log_gate {S1,S2,S3,release} wajib (QA internal, tak dirender)")

    cm = doc.get("catatan_metodologi")
    v("S.metodologi", isinstance(cm, list) and len(cm) <= 6,
      "catatan_metodologi ≤5 poin (draft ≤6 ditoleransi)" if isinstance(cm, list)
      else "catatan_metodologi list wajib")

    # model_profile in meta required for production; draft legacy tolerated (profile in trace).
    if isinstance(meta, dict):
        if is_prod:
            v("S.meta.model_profile", bool(str(meta.get("model_profile") or "").strip()),
              "meta.model_profile wajib (production)")
        # draft: informational only, profile lives in intake/log_gate; don't block.

    blockers = [f"{c['check']}: {c['message']}" for c in checks if c.get("blocker")]
    return {"tool": "check_output_schema", "status": "lolos" if not blockers else "gagal",
            "checks": checks, "blockers": blockers}

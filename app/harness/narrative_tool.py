"""Tool: check_narrative + score_news — TAHAP 4 (§5) + SELF-CHECK (§6) Tier-1.

Deterministic text checks an LLM or template engine must pass.
Subjective checks (thesis quality, claim→angka→implikasi) stay as
LLM-judge prompts in llm_tools.py; this module blocks mechanical
violations: dashes, emoji, banned strings, period format, headline
lengths, number density, exhibit numbering/provenance, junk rows.
"""
from __future__ import annotations

import re

_LONG_DASH = re.compile(r"[—–]")
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]")
_PERIOD_OK = re.compile(r"\b(?:[1-4]Q\d{2}|[12]H\d{2}|9M\d{2}|FY\d{2})\b")
_PERIOD_BAD = re.compile(r"\bQ[1-4][-\s]?20\d{2}\b|\bKuartal\s+[IV1-4]\b", re.IGNORECASE)
_NUMBER = re.compile(r"\d[\d\.,]*\s*(?:%|x|Rp|US\$|miliar|triliun|juta|sen)?", re.IGNORECASE)

BANNED_BODY = ["endpoint", "payload", "engine deterministik",
               "policy tanpa estimasi karangan", "baris rekonsiliasi",
               "data/drivers"]
BANNED_PDF = ["kurasi skor", "sebelum masuk model", "aksi korporasi tercatat",
              "tanpa tanggal", "tanpa judul", "endpoint", "payload",
              "scraper", "scraping"]
# Whole-word pipeline tokens (avoid substring false positives like "gap" in "lengkap").
BANNED_TOKENS = [r"\blog\b", r"\bengine\b"]
BANNED_PHRASE = ["tentu saja", "perlu dicatat bahwa", "sebagai kesimpulan"]
CACHE_ALLOW = ("tidak ada di cache", "snapshot cache sectors", "sectors cache")


def _words(s: str) -> int:
    return len(str(s or "").split())


def _sentences(s: str) -> list[str]:
    # Jangan pecah titik ribuan Indonesia (1.021,3) atau desimal (2.052,0):
    # kalimat dipisah hanya pada tanda akhir yang diikuti spasi/akhir string.
    return [p.strip() for p in re.split(r"[.!?]+\s+|[.!?]+\s*$", str(s or "")) if p.strip()]


def _body_texts(doc: dict) -> list[str]:
    out: list[str] = []
    cover = (doc or {}).get("cover") or {}
    for p in cover.get("paragraf") or []:
        if isinstance(p, dict):
            out.append(str(p.get("isi") or "") + " " + str(p.get("judul") or ""))
        elif isinstance(p, str):
            out.append(p)
    for b in cover.get("bullets") or []:
        out.append(str(b))
    if cover.get("headline"):
        out.append(str(cover["headline"]))
    for sec in (doc or {}).get("bagian") or []:
        if isinstance(sec, dict):
            for p in sec.get("paragraf") or []:
                out.append(str(p))
    return out


def _exhibits(doc: dict) -> list[dict]:
    # doc menyimpan exhibit dua kali: top-level doc["exhibits"] (kanonis)
    # dan referensi yang sama di doc["bagian"][*]["exhibit"]. Setelah
    # round-trip JSON keduanya jadi kopi berbeda sehingga dedup id() gagal.
    # Ikuti report_contract: pakai top-level bila ada, jika tidak kumpulkan
    # dari bagian. Dedup berdasarkan nomor exhibit.
    top = [e for e in ((doc or {}).get("exhibits") or []) if isinstance(e, dict)]
    if top:
        seen: set[int] = set()
        out: list[dict] = []
        for e in top:
            try:
                n = int(e.get("n"))
            except (TypeError, ValueError):
                out.append(e)
                continue
            if n not in seen:
                seen.add(n)
                out.append(e)
        return out
    out = []
    for sec in (doc or {}).get("bagian") or []:
        if isinstance(sec, dict):
            out.extend(e for e in (sec.get("exhibit") or []) if isinstance(e, dict))
    return out


def check_narrative(doc: dict | None) -> dict:
    doc = doc or {}
    checks: list[dict] = []

    def v(cid: str, ok: bool, msg: str, blocker: bool = True,
          override: str | None = None) -> None:
        checks.append({"check": cid,
                       "status": override or ("lolos" if ok else "gagal"),
                       "blocker": blocker and not ok and (override or "") != "dilabeli",
                       "message": msg})

    bodies = _body_texts(doc)
    blob = "\n".join(bodies)
    blob_low = blob.lower()

    # N-headline: ≤10 kata, tesis forward (heuristic: ada koma/kata kerja, bukan statistik murni).
    hl = str(((doc.get("cover") or {}).get("headline")) or "")
    if not hl:
        v("N.headline", False, "headline kosong", True)
    else:
        wc = _words(hl)
        stat_like = bool(re.search(r"\d[,\.]\d+x\s+vs\b", hl) or re.search(r"\bmid-cycle\b", hl, re.I))
        v("N.headline", wc <= 10 and not stat_like,
          f"headline {wc} kata" + ("; statistik bukan tesis" if stat_like else ""), True)

    # N-para-headline ≤9 kata.
    for i, sec in enumerate((doc.get("cover") or {}).get("paragraf") or []):
        title = sec.get("judul") if isinstance(sec, dict) else ""
        if title and _words(title) > 9:
            v(f"N.parajudul.{i}", False, f"headline paragraf {i} >9 kata", True)
    if not any(c["check"].startswith("N.parajudul") and c["status"] == "gagal" for c in checks):
        v("N.parajudul", True, "headline paragraf ≤9 kata", False)

    # N-bullets: 3 x 1 kalimat ≤30 kata (draft legacy allows 3-4 as warning).
    bullets = (doc.get("cover") or {}).get("bullets") or []
    is_prod = str((doc.get("meta") or {}).get("status") or "") != "draft_non_distributable"
    if len(bullets) != 3:
        v("N.bullets", False, f"bullets halaman 1 harus 3, ada {len(bullets)}", is_prod,
          None if is_prod else "peringatan")
    else:
        bad = [i for i, b in enumerate(bullets) if _words(b) > 30 or len(_sentences(b)) > 1]
        v("N.bullets", not bad, "3 bullets 1 kalimat ≤30 kata" if not bad
          else f"bullet {bad} >30 kata/>1 kalimat", True)

    # N-style: no long dash, no emoji, no filler phrases.
    v("N.dash", not _LONG_DASH.search(blob), "nol tanda pisah panjang" if not _LONG_DASH.search(blob)
      else "ada em/en-dash; pakai koma/titik/hubung biasa", True)
    v("N.emoji", not _EMOJI.search(blob), "nol emoji" if not _EMOJI.search(blob)
      else "ada emoji", True)
    fill = [p for p in BANNED_PHRASE if p in blob_low]
    v("N.filler", not fill, "tanpa frasa filler" if not fill else f"frasa terlarang: {fill}", True)

    # N-pipeline terms in body (whole-word for log/engine to avoid false positives).
    pipe = [t for t in BANNED_BODY if t.lower() in blob_low]
    pipe += [pat for pat in BANNED_TOKENS if re.search(pat, blob_low)]
    v("N.pipeline", not pipe, "nol istilah pipeline di body" if not pipe
      else f"istilah pipeline di body: {pipe}", True)

    # N-internal strings anywhere in client PDF text (body + exhibit titles/rows, not log_gate).
    # Exhibit `catatan_sumber` provenance ("Sectors cache") is allowed in v1; only body
    # paragraphs + exhibit content rows are scanned for placeholders. `cache` in body
    # is a warning (paraphrase to "data lokal") until narrative templates are cleaned.
    ext_texts = []
    for e in _exhibits(doc):
        ext_texts.append(str(e.get("judul") or ""))
        d = e.get("data") or {}
        for r in (d.get("rows") or []):
            ext_texts.append(" ".join(str(c) for c in (r if isinstance(r, list) else [r])))
    exhib_blob = "\n".join(ext_texts).lower()
    pdf_hits = [t for t in BANNED_PDF if t in blob_low or t in exhib_blob]
    cache_in_body = "cache" in blob_low
    if cache_in_body and not any(a in blob_low for a in CACHE_ALLOW):
        v("N.cache_body", True, "kata 'cache' di narasi; parafrase jadi 'data lokal'",
          False, "peringatan")
    else:
        v("N.cache_body", True, "provenance cache ok / tanpa cache di body", False)
    # '$' untuk angka Rupiah: hanya $ telanjang yang bukan bagian "US$".
    # "US$2.052,0 juta" untuk model USD adalah sah; yang dilarang "$Rp" / "$ 5 miliar".
    if re.search(r"(?i)(?<!us)\$\s*\d", blob + "\n" + exhib_blob):
        pdf_hits.append("$ untuk angka Rupiah")
    v("N.internal", not pdf_hits, "nol string internal" if not pdf_hits
      else f"string internal: {sorted(set(pdf_hits))}", True)

    # N-period format.
    bad_period = _PERIOD_BAD.search(blob)
    v("N.periode", not bad_period,
      "format periode 1Q26/1H26/FY26" if not bad_period else f"format periode salah: {bad_period.group(0)}",
      True)

    # N-number density ≤3 per sentence.
    dense = []
    for t in bodies:
        for s in _sentences(t):
            if len(_NUMBER.findall(s)) > 3:
                dense.append(s[:80])
                break
    v("N.angka", not dense, "maks 3 angka/kalimat" if not dense
      else f"{len(dense)} paragraf >3 angka/kalimat", False, None if not dense else "peringatan")

    # N-exhibit: global sequential + source line.
    exs = _exhibits(doc)
    if exs:
        nums = []
        for e in exs:
            n = e.get("n")
            try:
                nums.append(int(n))
            except (TypeError, ValueError):
                nums.append(None)
        seq_ok = nums == list(range(1, len(exs) + 1))
        v("N.exhibit_nomor", seq_ok,
          "penomoran exhibit global berurutan" if seq_ok else f"penomoran {nums} tak berurutan", True)
        nosrc = [e.get("judul") or f"#{i+1}" for i, e in enumerate(exs)
                 if not str(e.get("catatan_sumber") or e.get("source") or "").strip()]
        v("N.exhibit_sumber", not nosrc, "semua exhibit ada source" if not nosrc
          else f"tanpa source: {nosrc[:3]}", True)
        # junk rows: all-placeholder rows must be dropped
        junk = 0
        for e in exs:
            for r in ((e.get("data") or {}).get("rows") or []):
                cells = r if isinstance(r, list) else [r]
                txts = [" ".join(str(c).split()).lower() for c in cells if isinstance(c, str)]
                if txts and all(t in ("", "-", "--", "n/a", "na", "tidak tersedia",
                                      "tanpa tanggal", "aksi korporasi tercatat", "tanpa judul")
                                for t in txts):
                    junk += 1
        v("N.baris_sampah", junk == 0, "nol baris sampah" if junk == 0
          else f"{junk} baris sampah; buang + fallback jujur", True)
    else:
        v("N.exhibit_nomor", True, "tanpa exhibit; dilabeli", False, "dilabeli")
        v("N.exhibit_sumber", True, "tanpa exhibit; dilabeli", False, "dilabeli")
        v("N.baris_sampah", True, "tanpa exhibit; dilabeli", False, "dilabeli")

    # N-TP consistency + extreme + downside are cross-checked in G3; re-assert presence.
    meta = doc.get("meta") or {}
    if meta.get("tp") is not None and meta.get("status") == "draft_non_distributable":
        v("N.tp_draft", False, "draft memuat TP; tahan sampai release lolos", True)
    else:
        v("N.tp_draft", True, "TP hanya saat production-ready", False)

    blockers = [f"{c['check']}: {c['message']}" for c in checks if c.get("blocker")]
    return {"tool": "check_narrative", "status": "lolos" if not blockers else "gagal",
            "checks": checks, "blockers": blockers}


def score_news(items: list[dict] | None) -> dict:
    """Validate §5.3 curation scores from LLM/agent. Each item needs 4 axes 0–3.

    Input item: {"id": str, "dampak": 0-3, "materialitas": 0-3, "durabilitas": 0-3,
                 "kebaruan": 0-3, "jenis": str (e.g. harga_harian/broker_flow/rebalance/insider/...)}
    Returns curated (total≥7, max 7) + dropped with reasons. Pure validator, not scorer.
    """
    items = items or []
    curated, dropped = [], []
    DISCARD_TYPES = {"harga_harian", "broker_flow_harian", "rebalance_tanpa_arus", "insider_kecil"}
    for it in items:
        iid = str(it.get("id") or "?")
        axes = [it.get(k) for k in ("dampak", "materialitas", "durabilitas", "kebaruan")]
        if any(not isinstance(a, int) or not 0 <= a <= 3 for a in axes):
            dropped.append({"id": iid, "reason": "skor 0–3 tiap sumbu wajib diisi LLM"})
            continue
        total = sum(axes)
        jenis = str(it.get("jenis") or "")
        if jenis in DISCARD_TYPES:
            dropped.append({"id": iid, "reason": f"jenis {jenis} dibuang per §5.3"})
            continue
        if it.get("insider_pct") is not None:
            try:
                if float(it["insider_pct"]) < 0.5:
                    dropped.append({"id": iid, "reason": "insider <0,5% dibuang"})
                    continue
            except (TypeError, ValueError):
                pass
        if total < 7:
            dropped.append({"id": iid, "reason": f"total {total}<7"})
        else:
            curated.append({"id": iid, "total": total, **it})
    curated.sort(key=lambda r: r["total"], reverse=True)
    kept, overflow = curated[:7], curated[7:]
    for r in overflow:
        dropped.append({"id": r["id"], "reason": "melebihi 7 item katalis"})
    return {"tool": "score_news", "curated": kept,
            "cover_max_3": [r["id"] for r in kept[:3]],
            "dropped": dropped}

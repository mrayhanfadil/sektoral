# Absorpsi Kritik GMFI-vs-AMMN — Implementation Plan

> **For Hermes:** implementasi per batch via AGY lane (scope sempit, owned-files eksplisit) atau langsung; orchestrator verifikasi independen tiap batch.

**Goal:** Menutup 8 poin kritik perbandingan GMFI vs AMMN yang valid — bug dulu, win murah kedua, struktural terakhir — tanpa mengubah arsitektur cache-only pipeline.

**Architecture:** Semua fix di `app/narrative.py` (teks/tabel) + `app/render.py` (chart/label) + `app/fmt.py` (format flag). Tidak ada file baru kecuali test. Tidak ada network, tidak ada LLM, tidak ada perubahan skema cache.

**Tech Stack:** Python stdlib + Playwright/Chromium (PDF), pytest, pdftotext/pdffonts/pdftoppm (verifikasi).

---

## Decision Log

| # | Keputusan | Kenapa | Alternatif ditolak | Risiko |
|---|-----------|--------|--------------------|--------|
| D1 | Terima seluruh kritik 1–8 sebagai valid | Poin 1–3 struktural & diakui metodologi sendiri; poin 4–5 bug nyata; 6–7 bisa diperbaiki murah; 8 benar (jangan ditiru) | Menyangkal / debat per poin — kalah kredibilitas, kritiknya akurat | Scope creep ke "riset setara analis manusia" — dibatasi eksplisit di D5 |
| D2 | Urutan: bug (A) → win murah (B) → label jujur (C) → struktural (D, butuh keputusan lo) | Bug (teks internal bocor, baris sampah, label $) itu malu aktif; tiap hari tayang = tiap hari malu | Kerjakan D (NAV tambang) dulu — mahal, butuh data yang tidak ada di cache, blokir semua | Batch A+B selesai tanpa input lo; D tidak jalan tanpa data cadangan |
| D3 | Peer absurd di-flag, tidak di-drop | Drop = sembunyi data; flag "n.m." + footnote = jujur + informatif | Winsorize diam-diam — melanggar disiplin no-silent-fallback | Tabel peer tetap jelek untuk sektor rugi massal; diterima |
| D4 | Risiko ditulis dari angka sensitivitas yang sudah ada | Data sudah dihitung (grid TP, sensitivitas EBITDA) — narasi doang, nol risiko model | Ambil risiko dari berita (scraper) — tidak berdasar, nambah noise | Paragraf tetap generik untuk risiko non-kuantitatif (regulasi, force majeure) |
| D5 | Positioning = "snapshot otomatis", bukan "inisiasi" | Satu-satunya klaim yang bisa dipertahankan kode + cache-nya; byline analis berlisensi tidak boleh ditiru (impersonasi) | Rebrand jadi "riset institusional" — bohong; pasang nama analis fiktif — pelanggaran | Produk terlihat "lebih kecil" — tapi jujur dan bisa dipertahankan |
| D6 | Chart diperbaiki minimal (label + caption), tidak dibangun ulang | Overlay IHSG tidak bisa (window beda periode, fakta cache); chart deck GMFI placeholder juga | Tambah matplotlib/seaborn — dependensi baru untuk nilai kecil; SVG sekarang cukup | Chart tetap sederhana vs GMFI — diterima sebagai batas snapshot |

---

## Batch A — Bug (malu aktif, fix hari ini)

### Task A1: Hapus teks internal "kurasi skor" yang bocor ke PDF

**Objective:** Kolom Katalis tidak lagi memuat string debug scorer.

**Files:**
- Modify: `app/narrative.py:356-358` (loop `scored[:5]`, string `f"kurasi skor {s}/9 ..."`)
- Test: `tests/test_pipeline.py` (tambah 1 assert)

**Step 1: Tulis test gagal**

```python
def test_katalis_no_internal_text():
    from app import narrative
    doc = narrative.build(_sample_doc_inputs())  # atau via build AMMN bila fixture ada
    kat = next(e for e in doc["exhibits"] if e["judul"].endswith("Katalis"))
    blob = " ".join(" ".join(r) for r in kat["data"]["rows"])
    assert "kurasi skor" not in blob
    assert "sebelum masuk model" not in blob
```

(Sesuaikan constructor dengan helper yang sudah ada di `test_pipeline.py` — baca dulu 51 barisnya.)

**Step 2: Run —** `pytest tests/test_pipeline.py::test_katalis_no_internal_text -v` → Expected: FAIL (`kurasi skor` masih ada).

**Step 3: Implementasi minimal** — ganti isi kolom ketiga dengan kurasi layperson dari data yang sudah ada (skor → kata, bukan angka):

```python
for s, title, ts, src in scored[:5]:
    kait = "kandidat penggerak utama" if s >= 2 else "konteks pemberitaan"
    rows.append([title, ts, f"{kait} ({src})", "Netral"])
```

**Step 4: Run —** `pytest tests/ -q` → Expected: semua pass (sekarang 4, sesudah A-batch bertambah).

**Step 5: Verifikasi PDF —** `python3 -m app.build AMMN --out out --pdf && pdftotext -layout out/AMMN.pdf - | grep -c "kurasi skor"` → Expected: `0`.

**Step 6: Commit —** `git add app/narrative.py tests/test_pipeline.py && git commit -m "fix(report): kurasi katalis tanpa teks internal scorer"`.

### Task A2: Buang baris sampah "aksi korporasi | tanpa tanggal"

**Objective:** Fallback corp-action yang tidak memberi info tidak dirender.

**Files:**
- Modify: `app/narrative.py:351-364` (`_katalis`, baris `ts ... or "tanpa tanggal"` + `rows.append([act, ts, "aksi korporasi tercatat", ...])`)

**Step 1: Test gagal**

```python
def test_katalis_no_empty_corp_row():
    # ... ambil tabel Katalis seperti A1 ...
    for r in kat["data"]["rows"]:
        assert not (r[1] == "tanpa tanggal" and r[2] == "aksi korporasi tercatat")
```

**Step 2: Run → FAIL. Step 3: Implementasi —** lewati entri corp-action tanpa tanggal DAN tanpa aksi bermakna; kalau habis semua, biarkan fallback jujur yang sudah ada (`"Belum ada katalis terkurasi dari cache"`):

```python
for c in (intake["corp_actions"] or [])[:2]:
    if not isinstance(c, dict):
        continue
    act_raw = str(c.get("action") or c.get("type") or "").strip()
    ts_raw = str(c.get("date") or "")[:10]
    if not act_raw or not ts_raw:
        continue
    rows.append([_word_cut(act_raw, 64), ts_raw, "aksi korporasi tercatat", "Netral"])
```

**Step 4: `pytest tests/ -q` → pass. Step 5: PDF —** `pdftotext -layout out/AMMN.pdf - | grep -c "tanpa tanggal"` → `0`. **Step 6: Commit.**

### Task A3: Perbaiki label sumbu chart harga (simbol `$`, tanggal mentah)

**Objective:** Tidak ada simbol mata uang asing; tanggal ringkas; caption jujur tetap ada.

**Files:**
- Modify: `app/render.py:91-99` (`_price_chart`: `f"{hi:,.0f}"`, `{dates[0]}`, `{dates[-1]}`, caption IHSG)

**Step 1: Reproduksi —** `pdftotext -layout -f 1 -l 1 out/AMMN.pdf - | grep -E "\\$|2025-09-12"` → catat temuan (sumber keluhan: `$175`, tanggal full ISO).

**Step 2: Implementasi —** label atas `Rp{hi:,.0f}` → format Indonesia via `fmt` (titik ribuan, tanpa `$`); tanggal `YYYY-MM-DD` → `DD Mon YY` (`12 Sep 25`); caption IHSG dipertahankan (jujur, sudah benar).

**Step 3: Rebuild + cek —** `python3 -m app.build AMMN --out out --pdf && pdftotext -layout -f 1 -l 1 out/AMMN.pdf - | grep -c "\\$"` → `0`. **Step 4: Screenshot cover** (`pdftoppm -png -r 55 -f 1 -l 1`) + cold-read manual: label terbaca, tidak overlap. **Step 5: Commit.**

### Task A4: Flag multiple peer absurd (MDKA 9141x, EMAS negatif)

**Objective:** PER/PBV tidak bermakna ditampilkan sebagai `n.m.` + footnote, bukan angka mentah.

**Files:**
- Modify: `app/narrative.py:246-249` (tabel Peer) + `app/fmt.py` (tambah `mult_flag` bila belum ada)
- Test: `tests/test_pipeline.py` (+1 assert: tidak ada `9.141` mentah / tidak ada PER negatif di render)

**Step 1: Test gagal** — render tabel Peer dari intake AMMN, assert tidak ada sel PER dengan `abs(pe) > 200` tampil sebagai angka.

**Step 2: Implementasi —**

```python
def _peer_cell(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "-"
    if f <= 0 or f > 200:
        return "n.m."
    return fmt.mult(f)
```

Pakai di kedua kolom PER TTM dan PBV; tambah `catatan_sumber` tabel: `"n.m. = tidak bermakna (rugi atau >200x). Source: ..."`.

**Step 3: `pytest tests/ -q` → pass. Step 4: PDF —** `pdftotext -layout out/AMMN.pdf - | grep -E "9\.141|-368"` → `0`; ada string `n.m.`. **Step 5: Commit.**

---

## Batch B — Win murah (data sudah ada, tinggal narasi)

### Task B1: Paragraf risiko dari angka sensitivitas (bukan satu kalimat)

**Objective:** Bagian "Katalis, risiko, kepemilikan" punya 3–4 kalimat risiko terukur dari grid yang sudah dihitung.

**Files:**
- Modify: `app/narrative.py:268-270` (paragraf risiko; input `va["tp_grid"]`, sensitivitas EBITDA, `fc` sudah tersedia di scope `build`)

**Step 1: Tulis dulu contoh output yang diharapkan** (manual, dari `out/AMMN.json` saat ini): rentang TP grid (min–maks), driver sensitivitas EBITDA terbesar. Catat angkanya.

**Step 2: Implementasi —** template deterministik, contoh pola (sesuaikan variabel nyata):

```python
r3 = (f"risiko utama: (1) harga komoditas — skenario WACC/g di grid TP "
      f"membentang Rp{rendah}–Rp{tinggi}; (2) eksekusi belanja modal ...; "
      f"(3) leverage ... Utang bersih Rp{...}.")
```

Semua angka dari `va`/`fc`, nol konstanta baru.

**Step 3: Verifikasi —** rebuild, `pdftotext` halaman risiko ≥ 3 kalimat, setiap angka di paragraf ada pasangannya di exhibit (cek manual 5 menit). **Step 4: `pytest` + commit.**

### Task B2: Forward multiple untuk emiten yang di-cover (kolom FY26F di tabel Peer)

**Objective:** Tabel Peer punya kolom `EV/EBITDA FY26F*` minimal untuk baris emiten; peer tanpa forecast = `-`.

**Files:**
- Modify: `app/narrative.py:246-249` (+1 kolom, EV dari `va`, EBITDA FY26F dari `fc["rows"][0]`)

**Step 1: Hitung manual** dari `out/AMMN.json` (EV ÷ EBITDA FY26F) sebagai oracle.

**Step 2: Implementasi + footnote** `"*Hanya emiten yang di-cover; peer = data cache TTM."`.

**Step 3: Rebuild, cek kolom muncul, `pytest` + commit.**

### Task B3: Label jujur "snapshot otomatis" di cover

**Objective:** Cover menyatakan positioning D5 dalam 1 baris, bahasa awam.

**Files:**
- Modify: `app/render.py:208` (blok `Analis Sektoral<br>Tim Riset Sektoral`) — tambah 1 baris kecil: `Snapshot otomatis dari data cache — bukan riset inisiasi penuh`.

**Step 1–3: Edit → rebuild → screenshot cover cold-read → commit.** (Tanpa test baru; string statis.)

---

## Batch C — Struktural (TIDAK jalan tanpa keputusan Fadil)

- **C1 — Overlay komoditas tambang:** asumsi harga Cu/Au berlabel (sumber + tanggal) masuk `forecast.py` sebagai driver eksplisit. Butuh: sumber harga yang disepakati (Sectors? manual input per kuartal?).
- **C2 — NAV LoM untuk emiten tambang:** ganti Gordon+exit dengan DCF hingga akhir umur cadangan. Butuh: umur cadangan + profil produksi — TIDAK ada di cache hari ini. Opsi: input manual per emiten (`data/drivers/<TICKER>.json`) atau terima TP absurd sebagai "proksi disclosed".
- **C3 — Perincian NWC/COGS:** tarik piutang/persediaan dari historis financials bila ada di cache; kalau tidak ada, tetap disclose ringkas. Butuh: audit field `financials/*` di `sectors_cache.db` dulu (1 query).
- **C4 — Byline/kontak analis:** TIDAK direkomendasikan (D5). Kalau produk butuh kredibilitas institusional, itu urusan lisensi/organisasi, bukan kode.

---

## Verifikasi akhir (orchestrator, tiap batch)

1. `python3 -m pytest tests/ -q` — semua pass, jumlah test naik (4 → ≥7).
2. `python3 -m app.build AMMN --out out --pdf` — gates G1/G2/G3 OK.
3. `pdftotext` asserts: `kurasi skor`=0, `tanpa tanggal`=0, `$`=0 (hal.1), `9.141`/`-368`=0, ada `n.m.`.
4. `pdffonts` masih Poppins; `pdfinfo` 7 halaman (boleh ±1 bila konten B bertambah).
5. Cold-read 2 screenshot (cover + hal. risiko) via AGY-vision; nol overlap/teks terpotong.
6. `git add` hanya `app/*` + `tests/*` + plan ini; push `main`.

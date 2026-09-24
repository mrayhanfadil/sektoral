# Self review e2e sembilan emiten — 25 September 2026

## Cakupan

Riset end-to-end dijalankan untuk AMMN, BBCA, BBRI, GMFI, INET, JPFA, POWR, SIDO dan SSIA (`python -m app.batch ... --jobs 2 --as-of 2026-09-24 --pdf`), lalu setiap laporan dibaca pada cover, Key Financials, skenario laba FY26F dan tahun lanjutan, tabel valuasi, rantai metode, tabel peer, band historis serta laporan keuangan (laba rugi, neraca, arus kas, rasio). Fokusnya angka yang aneh, angka yang tidak saling cocok antar-tabel, dan kolom forecast.

| Emiten | Status | Rating | Target | Harga | Potensi | Metode |
|---|---|---|---|---|---|---|
| AMMN | assumption-led | Sell | Rp3.140 | Rp4.870 | −35,5% | SOTP/LoM |
| BBCA | draft | – | – | Rp6.300 | – | ditahan: skenario forecast belum tervalidasi |
| BBRI | assumption-led | Buy | Rp5.625 | Rp3.180 | +76,9% | DDM skenario FY26F–FY30F |
| GMFI | assumption-led | Buy | Rp111 | Rp56 | +98,2% | DCF FCFF skenario |
| INET | assumption-led | Sell | Rp250 | Rp316 | −20,9% | EV/EBITDA peer FY26F |
| JPFA | assumption-led | Sell | Rp1.275 | Rp2.230 | −42,8% | DCF FCFF skenario |
| POWR | assumption-led | Buy | Rp1.870 | Rp980 | +90,8% | DCF FCFF skenario |
| SIDO | draft | – | – | Rp352 | – | ditahan: rilis interim belum tervalidasi |
| SSIA | assumption-led | Sell | Rp1.235 | Rp1.600 | −22,8% | SOTP holding |

## Cacat yang diperbaiki

Semua ditemukan pada run pertama dan diuji ulang dengan pemeriksa otomatis pada run sesudah perbaikan (lihat "Verifikasi").

1. **Satuan tercampur di Key Financials (POWR).** Kolom 2024–2025 berisi nilai rupiah (8.838.196,9) di bawah label "US$ juta", di samping FY26F 577,0 dalam dolar. Fallback sejarah Sectors kini selalu dalam Rp miliar; kolom skenario USD dikonversi dengan kurs yang sama dengan DCF.
2. **Kolom FY26F kosong di tabel keuangan (AMMN).** Laba bersih FY26F tertulis NA di laba rugi dan rasio, padahal FY27F–FY28F terisi dan Key Financials menulis US$1.144 juta. Skenario interim tambang tidak memisahkan porsi induk; tabel kini memakai laba bersih yang sama dengan Key Financials.
3. **EBITDA forecast tidak konsisten antar-tabel (SSIA).** Key Financials menulis FY26F NA tetapi FY27F terisi, sementara laba rugi menulis FY26F Rp1.370 miliar. Aturannya kini satu: EBITDA skenario tampil di semua tabel bila skenario memuatnya.
4. **Catatan sumber bertentangan dengan isinya.** Key Financials BBRI, INET, JPFA, POWR dan SSIA menyatakan "kolom forecast belum tersedia (NA)" padahal kolom forecast terisi; INET juga menulis "EBITDA tidak dimodelkan" tepat di bawah EBITDA FY26F. Kalimat itu kini dihapus saat skenario mengisi kolom.
5. **Draft membocorkan nilai wajar (BBCA).** Laporan draft menahan target, tetapi memuat "DDM Gordon memberi Rp4.980/saham" dan dua grid sensitivitas bertanda basis. Draft (tanpa `--illustrative-scenarios`) kini tidak mencetak nilai screening itu.
6. **Dua nilai DDM yang bertentangan (BBRI).** Target Rp5.625 dari DDM skenario berdampingan dengan grid DDM screening berbasis Rp3.270. Grid screening dihapus bila DDM skenario menjadi dasar target.
7. **Multiple tanpa makna dicetak sebagai angka.** P/E 9.141,7x (MDKA), 5.322,5x (INET 2024), P/B 793,8x (RONY), band P/E INET rata-rata 1.702,1x dengan "harga implisit" Rp4.350. Multiple di atas 100x kini ditulis n.m., dan harga implisitnya tidak dihitung.
8. **Rata-rata peer rusak oleh satu pencilan.** Margin bersih rata-rata peer AMMN −2.306,2%, ROE rata-rata peer SSIA −78,6%, POWR −46,8%. Rasio yang oleh tabel sendiri ditandai n.m. (di atas 500%) kini tidak masuk rata-rata.
9. **Perubahan yoy di atas 500% (AMMN 1.211,6%, SSIA 553,3%).** Tabel interim kini mengikuti aturan laporan sendiri: n.m.
10. **Format:** "-0" pada arus kas (AMMN, GMFI, INET, POWR, SIDO) dan "2,43xx" (BBCA, BBRI).
11. **Label target salah (SSIA).** Tabel "Target harga: PER peer x EPS FY26F" dengan "Median (basis)" Rp825, padahal target berasal dari SOTP Rp1.235. Di bawah target SOTP, tabel itu kini berjudul "Silang cek".
12. **Kalimat bahasa Inggris di laporan berbahasa Indonesia** pada rantai metode AMMN ("8x is an analyst assumption…") dan JPFA ("fixed assets below half of total assets…").

## Temuan yang perlu keputusan analis

Ini bukan cacat tampilan; angka-angkanya keluar dari model sebagaimana dirancang, tetapi layak diperiksa sebelum laporan dipakai.

1. **JPFA — DCF jauh di bawah silang cek.** Target Rp1.275 (Sell −42,8%) sementara PER FY skenario Rp2.390 dan band P/E historis Rp2.700. Exit EV/EBITDA tersirat dari Gordon hanya 3,3x terhadap sejarah 6–9x (selisih 49,8% sudah diungkapkan). Penyebabnya adalah data D&A yang salah (lihat "Validasi eksternal": penyusutan audit Rp1.265 miliar, bukan Rp325 miliar), bukan capex atau modal kerja seperti dugaan awal versi ini.
2. **GMFI — upside +98,2% tepat di bawah ambang Review Required (+100%).** Target DCF Rp111 berbanding silang cek PER Rp34 dan P/BV Rp24. Grup peer "Airport Operators" dari Sectors memuat BREN (energi terbarukan), META dan KARW, sehingga median dan peringkat peer kurang bermakna. Data Sectors juga mencatat EBITDA di bawah EBIT (2024: 727 vs 767; 2025: 1.019 vs 1.176).
3. **BBRI — Buy +76,9%** dengan porsi terminal 72,7% dari nilai DDM; silang cek PER FY Rp3.130 dan P/BV-ROE Rp4.510. Pendapatan FY26F Rp215,8 triliun adalah 2 x pendapatan interim 1H26, sedangkan pendapatan tahunan Sectors 2025 Rp181,3 triliun memakai definisi lain; pertumbuhan tersirat +19% itu artefak definisi, bukan asumsi. Neraca interim BBRI dan JPFA hanya terisi jumlah saham.
4. **POWR — Buy +90,8%.** Gordon menyiratkan exit 8,0x terhadap sejarah 3,7–7,2x (selisih 36,6% diungkapkan); P/BV silang cek Rp960. Peer "Electric Utilities" berisi BREN, CDIA dan ARKO dengan P/E di atas 60x sehingga PER relatif tidak dapat dipakai.
5. **AMMN — dua pendapatan 2H26:** jadwal LoM Rp3.202 juta dolar (panduan produksi) berbanding skenario interim 2.667,6. Dua "P/E kini" juga berbeda: 38,6x di tabel peer (TTM Sectors) dan 84,6x di band historis (laba tahunan terbit).
6. **SIDO — draft karena rilis interim tidak tervalidasi.** Penyebabnya disengaja: paket `data/issuer_evidence/SIDO.json` berstatus `blocked` karena laporannya berasal dari cermin Indo Premier dan tanggal terbitnya belum diverifikasi dari sumber primer (IDX). Angkanya sendiri cocok dengan jumlah kuartal Yahoo dan pemberitaan (lihat "Validasi eksternal").
7. **Kualitas grup peer Sectors** menjadi masalah berulang (GMFI, POWR, JPFA dengan RLCO/AYAM, SSIA dengan RONY). Pilihan: menyaring peer dengan multiple di luar rentang sebelum median, bukan hanya menandai n.m.

## Verifikasi

Pemeriksa otomatis membaca dokumen laporan dan menguji setiap cacat di atas (satuan Key Financials, kolom FY26F, catatan yang bertentangan, EBITDA antar-tabel, "-0", "xx", multiple di atas 100x, kalimat bahasa Inggris, nilai screening di draft, grid DDM ganda, label target SOTP, rata-rata peer).

| Run | Laporan dengan cacat |
|---|---|
| Sebelum perbaikan (`out/e2e-2026-09-24/all9`, JSON per file) | 9 dari 9 |
| Sesudah perbaikan (`out/e2e-2026-09-25/all9-fixed`, dokumen di basis data aplikasi) | 0 dari 9 |

Rating dan target kesembilan emiten sama persis pada kedua run: perbaikan ini mengubah penyajian dan konsistensi, bukan valuasi. Rencana forecast tersimpan dipakai ulang karena buktinya tidak berubah. Run sesudah perbaikan juga tidak menulis satu pun file JSON ke folder output; laporan, jejak dan manifest tersimpan di `data/sectoral.db`.

## Validasi eksternal (25 September 2026)

Setiap temuan di atas diuji ulang dengan sumber di luar pipeline: harga penutupan dan laporan keuangan Yahoo Finance (yfinance), laporan keuangan audit emiten, harga komoditas, dan konsensus analis dari pemberitaan. Ringkasnya: angka input harga dan interim benar, tetapi dua kesalahan data mengubah arah rating (JPFA dan AMMN), dan beberapa target berada jauh di luar konsensus.

### Yang terkonfirmasi

- **Harga penutupan** kesembilan laporan sama persis dengan Yahoo pada tanggal harga masing-masing. Catatan: laporan bertanggal 24 September memakai penutupan 22–23 September; SSIA memakai Rp1.600 dari hari turun tajam (23 Sep Rp1.715, 24 Sep Rp1.750), sehingga Sell −22,8% bergantung pada satu hari perdagangan.
- **Angka interim 1H26** AMMN, JPFA, SSIA, SIDO dan INET cocok dengan jumlah dua kuartal Yahoo atau rilis yang diberitakan (INET: pendapatan Rp926,45 miliar, laba induk Rp33,67 miliar; SIDO: penjualan −19,8% dan laba −44,4% yoy karena normalisasi stok distributor Tolak Angin).
- **BBRI:** pendapatan FY26F Rp215,8 triliun memang artefak definisi. Dengan basis Yahoo yang konsisten, pendapatan 1H26 Rp98,3 triliun, bukan Rp107,9 triliun.
- **GMFI:** Yahoo juga mencatat EBITDA sama dengan EBIT (tanpa D&A), jadi keanehan EBITDA di bawah EBIT berasal dari agregator data, bukan dari model. BREN memang ada di tabel peer Sectors untuk GMFI dan POWR.
- **Kurs** tersimpan Rp17.878 bertanggal 23 September; penutupan Yahoo pada tanggal itu Rp17.805 (selisih 0,4%, tidak material).

### Kesalahan data yang mengubah rating

1. **JPFA: D&A Sectors salah sekitar empat kali lipat.** Laporan keuangan audit 2025 (catatan segmen) mencatat penyusutan Rp1.265 miliar (2024: Rp1.165 miliar), sedangkan Sectors dan Yahoo sama-sama hanya sekitar Rp325 miliar. Umur aset sebenarnya sekitar 15 tahun, bukan 50. Karena EBITDA Sectors juga kehilangan penyusutan itu, margin EBITDA skenario (11%, menuju "rata-rata historis ~9%") ikut terlalu rendah sekitar 1,5 pp. Nilai DCF dihitung ulang dengan rencana forecast yang sama:

   | Kasus | Nilai per saham | Terhadap Rp2.230 |
   |---|---|---|
   | Seperti laporan (D&A Sectors) | Rp1.277 | −43% |
   | D&A audit saja (2,1% pendapatan) | Rp1.718 | −23% |
   | D&A audit dan margin EBITDA +1,5 pp | Rp2.911 | +31% |

   Konsensus 11 analis Rp2.800–3.750 (Indo Premier Buy, Rp3.400). Rating Sell JPFA adalah artefak data dan tidak boleh didistribusikan.

2. **AMMN: dek harga tembaga basi tujuh bulan.** Seri `/mining/commodities/Copper/price/` di cache Sectors berhenti pada 15 Februari 2026 (seri emas mutakhir sampai September), sehingga "rata-rata 12 bulan" US$11.122/t sebenarnya rata-rata Februari 2025–Februari 2026. LME copper sekitar US$14.800/t pada 22 September 2026 dengan rata-rata 2026 sekitar US$13.400/t, dan harga realisasi katoda AMMN sendiri pada 1H26 US$13.625/t. SOTP/LoM dihitung ulang dengan asumsi lain tetap:

   | Dek tembaga | Nilai per saham | Terhadap Rp4.870 |
   |---|---|---|
   | US$11.122/t (laporan) | Rp3.155 | −35% |
   | US$13.383/t (rata-rata 2026) | Rp3.881 | −20% |
   | US$14.797/t (spot 22 Sep) | Rp4.335 | −11% |

   Terhadap penutupan 24 September Rp4.730, dek spot memberi −8% (Hold). Konsensus: 15 dari 16 analis Buy, rata-rata target Rp6.829 (Mandiri Rp7.100, KB Valbury Rp6.500, BRI Danareksa Rp6.000); selisih sisanya terutama dari diskon risiko Elang 50% dan dek harga. Pipeline perlu cek kesegaran seri komoditas sebelum dipakai sebagai dek.

### Target di luar konsensus yang perlu ditinjau

- **BBRI Buy Rp5.625** lebih tinggi dari target tertinggi 22 analis (Rp4.900; rata-rata Rp3.692–4.250). Payout justru konservatif: BBRI membagikan sekitar 92% laba FY2025 (DPS Rp346), sedangkan model memakai 83,2% dan DPS FY26F Rp342 berada di bawah DPS aktual tahun lalu. Kelebihan nilai berasal dari CoE 10,9% dan g 3,5% (porsi terminal 72,7%), bukan dari payout.
- **POWR Buy Rp1.870** sekitar dua kali target yang dipublikasikan (sekitar Rp804–872, satu analis). Jembatan EV ke ekuitas memakai kas Sectors akhir 2025 (Rp5.176 miliar), padahal neraca resmi 30 Juni 2026 mencatat kas US$124 juta (sekitar Rp2,2 triliun) dan utang US$344,6 juta; memakai neraca interim menurunkan nilai sekitar Rp210 per saham. Tabel neraca interim POWR juga menulis pinjaman "-", celah ekstraksi yang sama dengan BBRI dan JPFA.
- **INET Sell Rp250** berlawanan dengan dua analis Buy (rata-rata Rp585). Kelipatan peer dari snapshot Yahoo berbeda jauh dari data Yahoo terkini (LINK 14,4x vs 5,4x, DATA 16,9x vs 11,2x, SUPR 45,0x vs 33,2x); median terkini sekitar 8,7x, bukan 13,8x, yang justru menurunkan nilai ke sekitar Rp205. Basis EBITDA FY26F (margin 10,5% sesudah konsolidasi) dan kualitas grup peer lebih menentukan daripada angka median.
- **SSIA Sell Rp1.235** berlawanan dengan konsensus Buy (Rp2.080–2.579; RHB Rp2.200). SOTP menilai lahan industri pada biaya perolehan, sehingga secara konstruksi di bawah nilai pasar; ditambah harga Rp1.600 dari hari turun tajam.
- **GMFI Buy Rp111** berada di antara dua target yang ditemukan (Rp98 dan Rp150, masing-masing satu analis), jadi tidak janggal terhadap konsensus; risikonya tetap upside yang berada tepat di bawah ambang Review Required.

### Koreksi atas versi awal dokumen ini

- Penyebab DCF JPFA yang rendah adalah D&A, bukan capex dan modal kerja.
- Pertanyaan SIDO sudah terjawab: paket bukti sengaja diblokir karena sumbernya cermin broker.
- Celah neraca interim juga terjadi pada POWR, tidak hanya BBRI dan JPFA.
- Dek tembaga AMMN yang basi tidak tertangkap pada review awal.

### Sumber

- Harga, laporan keuangan dan kurs: Yahoo Finance melalui yfinance (ticker `.JK`, `IDR=X`, `GC=F`, `HG=F`), diambil 25 September 2026.
- [Laporan keuangan audit JPFA 31 Desember 2025](https://d1be5sn7lppxuh.cloudfront.net/assets/files/files/financial_report/01-2026/pt-japfa-tbk-cfs-as-of-31-december-2025-audited.pdf)
- [Harga tembaga LME (Westmetall)](https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Cu_cash), [Trading Economics](https://tradingeconomics.com/commodity/copper), [Discovery Alert, September 2026](https://discoveryalert.com/news/copper-price-lme-stocks-september-2026/)
- [Dividen BBRI tahun buku 2025 (Investortrust)](https://investortrust.id/market/99658/bbri-tebar-dividen-rp-52-1-triliun-rasio-dinaikkan), [Receh.in](https://www.receh.in/2026/04/dividen-bri-bbri-2025-payout-ratio.html)
- Konsensus: [AMMN (Investortrust)](https://investortrust.id/market/117045/kinerja-amman-ammn-melejit-analis-pasang-target-harga-hingga-level-ini), [AMMN (KabarBursa)](https://www.kabarbursa.com/market-hari-ini/penjualan-dan-laba-meroket-di-semester-i-2026-begini-proyeksi-dan-target-saham-ammn), [BBRI (Investing.com)](https://www.investing.com/equities/bank-rakyat-in-consensus-estimates), [JPFA (TradingView)](https://id.tradingview.com/symbols/IDX-JPFA/forecast-price-target/), [JPFA (Sumbarbisnis)](https://sumbarbisnis.com/saham-jpfa-diprediksi-pulih-indo-premier-rekomendasikan-beli/), [POWR (TradingView)](https://id.tradingview.com/symbols/IDX-POWR/forecast/), [INET (Investing.com)](https://www.investing.com/equities/sinergi-inti-andalan-prima-tbk-pt-consensus-estimates), [SSIA (Infonasional)](https://www.infonasional.com/rhb-sekuritas-target-saham-ssia), [GMFI (TradingView)](https://www.tradingview.com/symbols/IDX-GMFI/forecast/)
- Interim: [INET 1H26 (Kompas)](https://money.kompas.com/read/2026/09/14/142058826/inet-bukukan-pendapatan-neto-rp-926-miliar-laba-bersih-rp-34-miliar), [SIDO 1H26 (IDX Channel)](https://www.idxchannel.com/market-news/penjualan-jamu-dan-suplemen-lesu-laba-sidomuncul-sido-turun-44-persen), [SIDO (Warta Ekonomi)](https://wartaekonomi.co.id/read633627/penjualan-sido-turun-20-jadi-rp147-triliun-tolak-angin-jadi-andalan-pemulihan)

Konsensus dan pemberitaan dipakai sebagai pembanding, bukan kebenaran: perbedaan dengan konsensus adalah sinyal untuk memeriksa, dan hanya kesalahan data yang terbukti (JPFA, AMMN, jembatan POWR) yang dinyatakan sebagai cacat.


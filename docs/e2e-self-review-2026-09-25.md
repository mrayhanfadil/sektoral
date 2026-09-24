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

1. **JPFA — DCF jauh di bawah silang cek.** Target Rp1.275 (Sell −42,8%) sementara PER FY skenario Rp2.390 dan band P/E historis Rp2.700. Exit EV/EBITDA tersirat dari Gordon hanya 3,3x terhadap sejarah 6–9x (selisih 49,8% sudah diungkapkan). Penyebab utama: capex 4,5% pendapatan dan kenaikan modal kerja 18% dari tambahan pendapatan menekan FCFF menjadi sekitar 20% EBITDA. D&A juga tidak masuk akal: EBITDA Sectors 2025 hanya Rp375 miliar di atas EBIT untuk aset tetap Rp18,7 triliun (umur aset tersirat sekitar 50 tahun), sehingga perisai pajak penyusutan terlalu kecil. Pilihan: menerima DCF, atau menambah cek struktural (umur aset tersirat lebih dari 40 tahun membuat DCF tidak memadai), yang akan memindahkan rantai ke PER FY skenario.
2. **GMFI — upside +98,2% tepat di bawah ambang Review Required (+100%).** Target DCF Rp111 berbanding silang cek PER Rp34 dan P/BV Rp24. Grup peer "Airport Operators" dari Sectors memuat BREN (energi terbarukan), META dan KARW, sehingga median dan peringkat peer kurang bermakna. Data Sectors juga mencatat EBITDA di bawah EBIT (2024: 727 vs 767; 2025: 1.019 vs 1.176).
3. **BBRI — Buy +76,9%** dengan porsi terminal 72,7% dari nilai DDM; silang cek PER FY Rp3.130 dan P/BV-ROE Rp4.510. Pendapatan FY26F Rp215,8 triliun adalah 2 x pendapatan interim 1H26, sedangkan pendapatan tahunan Sectors 2025 Rp181,3 triliun memakai definisi lain; pertumbuhan tersirat +19% itu artefak definisi, bukan asumsi. Neraca interim BBRI dan JPFA hanya terisi jumlah saham.
4. **POWR — Buy +90,8%.** Gordon menyiratkan exit 8,0x terhadap sejarah 3,7–7,2x (selisih 36,6% diungkapkan); P/BV silang cek Rp960. Peer "Electric Utilities" berisi BREN, CDIA dan ARKO dengan P/E di atas 60x sehingga PER relatif tidak dapat dipakai.
5. **AMMN — dua pendapatan 2H26:** jadwal LoM Rp3.202 juta dolar (panduan produksi) berbanding skenario interim 2.667,6. Dua "P/E kini" juga berbeda: 38,6x di tabel peer (TTM Sectors) dan 84,6x di band historis (laba tahunan terbit).
6. **SIDO — draft karena rilis interim tidak tervalidasi**, padahal `data/issuer_evidence/SIDO.json` ada; perlu diperiksa mengapa paket itu tidak lolos gate S1.
7. **Kualitas grup peer Sectors** menjadi masalah berulang (GMFI, POWR, JPFA dengan RLCO/AYAM, SSIA dengan RONY). Pilihan: menyaring peer dengan multiple di luar rentang sebelum median, bukan hanya menandai n.m.

## Verifikasi

Pemeriksa otomatis membaca dokumen laporan dan menguji setiap cacat di atas (satuan Key Financials, kolom FY26F, catatan yang bertentangan, EBITDA antar-tabel, "-0", "xx", multiple di atas 100x, kalimat bahasa Inggris, nilai screening di draft, grid DDM ganda, label target SOTP, rata-rata peer).

| Run | Laporan dengan cacat |
|---|---|
| Sebelum perbaikan (`out/e2e-2026-09-24/all9`, JSON per file) | 9 dari 9 |
| Sesudah perbaikan (`out/e2e-2026-09-25/all9-fixed`, dokumen di basis data aplikasi) | 0 dari 9 |

Rating dan target kesembilan emiten sama persis pada kedua run: perbaikan ini mengubah penyajian dan konsistensi, bukan valuasi. Rencana forecast tersimpan dipakai ulang karena buktinya tidak berubah. Run sesudah perbaikan juga tidak menulis satu pun file JSON ke folder output; laporan, jejak dan manifest tersimpan di `data/sectoral.db`.

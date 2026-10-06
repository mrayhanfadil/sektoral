# Benchmark terhadap riset broker: GMFI, BBCA, SIDO (lanjutan e2e 25 September 2026)

Lanjutan dari `docs/e2e-self-review-2026-09-25.md` (benchmark AMMN ada di sana). Target Sectoral di sini adalah hasil rebuild sesudah rencana perbaikan 1.1 (batas modal bank), 1.2, 2.1 dan 3.2 (POWR US$), tanggal laporan 24 September 2026. Setiap selisih digolongkan sebagai **data** (angka sumber salah atau berbeda), **metodologi** (cara menilai berbeda) atau **asumsi** (input berbeda pada metode yang sama). Aturan rencana: setiap selisih di atas 20% target harus dijelaskan atau diperbaiki.

## Ringkasan

| Emiten | Sectoral | Pembanding | Selisih terhadap pembanding | Penyebab utama | Golongan |
|---|---|---|---|---|---|
| GMFI | Buy Rp103 | BRI Danareksa (Kompas Saham), Buy Rp88, 24 Sep 2026 | +17% | g 3,0% vs 2,5%, WACC 9,3% vs 9,6%, terminal Gordon penuh vs campuran 50/50 dengan exit 7,0x; sebagian tertutup margin EBITDA broker yang lebih tinggi | asumsi dan metodologi |
| BBCA | Hold Rp6.575 | BRI Danareksa dan Mandiri, Buy Rp8.600, 29 Jul 2026 | −24% | CoE: CAPM kebijakan 10,9% vs band CoE broker (rata-rata dikurangi 1 SD); Rp8.600 membutuhkan CoE sekitar 9,2% pada g 3,5% di model kami | asumsi (tingkat diskonto) |
| SIDO | Buy Rp448 | Kiwoom, Hold Rp394; Panin, Rp650; 9 Sep 2026 | +14% vs Kiwoom; −31% vs Panin | Panin adalah pandangan kepala cabang tanpa metode tertulis; Kiwoom lebih rendah karena menilai 2026 sebagai tahun penurunan penuh | asumsi (tahun pemulihan) |
| AMMN | Sell Rp2.830 | BRI Danareksa, 29 Jun 2026 (lihat e2e) | jauh di bawah | Elang, izin ekspor, horizon lisensi | metodologi dan asumsi |

Tidak ada selisih yang berasal dari kesalahan data Sectoral.

## GMFI: Kompas Saham (BRI Danareksa), Buy Rp88

Sumber: *Kompas Saham Retail Research Insight, GMFI IJ*, 24 September 2026 (`spec/Kompas Saham - GMFI.pdf` di checkout utama).

**Yang sama.** Keduanya FCFF DCF lima tahun dalam US$ dan dikonversi sekali ke rupiah (broker Rp17.800/US$, kami Rp17.837/US$, Yahoo 24 September). Keduanya membaca 1H26 yang sama: pendapatan US$270,3 juta (+51% yoy).

**Jembatan dari target kami ke target broker** (dihitung pada model kami, hanya input yang diganti):

| Langkah | Nilai per saham |
|---|---|
| Target Sectoral (WACC 9,3%, g 3,0%, terminal Gordon) | Rp103 |
| g 2,5% seperti broker | Rp94 (−9) |
| WACC 9,6% seperti broker | Rp89 (−5) |
| Terminal 50% Gordon, 50% exit EV/EBITDA 7,0x seperti broker | Rp75 (−14) |
| Sisa: proyeksi broker (margin EBITDA lebih tinggi, pendapatan lebih rendah) | Rp88 (+13) |

**Proyeksi.** FY26F broker: pendapatan US$541,2 juta, EBITDA US$86,1 juta, laba US$38,4 juta. Kami: US$594,6 juta, US$75,5 juta, US$28,7 juta. Pendapatan kami lebih tinggi karena skenario H2 memakai run-rate 1H yang ditopang engine overhaul; margin kami lebih rendah karena beban material naik ke 43% pendapatan pada mix engine. Broker menaikkan margin EBITDA ke 17,7% pada FY28F lewat operating leverage; kami 14,0%. Selisih margin ini yang menutup sebagian besar selisih metode terminal.

**Catatan metodologi.** Kami memakai exit EV/EBITDA historis emiten hanya sebagai cross-check yang diungkapkan (§4.4, tidak dirata-rata). Broker merata-ratanya, dan menyebut sendiri bahwa exit 7,0x menyiratkan pertumbuhan terminal mendekati nol. Selisih 17% di bawah ambang 20%; tidak ada perubahan.

## BBCA: BRI Danareksa dan Mandiri, Buy Rp8.600

Sumber: Investortrust, 29 Juli 2026 (BRI Danareksa menurunkan target dari Rp10.900 ke Rp8.600; Mandiri Rp8.600). Artikel tidak memuat metode rinci; BRI Danareksa menyebut CoE diturunkan satu simpangan baku untuk mencerminkan kenaikan risk-free.

**Laba sejalan.** Laba induk FY26F kami Rp60,9 triliun, dua kali laba 1H26 resmi Rp30,3 triliun; artikel melaporkan biaya kredit 0,4% dan tekanan NIM, yang juga tercermin di driver kami.

**Selisih hampir seluruhnya tingkat diskonto.** Pada model DDM kami (laba, payout dan batas modal yang sama):

| CoE | g | Nilai per saham |
|---|---|---|
| 10,9% (kebijakan) | 3,5% | Rp6.583 |
| 10,0% | 3,5% | Rp7.511 |
| 9,5% | 3,5% | Rp8.147 |
| 9,2% | 3,5% | Rp8.600 |
| 10,0% | 4,5% | Rp8.583 |

Target broker setara dengan CoE sekitar 9,2% pada g 3,5%, atau CoE 10,0% dengan g 4,5%. Pembanding bertanggal di laporan (rencana 2.1) memberi CoE BBCA 10,9% pada input pasar (INDOGB 7,01% dikurangi default spread 1,62%, beta Blume 0,82, ERP total Indonesia 6,69%), sama dengan CoE kebijakan. Harga pasar Rp6.225 menyiratkan CoE 11,3%, lebih tinggi dari kebijakan. Tidak ada dasar pasar untuk CoE 9,2%, jadi target tidak diubah. Selisih dijelaskan: **asumsi tingkat diskonto**, band CoE historis broker vs CAPM.

## SIDO: Kiwoom Hold Rp394, Panin Rp650

Sumber: Insider Indonesia, 10 September 2026 (kutipan 9 September).

- **Kiwoom (Hold, Rp394):** menilai 2026 sebagai tahun penurunan (pendapatan 1H26 turun sekitar 20% yoy, laba 44% yoy), dengan valuasi dan imbal hasil dividen menarik. Skenario kami juga menurunkan FY26F (pendapatan −14%, laba −31%), lalu tumbuh lagi mulai FY27F (laba +13,5%, margin EBITDA 35,0% ke 36,0%). Target kami 14% lebih tinggi; di bawah ambang 20%.
- **Panin (Accumulate, Rp650):** pandangan kepala cabang, bukan laporan riset dengan metode dan proyeksi tertulis; menyebut 2027 sebagai tahun pemulihan. Target kami 31% lebih rendah. Selisih dijelaskan sebagai **asumsi kecepatan pemulihan** dan kualitas sumber: tanpa proyeksi atau metode, angka Rp650 tidak dapat dijembatani ke model, sehingga tidak dipakai untuk menggeser target.

## Tindak lanjut

- GMFI: tidak ada perubahan. Kekuatan margin FY27F-FY28F adalah asumsi yang paling layak diuji ulang saat rilis 9M26.
- BBCA: tidak ada perubahan; CoE kebijakan kini tampil berdampingan dengan pembanding pasar di laporan (rencana 2.1).
- SIDO: tidak ada perubahan.
- Tidak ditemukan kesalahan data.

## Sumber

- BRI Danareksa Sekuritas, *Kompas Saham Retail Research Insight: GMFI IJ*, 24 September 2026 (`spec/Kompas Saham - GMFI.pdf`)
- [Investortrust, Saham BCA (BBCA) dipertahankan beli usai rilis kinerja semester I 2026, 29 Juli 2026](https://investortrust.id/market/111024/saham-bca-bbca-dipertahankan-beli-usai-rilis-kinerja-keuangan-semester-i-2026-intip-target-harga-ini)
- [Insider Indonesia, Kinerja SIDO diprediksi pulih pada 2027, 10 September 2026](https://insiderindonesia.com/detail/1450233/kinerja-sido-diprediksi-pulih-pada-2027-simak-rekomendasi-analis)

# Self review PDF keluaran — 23 September 2026

## Cakupan dan putusan

Saya memeriksa **22 PDF** di `out/` (halaman, teks terambil, status, dan indikasi cacat), membaca per halaman delapan laporan di `out/e2e-2026-09-23/`, serta merender cover delapan laporan dan kedua referensi. Saya juga merender halaman 3 dan 6 GMFI untuk memeriksa tabel serta page break. Pembandingnya adalah `spec/20260629-AMMN.pdf` (18 halaman), `spec/GMFI-Company-Update-contoh.pdf` (8 halaman), dan aturan `spec/Instruksi-Report-v3.md`. Angka dalam referensi dipakai untuk mendeteksi perbedaan yang perlu direkonsiliasi, bukan langsung mengganti data emiten pada tanggal laporan yang berbeda.

**Putusan: jangan distribusikan tujuh PDF non-AMMN sebagai Company Update atau nilai wajar yang dapat ditindaklanjuti.** Label “analisis skenario informasional” tidak menyelesaikan kesalahan metode, input, serta klaim yang bertentangan dengan exhibit. AMMN sudah benar diberi status `DRAFT NON-DISTRIBUTABLE`, tetapi halaman 4 masih memuat screen FY26F–FY28F berbasis CAGR yang mudah disalahbaca sebagai forecast tambang. File lama `out/BBCA.pdf` dan `out/test.pdf` lebih berisiko karena masih menampilkan Target Harga dan teks internal.

## Perbandingan dengan referensi

| Kebutuhan yang tampak di referensi/spesifikasi | Keadaan keluaran saat ini |
|---|---|
| GMFI: hasil aktual 1H26, revenue bridge engine/airframe, material cost, laba dan run rate FY26F (referensi hlm. 1–2) | PDF GMFI bertanggal 22 Sep 2026 masih membuka tesis dari FY25; tidak menyajikan 1H26 atau bridge operasional. Referensi bertanggal 18 Sep 2026 sudah memuat hasil 1H26, jadi keterlambatan ini terkonfirmasi dari dokumen yang diberikan. |
| AMMN: rangkaian fisik tambang–smelter, forecast operasional dan SOTP (referensi hlm. 1–2, serta exhibit sesudahnya) | PDF AMMN tidak mempunyai input cukup untuk memverifikasi 1H26, LoM dan SOTP. Status draft sudah tepat; screen CAGR pada hlm. 4 tidak memenuhi forecast fisik. |
| Cover: tesis, hasil aktual terbaru, target/metode yang dapat ditelusuri, dan Key Financials 5 tahun (kedua referensi hlm. 1) | Tujuh cover non-AMMN memakai pola generik dan Key Financials hanya empat baris; margin, pertumbuhan, BVPS/DPS, PER/PBV/yield serta EV/EBITDA hilang. |
| Driver dan unit sesuai emiten, sumber, periode, serta risk/catalyst transmission (spesifikasi §1–§5) | Semua tujuh PDF non-AMMN memuat kalimat risiko komoditas dan asumsi “proyek smelter” meskipun bukan emiten tambang. Katalis sering kosong; tabel forecast terutama memakai CAGR historis. |
| Model dan mata uang pelaporan konsisten (spesifikasi §2–§4) | GMFI referensi memakai US$; PDF memakai Rp tanpa jembatan sumber/kurs yang memadai. Bank BBRI menampilkan FCFF/WACC/EV sebagai nilai utama meski ada DDM di belakang. |

Referensi GMFI sendiri masih berisi placeholder chart; placeholder tersebut bukan standar yang perlu ditiru. Referensi AMMN mempunyai beberapa angka forecast yang berbeda antarparagraf cover, sehingga angka benchmark perlu verifikasi independen sebelum dipakai sebagai oracle.

## Temuan lintas laporan, urutan prioritas

1. **P0 — Gate rilis terlalu longgar.** Semua tujuh PDF non-AMMN tetap berstatus `informational_scenario_analysis` walaupun `G1_periode` hanya `dilabeli` dan catatan G2 menyebut interim terstruktur tidak tersedia. GMFI jelas tertinggal dari 1H26 yang telah muncul dalam referensi. INET memiliki `G1_kas=gagal-dilabeli` dan `G3.4_downside=gagal`, tetapi tetap menerbitkan nilai Rp60. BBRI memiliki `G3.2_skala=gagal-dilabeli` namun tetap menerbitkan nilai Rp6.460. Status dan log gate berasal dari JSON pasangan PDF.
2. **P0 — Valuasi bank salah metode.** BBRI hlm. 1, 5–6 memberi nilai utama FCFF DCF dengan WACC 7,9%, terminal Gordon dan EV/EBITDA. Hlm. 5–7 juga memuat DDM/Inverse CoE, sehingga pembaca mendapat dua logika nilai yang bertentangan. Spesifikasi §4 melarang EV/WACC DCF untuk bank. Tabel historis BBRI hlm. 2 bahkan menampilkan kas Rp0 untuk 2023–2025; ketiadaan data tidak boleh berubah menjadi nol.
3. **P0 — Tanda dan makna D&A/capex rusak.** JPFA, SIDO, SSIA hlm. 3/5 masing-masing memakai D&A negatif `-4,5%`, `-23,9%`, `-9,2%` dari revenue dan baris D&A negatif di FCFF. GMFI memakai D&A/capex sekitar Rp1,3 miliar per tahun terhadap pendapatan FY26F Rp8.413,5 miliar. Ini menuntut audit pemetaan sumber dan unit. Dalam ketujuh model, FCFF FY26F sama persis dengan laba bersih FY26F karena D&A disamakan dengan sustaining capex dan perubahan NWC tidak terlihat; kesamaan itu tidak membuktikan rekonsiliasi kas.
4. **P0 — Asumsi nol/flat tidak bersumber.** Hlm. 3 semua tujuh laporan memuat `capex proyek Rp0` dengan alasan tidak ada guidance di cache, `utang flat` tanpa jadwal pelunasan, dan sustaining capex `= D&A`. Catatan metodologi hlm. terakhir bahkan menyebut “jadwal smelter” pada emiten non-tambang. Angka yang tidak tersedia harus menjadi gap atau asumsi dengan bukti dan sensitivitas yang sah, bukan nilai nol otomatis.
5. **P1 — Narasi salah sektor.** Kalimat `Risiko utama: konsentrasi komoditas, eksekusi belanja modal, dan pelemahan harga` berulang di BBRI, GMFI, INET, JPFA, POWR, SIDO, SSIA hlm. 1/4. “Capex proyek smelter selesai FY25” muncul pada tabel asumsi tujuh emiten. Template tersebut meniadakan mekanisme risiko nyata: misalnya GMFI terkait volume engine, material cost, dan pelanggan terkait seperti dibahas referensi.
6. **P1 — Kualitas nilai indikatif.** Pada SSIA hlm. 5, nilai exit `Rp-49` masih dirata-ratakan dengan Gordon menjadi nilai indikatif `Rp710`. Pada INET, log gate menyatakan downside Rp60 sama dengan base Rp60 setelah pembulatan. Terminal value mendominasi nilai pada banyak laporan; justifikasi tiga tahun eksplisit dan g 3,5% belum cukup untuk menyatakan nilai yang andal.
7. **P1 — Kepadatan dan alur halaman.** Pada delapan laporan, beberapa halaman hanya terisi sekitar 23–55% tinggi bidang isi; AMMN hlm. 4–5 sekitar 27–28%, dan tujuh laporan non-AMMN hlm. 3–4 sekitar 31–43%. GMFI hlm. 6 mulai dengan sambungan tabel di bagian paling atas tanpa running header; struktur yang sama muncul pada halaman sambungan valuasi lain. Cover jauh lebih lapang daripada dua referensi tetapi font dan tabel tetap kecil. Nama pemegang saham pada cover terpotong (`PT Angkasa Pura Indone`, `PT Garuda Indonesia (P`).
8. **P1 — Tanggal harga.** Ketujuh PDF non-AMMN bertanggal 22 Sep 2026, tetapi chart harga berakhir 14 Sep 2026. Jeda delapan hari harus diuji terhadap kebijakan freshness sebelum harga terakhir dan upside dipakai.
9. **P1 — Artefak lama masih mudah ditemukan.** `out/BBCA.pdf` dan `out/test.pdf` menampilkan Target Harga dan string `kurasi skor` lima kali. Keduanya belum diberi penanda arsip/rejected pada lokasinya. Semua delapan PDF di `out/review-rejected/` jelas merupakan kandidat yang sudah ditolak, tetapi keberadaannya memperbesar risiko salah memilih file untuk distribusi.

## Penilaian delapan PDF batch terkini

| PDF | Halaman | Putusan dan bukti utama |
|---|---:|---|
| `e2e-2026-09-23/AMMN/AMMN.pdf` | 5 | **Draft, benar ditahan.** Hlm. 2 terakhir hanya kuartal berakhir 31 Mar 2026; provenance/tanggal rilis tidak ada. Hlm. 3 merinci gap SOTP/LoM. Hlm. 4 tetap menampilkan screen CAGR FY26F–FY28F yang perlu dipindah dari bentuk forecast sebelum distribusi. |
| `e2e-2026-09-23/BBRI/BBRI.pdf` | 9 | **Tolak.** Valuasi utama bank memakai FCFF/WACC dan EV; kas historis nol; narasi/risiko smelter-komoditas; gate skala gagal-dilabeli. Hlm. 5–7 memuat DDM sebagai tambahan yang belum menggantikan nilai utama. |
| `e2e-2026-09-23/GMFI/GMFI.pdf` | 8 | **Tolak.** Hasil 1H26 yang ada di benchmark tidak dipakai. Model Rp dan saham 119.666 juta belum direkonsiliasi dengan benchmark US$ dan 124.835 juta. D&A/capex Rp1,3 miliar serta FCFF=laba bersih merusak DCF; hlm. 3/6 bermasalah secara visual. |
| `e2e-2026-09-23/INET/INET.pdf` | 8 | **Tolak.** Gate kas dan downside gagal; nilai Rp60 tetap tampil. Pertumbuhan FY26F 30% berbasis CAGR, debt flat dan capex proyek nol; risiko komoditas/smelter salah sektor. |
| `e2e-2026-09-23/JPFA/JPFA.pdf` | 8 | **Tolak.** D&A negatif Rp2.943 miliar FY26F dan sustaining capex `=D&A`; risiko dan asumsi smelter generik. Tidak ada bridge volume pakan/unggas dan biaya input yang membuktikan tesis. |
| `e2e-2026-09-23/POWR/POWR.pdf` | 8 | **Tolak.** Research trace `insufficient`, tetapi nilai Rp1.440 tetap tampil. Tidak ada bridge volume listrik/tarif/bahan bakar; debt flat, capex nol, narasi risiko komoditas generik. |
| `e2e-2026-09-23/SIDO/SIDO.pdf` | 8 | **Tolak.** Research trace `insufficient`; D&A negatif Rp1.024,7 miliar FY26F dan asumsi smelter. Nilai Rp390 tetap tampil meski basis operasi dan kas tidak tervalidasi. |
| `e2e-2026-09-23/SSIA/SSIA.pdf` | 8 | **Tolak.** Research trace `invalid`; D&A negatif Rp412,4 miliar FY26F; exit value negatif Rp-49 dirata-ratakan ke nilai Rp710. Katalis dan asumsi smelter tidak relevan. |

## Inventaris PDF lain di `out/`

| PDF | Halaman | Hasil pemeriksaan |
|---|---:|---|
| `AMMN.pdf` | 5 | Draft dengan blokir yang sama seperti batch; bukan report produksi. |
| `BBCA.pdf` | 7 | Output lama: Target Harga Rp6.710, `kurasi skor` lima kali, dan DCF bank; jangan dipakai. |
| `test.pdf` | 7 | Output lama: Target Harga AMMN Rp710 dan `kurasi skor` lima kali; jangan dipakai. |
| `branding-demo/AMMN.pdf` | 5 | Salinan visual draft AMMN; bukan report produksi. |
| `copyfix-2026-09-23/SIDO.pdf` | 8 | Iterasi copy, masih mempunyai masalah D&A/capex serta smelter; bukan pengganti batch yang diterima. |
| `demo/BBCA.pdf` | 10 | Demo bank masih memakai FCFF/WACC dan smelter; bukan report produksi. |
| `review-rejected/AMMN.pdf` | 9 | Versi AMMN yang sudah ditolak; status draft, layout lebih panjang. |
| `review-rejected/ammn-json-failure-20260923/AMMN.pdf` | 5 | Versi gagal JSON, status draft. |
| `review-rejected/bbca-bad-quarterly-paths-20260923/BBCA.pdf` | 9 | Versi ditolak; metode DCF bank tetap salah. |
| `review-rejected/bbca-before-quarterly-nudge-20260923/BBCA.pdf` | 10 | Versi ditolak; metode DCF bank tetap salah. |
| `review-rejected/bbca-flow-gate-20260923/BBCA.pdf` | 9 | Versi ditolak; metode DCF bank tetap salah. |
| `review-rejected/bbca-overclaim-20260923/BBCA.pdf` | 9 | Versi ditolak; metode DCF bank tetap salah. |
| `review-rejected/bbca-quartile-path-repair-20260923/BBCA.pdf` | 9 | Versi ditolak; metode DCF bank tetap salah. |
| `review-rejected/bbca-semantic-20260923/BBCA.pdf` | 10 | Versi ditolak; metode DCF bank tetap salah. |

## Tindakan perbaikan yang diperlukan sebelum review ulang

1. Jadikan hasil resmi interim terbaru, tanggal rilis, periode, satuan dan sumber sebagai syarat rilis per profile. Pisahkan draft dan skenario internal dari direktori output yang mungkin dibagikan.
2. Gunakan DDM/residual income sebagai metode utama bank, dan blokir nilai publik jika metode/rekonsiliasi profile gagal. Untuk emiten lain, blokir nilai bila D&A/capex, NWC, utang, downside atau riset wajib gagal.
3. Audit mapping D&A, capex, kas, utang dan unit setiap emiten dari cache/sumber primer. Hilangkan default `proyek Rp0`, `utang flat`, serta `capex=D&A` bila tidak dibuktikan. Rekonsiliasikan FCFF dari NOPAT, bukan hanya dari laba bersih.
4. Bangun driver operasi dan risiko per bisnis. GMFI perlu memasukkan 1H26 dan bridge engine/airframe; AMMN memerlukan input fisik dan SOTP/LoM. Hapus teks smelter/komoditas dari profile yang tidak berlaku.
5. Rapikan halaman: gabungkan halaman tipis, ulang header pada halaman sambungan exhibit, perbesar teks/tabel secukupnya, tulis nama pemegang saham lengkap, lalu inspeksi PDF final per halaman.

Ini adalah audit artefak yang sudah ada, bukan validasi independen atas seluruh angka pasar dan laporan keuangan. Rebuild dan pemeriksaan sumber primer diperlukan sebelum klaim akurasi angka atau status distribusi dapat dinaikkan.

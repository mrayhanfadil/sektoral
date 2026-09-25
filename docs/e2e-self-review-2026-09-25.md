# Self review e2e sembilan emiten — 25 September 2026

Riset end-to-end untuk AMMN, BBCA, BBRI, GMFI, INET, JPFA, POWR, SIDO dan SSIA pada tanggal laporan 24 September 2026, diperiksa dalam empat putaran: cacat penyajian, kesalahan data yang ditemukan lewat sumber luar, koherensi tiap laporan dibaca utuh, lalu grup peer. Dokumen ini mencatat keadaan terakhir (run `out/e2e-2026-09-25/all9-peers`), apa yang diperbaiki di tiap putaran, dugaan yang ternyata salah, dan penilaian analis yang masih menentukan hasil.

## Hasil terkini

| Emiten | Rating | Target | Harga 24 Sep | Potensi | Metode | Run pertama | Target publik pembanding |
|---|---|---|---|---|---|---|---|
| AMMN | Sell | Rp2.990 | Rp4.730 | −36,8% | SOTP/LoM | Sell Rp3.140 | 15 dari 16 Buy, rata-rata Rp6.829 |
| BBCA | Hold | Rp5.925 | Rp6.225 | −4,8% | DDM skenario | draft | Buy Rp8.600 (BRI Danareksa, Mandiri) |
| BBRI | Buy | Rp5.075 | Rp3.140 | +61,6% | DDM skenario | Buy Rp5.625 | rata-rata Rp3.692–4.250, tertinggi Rp4.900 |
| GMFI | Buy | Rp111 | Rp56 | +98,2% | DCF FCFF skenario | Buy Rp111 | Rp98 dan Rp150 |
| INET | Sell | Rp242 | Rp316 | −23,4% | EV/EBITDA peer | Sell Rp250 | rata-rata Rp585 (dua analis) |
| JPFA | Buy | Rp3.280 | Rp2.180 | +50,5% | DCF FCFF skenario | Sell Rp1.275 | Rp2.800–3.750 (11 analis) |
| POWR | Buy | Rp1.445 | Rp955 | +51,3% | DCF FCFF skenario | Buy Rp1.870 | sekitar Rp804–872 |
| SIDO | Buy | Rp448 | Rp350 | +28,0% | DCF FCFF skenario | draft | Hold Rp394 (Kiwoom), Accumulate Rp650 (Panin) |
| SSIA | Sell | Rp1.370 | Rp1.750 | −21,7% | SOTP holding + RNAV landbank | Sell Rp1.235 | Rp2.080–2.579 |

Kesembilan laporan kini terbit sebagai `distributable_assumption_led` dan lolos pemeriksa otomatis; 601 tes lolos. Harga memakai penutupan 24 September dan kurs Rp17.893/USD. Target publik adalah pembanding, bukan kebenaran: perbedaan dengannya adalah sinyal untuk memeriksa (bagian "Perbandingan dengan target publik").

| Run | Isi | Laporan bercacat |
|---|---|---|
| `out/e2e-2026-09-24/all9` | run pertama, JSON per file | 9 dari 9 |
| `out/e2e-2026-09-25/all9-fixed` | putaran 1: cacat penyajian; dokumen di `data/sectoral.db` | 0 dari 9 |
| `out/e2e-2026-09-25/all9-validated` | putaran 2: kesalahan data dari validasi eksternal | 0 dari 9 |
| `out/e2e-2026-09-25/all9-sense` | putaran 3: koherensi laporan | 0 dari 9 |
| `out/e2e-2026-09-25/all9-peers` | putaran 4: grup peer kurasi | 0 dari 9 |

## Putaran 1: cacat penyajian

Semua ditemukan pada run pertama; rating dan target tidak berubah karena perbaikannya menyangkut penyajian.

1. **Satuan tercampur di Key Financials (POWR):** kolom 2024–2025 berisi rupiah (8.838.196,9) di bawah label "US$ juta". Fallback sejarah Sectors kini selalu Rp miliar; skenario USD dikonversi dengan kurs yang sama dengan DCF.
2. **Kolom FY26F kosong (AMMN):** laba bersih FY26F NA di laba rugi dan rasio padahal Key Financials menulis US$1.144 juta. Tabel kini memakai laba yang sama.
3. **EBITDA forecast tidak konsisten antar-tabel (SSIA):** kini satu aturan untuk semua tabel.
4. **Catatan sumber bertentangan dengan isinya:** "kolom forecast belum tersedia (NA)" di bawah kolom yang terisi (BBRI, INET, JPFA, POWR, SSIA). Kalimat itu dihapus saat skenario mengisi kolom.
5. **Draft membocorkan nilai wajar (BBCA):** "DDM Gordon memberi Rp4.980/saham" di laporan yang menahan target. Draft kini tidak mencetak nilai screening.
6. **Dua nilai DDM yang bertentangan (BBRI):** grid screening dihapus bila DDM skenario menjadi dasar target.
7. **Multiple tanpa makna:** P/E 9.141,7x, P/B 793,8x, band P/E rata-rata 1.702,1x. Di atas 100x kini ditulis n.m.
8. **Rata-rata peer rusak oleh pencilan:** margin bersih rata-rata −2.306,2%. Rasio n.m. tidak masuk rata-rata.
9. **Perubahan yoy di atas 500%** kini n.m.
10. **Format:** "-0" dan "2,43xx".
11. **Label target salah (SSIA):** tabel PER berjudul "Target harga" di bawah target SOTP kini "Silang cek".
12. **Kalimat bahasa Inggris** di rantai metode AMMN dan JPFA.

## Putaran 2: kesalahan data dari validasi eksternal

Setiap angka diuji dengan sumber di luar pipeline: harga dan laporan keuangan Yahoo Finance, laporan keuangan resmi dan audit emiten, harga komoditas, dan target analis yang diberitakan.

**Yang terkonfirmasi.** Angka interim 1H26 AMMN, JPFA, SSIA, SIDO dan INET cocok dengan jumlah kuartal Yahoo atau rilis yang diberitakan. Pendapatan FY26F BBRI Rp215,8 triliun adalah artefak definisi (Yahoo 1H26 Rp98,3 triliun, bukan Rp107,9 triliun). Yahoo juga mencatat EBITDA GMFI sama dengan EBIT, jadi keanehan itu berasal dari agregator data. Harga penutupan cocok dengan Yahoo pada tanggal masing-masing, tetapi laporan 24 September memakai penutupan 22–23 September (SSIA Rp1.600 dari hari turun tajam).

**Yang diperbaiki**

1. **D&A Sectors tidak kredibel.** Sectors menurunkan D&A sebagai EBITDA − EBIT; untuk JPFA, SIDO, SSIA, INET dan GMFI itu menyiratkan umur aset tetap 63 sampai lebih dari 2.000 tahun. Laporan audit JPFA 2025 mencatat penyusutan Rp1.265 miliar, bukan sekitar Rp236 miliar. D&A dengan umur tersirat di atas 40 tahun kini ditolak; DCF memakai penyusutan resmi 1H26 atau tahunan audit, dan tanpa keduanya DCF tidak memadai. JPFA berbalik dari Sell Rp1.275 ke Buy Rp3.280, dan selisih Gordon vs exit turun dari 49,8% ke 4,1%.
2. **Dek tembaga basi tujuh bulan (AMMN).** Seri tembaga Sectors berhenti 15 Februari 2026, dan "rata-rata 12 bulan"-nya hanya enam bulan karena datanya dua kali sebulan. Seri Sectors kini dipakai bila titik terakhirnya paling lama 45 hari sebelum tanggal laporan; bila tidak, seri harian Yahoo (COMEX `HG=F`, `GC=F`) berlabel; tanpa seri segar SOTP/LoM tidak memadai. Dek tembaga US$13.002/t (Okt 2025–Sep 2026), bukan US$11.122/t.
3. **Dividen sesudah tanggal neraca** kini dikurangkan dari ekuitas dan tampil sebagai baris sendiri (JPFA Rp140/saham, POWR Rp49,53, SIDO Rp15).
4. **Payout = DPS 12 bulan terakhir / EPS tahun buku terakhir.** `payout_ratio` Sectors memakai laba 12 bulan yang sudah memuat 1H26; BBRI kini 92,0%, sesuai payout FY2025 yang diumumkan (DPS Rp346).
5. **EV/EBITDA peer dari 12 bulan terakhir** (empat kuartal Yahoo) bila tersedia, selain itu tahun buku terakhir.
6. **Harga dan kurs terbaru.** `python -m app.market_quote --as-of <tanggal> <ticker>...` menyimpan sepuluh penutupan terakhir; run memakai penutupan terakhir pada atau sebelum tanggal laporan. Kurs tidak lagi mengambil batang hari berjalan (Rp17.878 intraday berbanding penutupan Rp17.805 pada 23 September).
7. **Tingkat diskonto tersirat harga.** ERP 4% dipertahankan sebagai kebijakan; setiap DDM dan DCF kini menampilkan CoE/WACC yang membuat nilai model sama dengan harga. Label "Beta (Bloomberg)" dan "ERP (Damodaran)" diganti "kebijakan analis".
8. **BBCA ditolak karena "net sell asing".** Filter bahasa rekomendasi agen forecast menolak kata "sell" di risiko arus asing, sehingga skenario gugur di setiap run. Frasa arus pasar kini dibuang lebih dahulu (aturan agen analis); saran sungguhan tetap ditolak.
9. **SIDO dibuka.** Laporan dari cermin Indo Premier diberi tanggal terbit batas atas 3 Agustus 2026, hari angka yang sama diberitakan; dasarnya tercatat di paket.
10. **Paket bukti POWR** kini memuat utang wesel US$343,6 juta, investasi jangka pendek dan penyusutan 1H26, sehingga neraca interim tidak lagi menulis pinjaman "-".

**Dugaan yang ternyata salah**

- Penyebab DCF JPFA yang rendah adalah D&A, bukan capex dan modal kerja seperti ditulis versi awal.
- Kas POWR tidak berlebih: Rp5.176 miliar adalah kas plus investasi jangka pendek, dan neraca 30 Juni 2026 mencatat total US$298 juta, hampir sama dengan akhir 2025.
- EBITDA LINK tidak tidak-konsisten: pembandingnya (Rp2,35 triliun) dari ringkasan `info` Yahoo; empat kuartal laporan LINK berjumlah Rp645 miliar.

## Putaran 3: koherensi laporan

Tujuannya: angka di tabel, target, teks cover dan asumsi berasal dari satu model yang sama, tidak bertentangan dengan fakta bersumber, dan setiap penilaian analis diberi label beserta sensitivitasnya.

**AMMN: satu model tambang dari target sampai Key Financials**

1. **Tanpa izin ekspor sebagai kasus dasar.** Izin ekspor konsentrat sementara berakhir 30 April 2026; Paparan Publik 2026 menyebut konsentrat hanya dapat dijual dengan izin itu, dan IDN Times (6 Juni 2026) mengutip ESDM NTB bahwa AMNT tidak berencana mengajukan perpanjangan. Model sebelumnya tetap menjual kelebihan konsentrat, padahal skenario 2H26-nya sendiri tanpa penjualan konsentrat. Kini umpan pabrik dibatasi pada bijih yang tembaganya dapat dilebur smelter (220 kt x utilisasi Juni 93%), sisa bijih diproses kemudian, dan konsentrat 2H26 di atas kapasitas dilebur pada 2027. Pit berjalan sampai 2033, stockpile sampai 2038 dan Elang mulai 2038; jadwal emiten dengan ekspor (pit 2031/2032, stockpile 2033/2034) menjadi sensitivitas Rp3.800.
2. **Capex Elang mengikuti umpan Elang pertama** (2036–2037 untuk umpan 2038), bukan profil broker 2029–2030 yang berlaku untuk bijih pertama 2031.
3. **Faktor Elang 50% adalah probabilitas pengembangan.** Elang dimulai sesudah umur tambang Batu Hijau (Laporan Tahunan 2025), sehingga jadwal Batu Hijau sama dengan atau tanpa Elang; NAV Elang (termasuk capex) x 50% sama dengan rata-rata tertimbang kedua rencana tambang.
4. **FY27F–FY30F dari jadwal LoM.** Key Financials, laba rugi dan multiple kini membaca jadwal yang sama dengan target: FY27F pendapatan US$5,04 miliar, EBITDA US$3,39 miliar, laba bersih US$1,77 miliar. Sebelumnya tabel memakai skenario agen terpisah (EBITDA FY27F US$2,70 miliar) di samping jadwal LoM US$3,9 miliar per tahun.
5. **Sensitivitas umur izin.** Emiten menyebut Elang berjalan "sekurangnya sampai 2050"; menambang sampai cadangan habis (2075) memberi Rp3.230.

**SSIA: landbank dinilai dengan RNAV, bukan biaya perolehan**

Klaim lama bahwa lahan pada biaya perolehan "konservatif" tidak pernah diuji. Paket bukti kini memuat Laporan Tahunan 2025 (catatan 15, diaudit: 1.683 ha tanah untuk pengembangan, nilai buku Rp4.255 miliar atau Rp253 ribu/m²; penilai independen 126 ha pada Rp323 ribu/m²; SSIA memiliki 63,5% Suryacipta Swadaya) dan presentasi 1H26 (harga jual marketing, penjualan lahan 2021–1H26, margin segmen properti, sisa lahan Karawang 23,6 ha).

RNAV = lahan bruto x porsi dapat dijual 65% (asumsi analis) x laju historis 50,3 ha/tahun x harga marketing 1H26 Rp2,08 juta/m² yang tumbuh 2,0%/tahun (CAGR 2021–2025 tanpa 2024) x margin kas 50,7%, didiskonto CoE 10,9%. Margin kas adalah margin laba kotor segmen properti ditambah biaya buku lahan yang sudah tercatat di beban pokok (sunk), dikurangi beban usaha dan PPh final 2,5%. RNAV Rp5,25 triliun berbanding nilai buku Rp4,25 triliun; porsi SSIA atas selisihnya menambah Rp134 per saham.

| Laju penjualan | Harga tetap | Harga +2,0%/tahun (basis) | Harga +5%/tahun |
|---|---|---|---|
| 25 ha/tahun | (Rp234) | (Rp165) | Rp4 |
| 50 ha/tahun | Rp43 | Rp132 | Rp313 |
| 75 ha/tahun | Rp230 | Rp315 | Rp474 |
| 100 ha/tahun | Rp359 | Rp435 | Rp571 |
| 135 ha/tahun (target emiten 2026) | Rp481 | Rp545 | Rp655 |

Pada laju historis, lahan itu hanya sedikit di atas nilai bukunya; laju penjualan yang menentukan, dan 1H26 baru 9,4 ha dari target 135 ha.

**BBRI: jalur laba harus dekat dengan rekam jejaknya**

Agen forecast menulis pertumbuhan pendapatan 10,5%, 9,5%, 9,0% dan 8,5% untuk FY27F–FY30F dengan alasan "momentum NII 1H26", padahal pendapatan BBRI tumbuh 3,1% dan laba 3,5% per tahun pada 2022–2025, dan keduanya turun pada 2025. Validator agen kini menolak rata-rata pertumbuhan lebih dari 5pp di atas CAGR tiga tahun pendapatan atau laba emiten kecuali ada artikel bertanggal yang mendukungnya; aturan yang sama ada di instruksi agen. Jalur baru membawa laba dari Rp59,3 triliun (FY26F) ke Rp68,8 triliun (FY30F), dan target turun dari Rp6.225 ke Rp5.075. BBCA, JPFA, POWR, GMFI dan SIDO sudah berada di dekat rekam jejaknya; INET mengutip berita bertanggal.

**Kelipatan historis dari EBITDA yang cacat**

EV/EBITDA historis Sectors dibagi EBITDA Sectors yang sama. Tahun yang D&A-nya ditolak (umur tersirat di atas 40 tahun, atau EBITDA di bawah EBIT) kini tidak masuk cross-check exit, dan EBITDA yang diganti angka audit (JPFA 2025) diskalakan ulang. Cross-check exit GMFI sebelumnya "mengonfirmasi" DCF dengan 13,3–15,3x yang dihitung atas EBITDA tanpa penyusutan; laporannya kini menyatakan multiple historis yang kredibel kurang dari tiga titik.

**Teks cover yang bertentangan dengan angkanya**

- "Target ini mengimplikasikan ..., didukung rilis earnings 3Q26" (BBRI, rilis yang belum terbit) dan "didukung sertifikasi AS9100D" (GMFI) menyajikan katalis mendatang dari agen sebagai bukti; kini ditulis "Katalis positif terdekat: ...".
- AMMN menulis "jembatan produksi ... belum lengkap untuk membangun proyeksi umur aset" di halaman yang targetnya justru proyeksi umur aset; kalimat itu kini menjelaskan dasar LoM, dan paragraf target menyebut batasan izin ekspor.
- Butir cover SSIA kini menyebut landbank pada RNAV.

## Putaran 4: grup peer

Tabel peer Sectors adalah sub-sektor emiten, bukan model bisnisnya. GMFI (perawatan pesawat) dibandingkan dengan jalan tol, pelabuhan dan BREN di grup "Airport Operators"; POWR (listrik gas untuk kawasan industri) dengan pengembang energi terbarukan ber-P/E 50–190x; SSIA (pemilik kawasan industri) hanya dengan kontraktor, termasuk anak usahanya sendiri; AMMN dengan penambang emas, nikel dan timah; JPFA dengan emiten kecil ber-P/E 132–1.270x. Median dan cross-check dari grup itu tidak berarti apa-apa.

Kini tiap emiten punya paket grup peer di `data/peer_groups/<T>.json` yang ditinjau di git: peer dipilih menurut model bisnis, dan setiap peer yang dipakai maupun dikeluarkan tercatat dengan alasannya. Peer yang ada di tabel Sectors emiten tetap memakai baris Sectors; peer lain (termasuk bursa luar negeri) memakai snapshot Yahoo Finance bertanggal (`python -m app.peer_fundamentals --group <T>`): P/E, P/B dan EV/EBITDA dihitung dalam mata uang laporan peer sendiri, kapitalisasi dikonversi ke rupiah hanya untuk tampilan, dan periodenya tertulis (12 bulan terakhir, atau tahun buku terakhir bagi emiten yang melapor semesteran). Valuasi dan halaman peer membaca satu set yang sama, dan halaman peer memuat tabel "Grup peer: alasan pemilihan". Bila kurang dari tiga peer punya data, laporan memakai tabel Sectors dan menyebut alasannya. BBCA dan BBRI tetap memakai tabel bank Sectors, yang memang berisi bank.

| Emiten | Grup peer kurasi | Median P/E | P/B | EV/EBITDA | Dampak |
|---|---|---|---|---|---|
| AMMN | MDKA + produsen tembaga regional dan global (Freeport, Southern Copper, Antofagasta, Lundin, Hudbay, Zijin, MMG, CMOC, Sandfire) | 20,9x | 3,4x | 8,9x | cross-check P/E naik dari Rp2.510 (9,2x) ke Rp5.700 dan P/B dari Rp3.010 ke Rp4.780, jauh di atas target LoM Rp2.990 |
| GMFI | MRO: SIA Engineering, ST Engineering, AAR, VSE | 23,4x (dua peer valid) | 2,1x | 20,7x | cross-check PER gugur karena dua peer di atas 50x; P/BV Rp24 menjadi Rp43; EV/EBITDA peer jauh di atas multiple GMFI sendiri |
| POWR | PGEO, B.Grimm, GPSC, RATCH, EGCO, Gulf | 19,4x | 1,3x | 11,9x | PER FY kini dapat dihitung (Rp1.755) dan berada di atas target DCF Rp1.445; P/BV Rp990 |
| SSIA | DMAS, BEST, KIJA, TOTL, PBSA | 8,7x | 1,3x | 6,6x | cross-check PER Rp825 menjadi Rp740 |
| JPFA | CPIN, MAIN, SIPD, CPRO, CP Foods | 8,0x | 0,7x | 6,3x | cross-check PER Rp2.440 menjadi Rp2.870, 13% di bawah target DCF Rp3.280 |
| INET | LINK, MORA, KETR, DATA, TLKM, ISAT, SUPR | 18,3x | 2,1x | 12,8x | target tidak berubah (KBLV dan JAST tidak punya EV yang dapat dipakai) |
| SIDO | KLBF, TSPC, SOHO, DVLA, MERK, PYFA, KAEF | 9,7x | 1,4x | 5,8x | cross-check PER Rp268 menjadi Rp274 |

Target utama tidak berubah karena hanya INET yang dinilai dengan multiple peer. Yang berubah adalah apa yang dikatakan cross-check:

- **POWR dan GMFI kini didukung peer.** Produsen listrik industri diperdagangkan pada EV/EBITDA 11,9x dan P/E 19,4x, sedangkan DCF POWR menyiratkan exit 7,2x; MRO global pada EV/EBITDA 20,7x, sedangkan DCF GMFI menyiratkan sekitar 12x. Selisih dengan harga tetap berasal dari kebijakan tingkat diskonto, bukan dari peer.
- **AMMN kini bertentangan dengan peer.** Produsen tembaga diperdagangkan pada P/E 20,9x; target LoM Rp2.990 setara sekitar 7x laba FY27F. Selisihnya adalah asumsi LoM (tanpa izin ekspor, probabilitas Elang 50%, izin sampai 2050, diskonto USD 10%) berbanding cara pasar menilai produsen tembaga berumur panjang. Cross-check ini tampil di laporan dan tidak dirata-ratakan dengan target.

## Perbandingan dengan target publik

| Emiten | Sektoral | Target publik | Sumber selisih |
|---|---|---|---|
| AMMN | Sell Rp2.990 | rata-rata Rp6.829 | Elang dinilai sebagai proyek pra-FID dengan probabilitas 50% dan tanpa izin ekspor; lihat benchmark di bawah |
| BBCA | Hold Rp5.925 | Buy Rp8.600 | Harga menyiratkan CoE 10,5%, hampir sama dengan kebijakan 10,9%: model dan pasar sejalan, sedangkan Rp8.600 pada jalur dividen yang sama menyiratkan CoE 8,6%, atau pertumbuhan yang lebih tinggi |
| BBRI | Buy Rp5.075 | tertinggi Rp4.900 | Kebijakan CoE 10,9%; harga menyiratkan 15,6% |
| GMFI | Buy Rp111 | Rp98 dan Rp150 | Di dalam rentang |
| INET | Sell Rp242 | rata-rata Rp585 | Pasar menilai pertumbuhan (harga setara 106x laba FY26F); target memakai EV/EBITDA peer 12 bulan terakhir |
| JPFA | Buy Rp3.280 | Rp2.800–3.750 | Di dalam rentang sesudah perbaikan D&A |
| POWR | Buy Rp1.445 | sekitar Rp804–872 | Kebijakan WACC 9,7%; harga menyiratkan 12,9% |
| SIDO | Buy Rp448 | Rp394–650 | Di dalam rentang |
| SSIA | Sell Rp1.370 | Rp2.080–2.579 | Target broker memerlukan laju penjualan lahan mendekati target emiten dan kenaikan harga yang lebih cepat |

Tingkat diskonto tersirat harga pada DCF lainnya: JPFA WACC 11,7% (kebijakan 9,6%), GMFI 12,5% (9,3%), SIDO 13,0% (10,9%).

## Benchmark AMMN: BRI Danareksa, 29 Juni 2026 (`spec/20260629-AMMN.pdf`)

| | BRI Danareksa | Sektoral (24 Sep) |
|---|---|---|
| Rating / target | Buy / Rp6.000 | Sell / Rp2.990 |
| Harga pada tanggal laporan | Rp3.340 | Rp4.730 |
| Metode | SOTP: DCF Batu Hijau + EV/cadangan Elang, diskon 15% | SOTP/LoM per aset sampai 2050, tanpa terminal |
| Tingkat diskonto | WACC 12,7% (rf 6,8%, ERP 6,7%, beta 1,2) | 10% USD |
| Tembaga / emas 2026–30 | katoda US$5,9–6,0/lb; emas US$4.256–4.384/oz | US$13.002/t (US$5,90/lb); US$4.455/oz |
| Ekspor konsentrat sesudah 2026 | tidak | tidak (umpan dibatasi kapasitas smelter) |
| FY26F pendapatan / EBITDA (US$ miliar) | 4,00 / 2,02 (tabel); 4,7 / 2,56 (teks) | 4,72 / 2,54 |
| FY27F pendapatan / EBITDA (US$ miliar) | 4,29 / 2,67 | 5,04 / 3,39 |

Rekonsiliasi (US$ juta; Rp/saham pada Rp17.803/USD dan 72,41 miliar saham):

| Komponen | BRI Danareksa | Sektoral | Beda (Rp/saham) |
|---|---|---|---|
| Batu Hijau sesudah utang bersih | 6.355 | 9.590 | −800 |
| Elang | 22.663 | 2.559 | +4.940 |
| Diskon 15% | −4.353 | – | −1.070 |
| Total | 24.666 (Rp6.093) | 12.148 (Rp2.990) | ≈ +3.070 |

- **Selisih target seluruhnya Elang.** Elang adalah 78% SOTP broker, dinilai dengan EV/cadangan US$2.560/t Cu dan US$1.260/oz Au, tingkat multiple produsen, untuk proyek pra-FID yang butuh capex sekitar US$2 miliar dan belum berproduksi bertahun-tahun. Diskonnya ganda: 30% atas cadangan, lalu EV dikali 0,6 tanpa label.
- **Batu Hijau kami lebih tinggi**, bukan lebih konservatif. DCF broker memasukkan FCF 2025A (−US$1.540 juta) yang sudah tercermin di utang yang dikurangkan, memakai terminal 0% perpetual untuk tambang yang pit-nya selesai sekitar 2032, dan NPV US$11.440 juta tidak dapat direproduksi dari baris exhibit. WACC 12,7% memadukan rf rupiah dengan arus kas USD, yang dilarang §4.2.
- **Dek harga dan laba sejalan.** Dek tembaga selisih kurang dari 1%; FY27F EBITDA kami US$3,39 miliar berbanding broker US$2,67 miliar (FY27F) dan US$3,30 miliar (FY28F).
- **Inkonsistensi broker:** pertumbuhan FY26F +117% di tabel dan +153% di teks; SOTP Rp519.872 miliar sedangkan target dari Rp441.891 miliar sesudah diskon 15% yang hanya tampil di exhibit DCF; saham 72.412 juta di cover dan 72,52 miliar di valuasi.

## Penilaian yang tersisa

Semua penilaian ini diberi label di laporan beserta sensitivitasnya.

- **Kebijakan ERP 4%** (dipertahankan): menentukan BBRI, POWR dan GMFI yang jauh di atas harga. Setiap DDM dan DCF menampilkan tingkat diskonto tersirat harga.
- **AMMN:** probabilitas pengembangan Elang (0% memberi Rp2.360, 100% Rp3.620) dan status izin ekspor (diperpanjang: Rp3.800).
- **SSIA:** porsi lahan dapat dijual (65%) dan laju penjualan.
- **GMFI:** upside +98,2% tepat di bawah ambang Review Required (+100%); ekuitas tipis sesudah konversi utang membuat nilai per saham sangat peka terhadap EV.
- **AMMN berbanding peer tembaga:** cross-check P/E Rp5.700 dan P/B Rp4.780 jauh di atas target LoM Rp2.990 (lihat putaran 4).
- **Grup peer:** paket di `data/peer_groups/` adalah penilaian analis dan snapshot Yahoo-nya bertanggal 25 September 2026; GMFI hanya punya dua peer dengan P/E di bawah 50x. INET: PER tidak bermakna selama laba masih ramping.

## Verifikasi

- Pemeriksa otomatis membaca dokumen laporan dan menguji setiap cacat di atas, ditambah: dek tembaga basi, D&A tidak kredibel di DCF, dividen sesudah neraca, payout BBRI, penutupan basi, label beta/ERP, kode templat yang tidak dirender, kalimat cover yang bertentangan dengan valuasi, dan butir cover SSIA. Kesembilan laporan bersih.
- 601 tes lolos, termasuk tes baru untuk grup peer kurasi (paket valid, peer asing dinilai dalam mata uangnya sendiri, fallback ke tabel Sectors, laba tahunan untuk emiten semesteran), D&A tidak kredibel, D&A audit, dividen sesudah neraca, payout, tingkat diskonto tersirat, paket harga, kurs, EBITDA peer 12 bulan terakhir, kelipatan historis, jadwal LoM tanpa ekspor, capex Elang, filter arus asing dan aturan pertumbuhan agen.
- Laporan, jejak dan manifest tiap run tersimpan di `data/sectoral.db`; tidak ada file JSON di folder output.
- Pembaruan data (butuh jaringan, dijalankan eksplisit): `python -m app.refresh --as-of <tanggal> <ticker>...` memperbarui kurs, seri tembaga dan emas, paket harga penutupan dan snapshot peer sekaligus; `python -m app.batch ... --refresh-data` menjalankannya sebelum riset.

## Sumber

- Harga, laporan keuangan, kurs dan komoditas: Yahoo Finance melalui yfinance (`.JK`, `IDR=X`, `HG=F`, `GC=F`), diambil 25 September 2026; peer luar negeri (`S59.SI`, `S63.SI`, `AIR`, `VSEC`, `BGRIM.BK`, `GPSC.BK`, `RATCH.BK`, `EGCO.BK`, `GULF.BK`, `CPF.BK`, `FCX`, `SCCO`, `ANTO.L`, `LUN.TO`, `HBM`, `2899.HK`, `1208.HK`, `3993.HK`, `SFR.AX`) dan kurs silangnya pada tanggal yang sama.
- [Laporan keuangan audit JPFA 31 Desember 2025](https://d1be5sn7lppxuh.cloudfront.net/assets/files/files/financial_report/01-2026/pt-japfa-tbk-cfs-as-of-31-december-2025-audited.pdf) (hlm. 16 dan 148–149)
- [Laporan keuangan interim POWR 30 Juni 2026](https://www.listrindo.com/uploads/idx/1fb0306b5c1f30d0319115d5eb5abacb.pdf)
- SSIA: [Laporan Tahunan 2025](https://suryainternusa.com/assets/source/files/annual-report/ar-surya-2025---spread_compressed-low_22.05.2026.pdf) (PDF hlm. 56 dan 187), [presentasi 1H26](https://suryainternusa.com/assets/source/files/corporate-persentation/2026.09.01---ssia_1h26_-ads_v2.pdf) (hlm. 43, 44, 46, 49), [rilis 1H26](https://suryainternusa.com/assets/source/files/press-release/2026.08.04_press-release-ssia-1h26_eng_v2_ebu.pdf)
- AMMN izin ekspor: [Bloomberg Technoz (4 Mei 2026)](https://www.bloombergtechnoz.com/detail-news/107907/izin-ekspor-konsentrat-tembaga-amman-habis-baru-terealisasi-56), [IDN Times (6 Juni 2026)](https://ntb.idntimes.com/news/ntb/amnt-dipastikan-tak-ajukan-perpanjangan-relaksasi-ekspor-konsentrat-00-ldn3d-b7qt8x)
- Tembaga: [LME (Westmetall)](https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Cu_cash), [Trading Economics](https://tradingeconomics.com/commodity/copper)
- [Dividen BBRI tahun buku 2025 (Investortrust)](https://investortrust.id/market/99658/bbri-tebar-dividen-rp-52-1-triliun-rasio-dinaikkan)
- SIDO 1H26: [Radar Tasik (3 Agustus 2026)](https://radartasik.id/2026/08/03/laba-bersih-sido-muncul-anjlok-44-persen-pada-semester-i-2026-pendapatan-juga-masih-tertekan/), [IDX Channel](https://www.idxchannel.com/market-news/penjualan-jamu-dan-suplemen-lesu-laba-sidomuncul-sido-turun-44-persen); INET 1H26: [Kompas](https://money.kompas.com/read/2026/09/14/142058826/inet-bukukan-pendapatan-neto-rp-926-miliar-laba-bersih-rp-34-miliar)
- Target publik: [AMMN (Investortrust)](https://investortrust.id/market/117045/kinerja-amman-ammn-melejit-analis-pasang-target-harga-hingga-level-ini), [BBCA (Investortrust, 29 Juli 2026)](https://investortrust.id/market/111024/saham-bca-bbca-dipertahankan-beli-usai-rilis-kinerja-keuangan-semester-i-2026-intip-target-harga-ini), [BBRI (Investing.com)](https://www.investing.com/equities/bank-rakyat-in-consensus-estimates), [GMFI (TradingView)](https://www.tradingview.com/symbols/IDX-GMFI/forecast/), [INET (Investing.com)](https://www.investing.com/equities/sinergi-inti-andalan-prima-tbk-pt-consensus-estimates), [JPFA (TradingView)](https://id.tradingview.com/symbols/IDX-JPFA/forecast-price-target/), [POWR (TradingView)](https://id.tradingview.com/symbols/IDX-POWR/forecast/), [SIDO (Insider Indonesia, 10 September 2026)](https://insiderindonesia.com/detail/1450233/kinerja-sido-diprediksi-pulih-pada-2027-simak-rekomendasi-analis), [SSIA (Infonasional)](https://www.infonasional.com/rhb-sekuritas-target-saham-ssia)
- Benchmark: BRI Danareksa Sekuritas, *Amman Mineral Internasional: From Pit to Cathode*, 29 Juni 2026 (`spec/20260629-AMMN.pdf`)

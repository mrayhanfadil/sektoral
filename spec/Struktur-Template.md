## **Struktur Template Equity Report BRIDS — Slide 1-7 (Versi Detail)**

---

### **ATURAN UMUM LINTAS SLIDE**

**Exhibit labeling dan sourcing**  
 Setiap objek visual (chart) atau tabular (tabel) tanpa terkecuali harus punya dua elemen wajib:

* Label di atas objek: format "Exhibit \[nomor\]. \[deskripsi singkat, deskriptif bukan generik\]". Contoh yang benar: "Exhibit 4\. Revenue and Revenue Growth (2024A-2028F)". Contoh yang salah (terlalu generik): "Exhibit 4\. Chart".  
* Source line di bawah objek: selalu "Source: Company, Team Estimates", tanpa terkecuali, meskipun datanya murni historis dari lapkeu.

**Penomoran sequential**  
Nomor Exhibit berjalan terus dari Slide 1 sampai slide terakhir, tidak reset per halaman. Ini konsisten dengan pola existing report di mana Exhibit 1 di halaman 1 lanjut ke Exhibit 10 dst di halaman-halaman berikutnya. Implikasi teknis untuk automation: nomor Exhibit harus jadi counter global di generator, bukan variabel lokal per slide, supaya kalau ada revisi jumlah chart di satu slide, nomor Exhibit slide berikutnya otomatis re-sequence.

**Header setiap slide**

* Kiri atas: "Equity Research – Company Update". Baris di bawahnya: tanggal publikasi format "Day, DD Month YYYY" (contoh: "Monday, 20 July 2026"), konsisten dengan format.  
* Kanan atas: logo Sectors.app, ukuran dan posisi konsisten semua slide.  
* Divider horizontal warna X (`#XXXXXX`)

**Footer setiap slide**

* Kiri bawah: "sectors.app"  
* Kanan bawah: "See important disclosure at the back of this report" \+ nomor halaman

---

### **SLIDE 1 — Cover / Main Page**

#### **Sidebar Kiri (\~30% lebar halaman)**

**Blok rating**

* Rating utama dalam font besar, bold: "Buy" / "Hold" / "Sell"  
* Di bawahnya, italic, ukuran lebih kecil: status perubahan, salah satu dari "(Maintained)", "(Upgrade from Hold)", "(Downgrade from Buy)", "(Initiation)". Status ini penting karena PM/investor institutional biasanya scan halaman depan untuk lihat ada perubahan rating atau tidak sebelum baca detail.

**Box data harga**  
 Format tabel dua kolom (label kiri, angka kanan, rata kanan untuk angka):

* Last Price (Rp): harga penutupan terakhir sebelum tanggal publikasi  
* Target Price (Rp): TP baru dari valuasi Slide 4  
* Upside/Downside (%): (Target Price / Last Price \- 1\) x 100%, ditulis dengan tanda \+ atau \-

**Blok statistik sekunder**

* No. of Shares (mn): jumlah saham beredar  
* Mkt Cap (Rpbn/US\$mn): kapitalisasi pasar dalam dua mata uang, dipisah slash  
* Avg. Daily T/O (Rpbn/US\$mn): rata-rata turnover harian, biasanya window 3 atau 6 bulan, perlu didefinisikan periode yang dipakai secara konsisten di semua report  
* Free Float (%): persentase saham yang beredar bebas di luar pemegang saham mayoritas/pengendali  
* Major Shareholder (%): nama pemegang saham utama beserta persentase kepemilikan, kalau ada lebih dari satu pemegang saham signifikan (\>5%), bisa ditambah baris kedua

**Exhibit 1\. EPS Consensus table (Ga perlu)**  
Tabel dengan kolom: tahun forecast (3 tahun ke depan dari tahun publikasi), baris BRIDS, Consensus, dan baris deviasi "BRIDS/Cons (%)" yang menunjukkan berapa persen estimasi BRIDS di atas/bawah konsensus pasar. Angka deviasi dalam kurung kalau BRIDS di bawah konsensus. Ini penting sebagai transparency device, supaya reader langsung tahu apakah BRIDS lebih bullish atau bearish dibanding consensus sebelum baca detail thesis.

**Exhibit 2\. Chart "\[TICKER\] relative to JCI Index"**  
 Chart dual-axis: LHS untuk harga saham absolut (line, biasanya warna navy pekat), RHS untuk relative performance terhadap JCI dalam persen (line kedua, warna lebih terang/abu). Periode tampilan: 1-2 tahun trailing dari tanggal publikasi (konsisten dengan pola BBTN dan MAPA yang pakai window sekitar 18-24 bulan). Sumbu X pakai label bulan-tahun singkat (contoh: "Sep-24", "Nov-24"). Ini chart yang butuh price time series data granular, jadi salah satu titik krusial dependency ke sumber data pihak ketiga yang perlu dipastikan reliable untuk ticker Indonesia.

**Footer sidebar**  
Nama analis (bold), title "Equity Analyst" di bawahnya,.

#### **Main Content Kanan (\~70% lebar halaman)**

**Header perusahaan**  
 Nama perusahaan lengkap \+ "(TICKER IJ)" dalam font besar bold navy, diikuti judul tema laporan di bawahnya sebagai subheading (italic atau warna berbeda), contoh pola dari MAPA: "Conservative Guidance, Sustained Growth Ahead". Judul ini harus mencerminkan thesis utama report, bukan generic title.

**3 bullet highlights**  
 Bullet point bold, masing-masing satu kalimat padat berisi klaim kuantitatif utama. Pola dari BBTN: bullet pertama tentang hasil kuartal terakhir vs ekspektasi, bullet kedua tentang driver spesifik, bullet ketiga tentang rating action dan TP. Ini adalah eksekutif summary paling atas, jadi harus bisa berdiri sendiri kalau reader cuma baca 3 baris ini saja.

**Paragraf 1 \- Kinerja Keuangan**  
 Subheading bold sebelum paragraf (contoh pola dari existing report: "Strong earnings growth driven by lower CoC"). Isi paragraf: buka dengan angka net profit/revenue aktual periode terkini dibanding periode sebelumnya (qoq) dan tahun lalu (yoy), sebutkan berapa persen dari estimasi FY BRIDS dan consensus yang sudah tercapai (running rate check), lalu breakdown driver utama (margin movement, volume growth, cost item spesifik), tutup dengan positioning terhadap full-year guidance management kalau ada. Setiap klaim kuantitatif harus attached ke angka eksplisit, tidak ada kalimat seperti "kinerja membaik" tanpa angka pendukung.

**Paragraf 2 \- News, Sentimen, Katalis**  
 Subheading bold terpisah. Isi: identifikasi katalis konkret yang relevan dalam periode pelaporan (bisa dari news flow, corporate action, kebijakan regulator, atau perubahan asumsi makro), kuantifikasi dampaknya ke earnings atau valuasi kalau ada basis perhitungan (contoh format kalimat: "Kami estimasi dampak kenaikan tarif ini terhadap net profit FY26F sebesar \+3-4%"), dan tutup dengan assessment apakah pasar sudah price-in katalis tersebut atau belum, dilihat dari pergerakan harga saham relatif ke sektor/JCI.

**Paragraf 3 \- Valuasi**  
 Subheading bold. Struktur kalimat wajib empat elemen:

1. Kalimat metodologi: "Kami mempertahankan/menaikkan/menurunkan TP menjadi Rp\[X\] menggunakan \[DCF/GGM/SOTP/RNAV\], dengan asumsi \[parameter kunci: WACC/CoE/exit multiple\] sebesar \[Y\]%."  
2. Kalimat linkage forecast: "TP ini mengimplikasikan pertumbuhan \[EBITDA/Revenue\] CAGR FY26-28F sebesar \[Z\]%, didukung oleh \[driver utama, sebutkan spesifik\]."  
3. Kalimat trading multiple: "Pada TP tersebut, saham diperdagangkan pada \[PER/PBV/EV-EBITDA\] 26F sebesar \[N\]x, dibandingkan dengan rata-rata historis 5 tahun sebesar \[M\]x atau rata-rata peers sebesar \[P\]x."  
4. Kalimat risk to view (opsional tapi disarankan): sebutkan satu-dua risiko konkret yang bisa membuat TP tidak tercapai, dengan arah dampaknya jelas (upside risk atau downside risk).

**Exhibit 3\. Key Financials table**  
 Kolom: 2024A, 2025A, 2026F, 2027F, 2028F (dua tahun aktual, tiga tahun forecast, selalu rolling forward setiap tahun publikasi berganti). Baris: Revenue, EBITDA, EBITDA Growth (%), Net Profit, EPS, EPS Growth (%), PER (x), PBV (x), EV/EBITDA (x). Header row shading navy dengan teks putih, angka rata kanan, satu desimal untuk multiple (x) dan persentase, tanpa desimal untuk angka Rpbn absolut kecuali EPS yang butuh satu desimal.

---

### **SLIDE 2 — Kondisi Industri dan Katalis/Sentimen Emiten**

Tidak ada tabel/chart wajib di slide ini secara default (murni narasi tiga paragraf), tapi kalau ada data pendukung visual (misal sector growth trend chart atau fund flow chart), tetap ikut aturan Exhibit sequential dan wajib source line.

**Paragraf 1 \- Kondisi Industri**  
 Buka dengan snapshot kondisi sektor secara makro: growth rate sektor tahun berjalan dan/atau forecast (dalam persen, dari data BPS/asosiasi industri/riset internal), demand-supply balance kalau relevan (contoh: utilization rate industri, oversupply/undersupply signal), backdrop makro yang paling material ke sektor tersebut (bisa suku bunga untuk banking/property, nilai tukar untuk emiten net importer/exporter, harga komoditas untuk mining/plantation, atau perubahan daya beli untuk consumer). Tutup paragraf dengan positioning emiten yang dicover relatif terhadap tren sektor ini, apakah dia outperform, in-line, atau underperform sektornya, dan alasan strukturalnya.

**Paragraf 2 \- Katalis Spesifik Emiten**  
 Fokus ke katalis yang applicable langsung ke emiten yang dicover, bukan katalis generik sektor. Contoh kategori katalis: perubahan regulasi (POJK, OJK, Bank Indonesia, kebijakan Kementerian terkait), siklus harga komoditas untuk emiten yang exposure ke commodity price, rencana ekspansi kapasitas atau capex besar, aktivitas konsolidasi/M\&A di sektor yang bisa mengubah competitive landscape. Setiap katalis yang disebut harus, kalau memungkinkan, dikuantifikasi dampaknya (ke earnings, margin, atau volume emiten), dengan basis perhitungan yang jelas, bukan asumsi tanpa dasar. Kalau tidak ada basis data untuk kuantifikasi, state itu sebagai kualitatif eksplisit, jangan dipaksa kasih angka.

**Paragraf 3 \- Sentimen Pasar**  
 Fokus murni ke bagaimana pasar sedang memandang sektor dan emiten ini saat ini, tanpa menyentuh valuasi atau target price sama sekali (itu domain Slide 4-5). Elemen yang bisa dibahas: net buy/sell asing atau domestik di sektor terkait (kalau data tersedia dari KSEI atau Bloomberg), pergerakan saham atau indeks sektor relatif terhadap JCI dalam periode berjalan (bisa refer ke Exhibit 2 di Slide 1 kalau relevan), tone pemberitaan media terhadap sektor (positif/negatif/netral, dengan sedikit konteks kenapa), dan agregat consensus rating di sektor tersebut (berapa banyak broker yang Buy/Hold/Sell untuk saham-saham di sektor ini, sebagai proxy risk appetite investor institusional).

---

### **SLIDE 3 — Visualisasi Kinerja Keuangan dan Forecasting**

Layout grid 2x2, masing-masing kuadran berisi satu chart plus blok narasi pendamping (baik di bawah chart atau di sampingnya tergantung ruang, tapi harus menempel visual dengan chart-nya masing-masing, bukan narasi terpisah di ujung slide).

**Exhibit 4\. Revenue & Revenue Growth**  
 Chart combo: bar untuk Revenue absolut (Rpbn) periode 2024A-2028F, line untuk growth yoy (%) di secondary axis. Warna bar navy solid untuk data aktual, navy dengan pattern/opacity lebih rendah untuk data forecast (supaya visual langsung membedakan aktual vs proyeksi tanpa perlu baca label).  
 Narasi (2-3 kalimat): identifikasi driver utama pertumbuhan atau penurunan revenue di tiap periode signifikan, bandingkan CAGR historis (2024A-2025A) dengan CAGR forecast (2026F-2028F) dan jelaskan kalau ada perbedaan laju yang material, flag inflection point kalau ada (contoh: growth melambat tajam di satu tahun forecast karena base effect tinggi atau selesainya periode ekspansi kapasitas).

**Exhibit 5\. EBITDA & EBITDA Margin**  
 Chart combo serupa: bar EBITDA (Rpbn), line EBITDA margin (%) secondary axis.  
 Narasi: jelaskan arah trajectory margin (ekspansi atau kontraksi) dan penyebab strukturalnya (cost structure shift, pricing power, operating leverage dari fixed cost absorption), bandingkan level margin forecast dengan rata-rata historis 3-5 tahun sebagai sanity check apakah asumsi margin forecast realistis atau terlalu optimis/pesimis dibanding track record perusahaan.

**Exhibit 6\. Net Profit & EPS Growth**  
 Chart combo: bar Net Profit (Rpbn), line EPS growth (%) secondary axis.  
 Narasi: bandingkan laju growth net profit/EPS dengan laju growth revenue dan EBITDA di dua chart sebelumnya, kalau ada gap material (misal EBITDA growth 15% tapi net profit growth cuma 5%), wajib jelaskan below-the-line item penyebabnya secara eksplisit (kenaikan tax rate efektif, beban bunga naik karena leverage tambahan, minority interest, atau kerugian/keuntungan kurs).

**Exhibit 7\. Chart keempat (switchable by sector)**

* Default non-bank: DER (bar, x) vs ROE (line, %) \- untuk menilai apakah pertumbuhan yang diproyeksikan didanai dengan leverage yang sehat atau berisiko meningkatkan financial risk berlebihan.  
* Bank: NIM (%) dan Cost of Credit (%) trend, atau alternatif NPL/LaR ratio trend, karena ini driver utama profitabilitas emiten bank, bukan leverage dalam pengertian umum.  
* E\&P/upstream: production volume (bar) dan lifting cost per barrel/boe (line), karena revenue emiten E\&P tidak bisa dianalisis lewat leverage sederhana, harus lihat volume dan cost structure produksi.  
* Sektor lain (property, plantation) perlu penyesuaian serupa sesuai driver utama earnings masing-masing, didiskusikan case-by-case saat build.

Semua data di Slide 3 harus tie-out langsung dengan Exhibit 3 (Key Financials Slide 1), tidak boleh ada angka yang berbeda antara dua exhibit ini untuk periode yang sama.

---

### **SLIDE 4 — Valuasi Intrinsik (DCF/DDM/RNAV)**

Metode dipilih manual oleh analis berdasarkan karakteristik emiten (bank pakai DDM, property/resources pakai RNAV, general corporate pakai DCF), bukan otomatis dari sistem. Struktur berikut generik, hanya satu opsi yang aktif per report sesuai emiten yang dicover.

#### **Opsi A — DCF (FCFF-based)**

**Exhibit 8\. FCFF Forecast and Terminal Value**  
 Satu tabel gabungan dengan tiga blok:

*Blok 1 \- Explicit forecast period (5 tahun: umumnya tahun berjalan \+4 forecast tahun ke depan)*: baris berurutan Revenue, EBIT, Tax on EBIT (dihitung EBIT x (1-effective tax rate), bukan tax rate statutory), NOPAT, (+) Depreciation & Amortization, (-) Capital Expenditure, (-)/(+) Increase/Decrease in Net Working Capital, **FCFF** (subtotal bold), FCFF growth (%) yoy, Discount Factor (1/(1+WACC)^n), **PV of FCFF** (bold).

*Blok 2 \- Terminal value*: Terminal FCFF (FCFF tahun terakhir forecast x (1+terminal growth)), Terminal Growth (g) dinyatakan eksplisit sebagai asumsi (biasanya di-cap tidak lebih tinggi dari long-term GDP growth atau risk-free rate, sesuai prinsip yang sudah Anda pegang), Terminal Value undiscounted, Discount Factor terminal, **PV of Terminal Value**. Kalau dilakukan cross-check dua metode (Gordon Growth vs Exit Multiple), tampilkan berdampingan sebagai dua kolom terpisah dalam blok yang sama.

*Blok 3 \- Bridge ke equity value*: Sum PV of FCFF (explicit period), (+) PV of Terminal Value, **Enterprise Value** (bold), (-) Net Debt (Total Debt \- Cash & Equivalents pada tanggal valuasi), (+/-) Minority Interest dan/atau Non-Operating Assets, **Equity Value** (bold), dibagi jumlah saham beredar, **Fair Value per Share** (bold, highlight).

**Exhibit 9\. WACC Components**  
 Tabel dua kolom (parameter, nilai): Cost of Equity dihitung via CAPM (Risk-free rate, Beta, Equity Risk Premium, hasil Cost of Equity), Cost of Debt (pre-tax cost of debt dari rata-rata kupon obligasi/pinjaman existing, tax rate efektif, after-tax cost of debt), Capital Structure (Weight of Debt \= D/(D+E), Weight of Equity \= E/(D+E), berdasarkan market value bukan book value kalau memungkinkan), hasil akhir **WACC** di baris paling bawah, bold.

**Exhibit 10\. Sensitivity Analysis**  
 Grid matrix: baris WACC (rentang misal \-1%, \-0.5%, base, \+0.5%, \+1% dari WACC yang dipakai), kolom Terminal Growth atau Exit Multiple (rentang serupa), isi cell adalah Fair Value per Share hasil kombinasi tersebut. Base case (WACC dan growth yang dipakai di Exhibit 8\) di-highlight beda warna supaya mudah dilihat reader.

**Narasi (di bawah ketiga exhibit, satu blok terpadu)**: sebutkan parameter mana yang paling sensitif terhadap valuasi (biasanya terminal growth di DCF perpetual), justifikasi asumsi growth/margin di forecast FCFF dikaitkan ke driver bisnis riil yang sudah dibahas di Slide 2-3 (bukan angka yang berdiri sendiri tanpa linkage), dan kalau ada gap material antara hasil Gordon Growth dan Exit Multiple, itu wajib di-flag eksplisit sebagai unresolved assumption yang perlu disclosure ke reader, bukan dirata-rata diam-diam.

#### **Opsi B — DDM (bank/institusi keuangan)**

**Exhibit 8\. Dividend Forecast and Terminal Value**  
 Blok 1 explicit period: Net Profit, Payout Ratio (%) asumsi berdasarkan historical payout perusahaan atau kebijakan dividen yang diumumkan, **DPS**, DPS growth (%), Discount Factor (menggunakan Cost of Equity bukan WACC karena DDM adalah equity valuation langsung), **PV of DPS**.  
 Blok 2 terminal value: Terminal DPS, Terminal Growth, Terminal Value, PV of Terminal Value, **Fair Value per Share** (Gordon Growth formula: Terminal DPS x (1+g) / (CoE-g)).  
 Jalur alternatif (kalau BRIDS pakai Inverse Cost of Equity method seperti pola BBTN di project): tambahkan baris Forward ROE (biasanya FY26F ROAE), Fair Value P/BV \= (ROAE \- g) / (CoE \- g), BVPS (book value per share forecast), **Fair Value \= Fair Value P/BV x BVPS**.

**Exhibit 9\. Cost of Equity Components**  
 Kalau pakai CAPM: Risk-free rate, Beta, ERP, Cost of Equity hasil. Kalau pakai band method (pola BBTN): Cost of Equity mean 5-tahun, Cost of Equity SD 5-tahun, jumlah SD yang dipakai dari mean (contoh: mean atau \-0.5SD tergantung view terhadap risiko), Cost of Equity yang dipakai di valuasi.

**Exhibit 10\. Sensitivity Analysis**  
 Grid Cost of Equity x Long-term Growth, atau Cost of Equity x Forward ROE kalau pakai Inverse CoE method, isi cell Fair Value per Share.

**Narasi**: fokus ke ROE trajectory sebagai driver utama (bukan cash flow generation seperti DCF), dan sustainability payout ratio ke depan mengingat kebutuhan modal untuk pertumbuhan kredit/aset bank.

#### **Opsi C — RNAV (property/plantation/resources dengan aset dominan)**

**Exhibit 8\. Asset Breakdown and RNAV Bridge**  
 Blok 1 per-aset: daftar aset/proyek/tambang/landbank, dengan kolom nama aset, ukuran (landbank hectare, cadangan ton/barrel, atau kapasitas produksi tergantung jenis aset), NAV per aset (hasil DCF per proyek atau appraisal value pihak independen), persentase kepemilikan emiten di aset tersebut, NAV attributable ke emiten (NAV per aset x % kepemilikan).  
 Blok 2 bridge: Sum of NAV seluruh aset, (+) Cash & Equivalents, (-) Total Debt, (-) Corporate overhead (PV dari biaya korporat yang tidak attributable ke aset spesifik), **Total RNAV** (bold), dibagi jumlah saham, **RNAV per share**, (-) Discount to RNAV (%) sebagai judgment call analis, **Target Price** (bold, highlight) \= RNAV per share x (1 \- discount%).

**Exhibit 9\. Discount Rate per Aset**  
 Kalau tiap proyek/aset di-valuasi dengan DCF masing-masing yang punya risk profile berbeda, tabel ini breakdown WACC/discount rate per aset (bisa beda signifikan antara proyek matang vs proyek development stage).

**Exhibit 10\. Sensitivity Analysis**  
 Grid Discount to RNAV (%) x Discount rate/WACC, atau kalau driver utama adalah harga komoditas/properti, grid Discount to RNAV x asumsi harga jual per unit.

**Narasi**: besaran discount to RNAV yang dipakai wajib dijustifikasi eksplisit, idealnya dengan basis pembanding (level discount historis emiten sejenis, atau rata-rata discount sektor), kalau tidak ada basis pembanding, state itu sebagai pure judgment assumption, jangan dipresentasikan seolah angka final tanpa dasar.

**Catatan lintas ketiga opsi**: semua komponen Risk-free rate, Beta, ERP harus dicatat sumbernya (INDOGB 10Y untuk Rf IDR, US Treasury untuk Rf USD kalau emiten functional currency USD seperti kasus GMFI, Damodaran untuk ERP, Bloomberg untuk Beta), supaya traceable saat direview internal maupun eksternal. Kasus khusus E\&P/PSC company perlu modifikasi tambahan dari Opsi A standar karena perpetual growth DCF secara teoritis tidak defensible untuk aset dengan cadangan terbatas (finite reserve life), sesuai prinsip yang sudah established sebelumnya, perlu didiskusikan terpisah kalau ada emiten E\&P yang akan pakai template ini.

---

### **SLIDE 5 — Peer Valuation & Historical Relative Valuation**

Slide ini terbagi dua metodologi berbeda filosofi (cross-sectional vs time-series), wajib dipisah tegas secara visual dengan divider atau section header, supaya reader tidak salah interpretasi bahwa keduanya saling mengonfirmasi satu kesimpulan yang sama.

#### **Bagian Atas (\~50%) — Peer Valuation Table**

**Exhibit 11\. Peer Valuation Table**  
 Kolom: nama perusahaan \+ ticker, P/E (x), PBV (x), EV/EBITDA (x), opsional ROE (%) dan Market Cap sebagai kolom konteks tambahan kalau ruang memungkinkan. Periode data: FY26F dan/atau LTM (Last Twelve Months), harus konsisten dipakai di semua baris. Baris penutup di bawah daftar peers: **Median** dan **Average** dari seluruh peer set (dua baris terpisah, bold, dengan sedikit spasi/garis pemisah dari baris peer individual). Baris emiten yang dicover di-highlight beda warna/shading supaya langsung terlihat posisinya relatif terhadap median/average tanpa perlu scanning manual.

Kriteria pemilihan peer set harus eksplisit dan defensible, dicantumkan minimal di source line tambahan atau footnote: kesamaan sektor/sub-sektor, rentang market cap yang sebanding, dan "as of" date data harga yang dipakai (karena multiple berbasis harga berubah setiap hari, perlu tanggal cut-off yang jelas).

**Narasi (2-3 kalimat)**: state posisi emiten relatif ke median dan average peer set (contoh: "MAPA saat ini diperdagangkan pada PER 26F 9.0x, diskon X% terhadap median peer sebesar Yx"), lalu justifikasi kenapa premium atau discount tersebut wajar atau tidak wajar, dikaitkan ke fundamental differential yang konkret (kualitas earnings, growth rate relatif, ROE gap, atau risk profile berbeda), bukan sekadar menyatakan angka gap tanpa penjelasan.

#### **Bagian Bawah (\~50%) — Relative Valuation Historical (Own-History Tool)**

Blok deskripsi metodologi ditampilkan sebagai teks pendek (bisa dipersingkat dari versi lengkap tapi substansi tetap sama): tool ini adalah own-history relative valuation, menghitung empat trailing multiple (P/E, P/BV, EV/EBITDA, EV/Sales) sepanjang window satu tahun, membandingkan level saat ini terhadap distribusi historisnya sendiri (average, median, persentil). Item laporan keuangan dikonversi ke mata uang harga untuk emiten yang melapor dalam mata uang berbeda dari harga sahamnya, driver fundamental dibangun dengan rolling TTM plus fallback berlapis untuk mengatasi data gap, dan sistem scoring rule-based memilih multiple mana yang paling relevan ditampilkan berdasarkan karakteristik sektor, stabilitas historis multiple tersebut, dan validitas driver fundamentalnya.

**Exhibit 12\. P/E Historical Band (1-Year)**  
 Chart line P/E trailing sepanjang 1 tahun, dengan garis horizontal mean dan garis horizontal median (dua garis berbeda style, misal dashed untuk mean dan dotted untuk median), plus marker khusus (dot atau diamond) menandai level P/E saat ini di titik paling kanan chart.

**Exhibit 13\. P/BV Historical Band (1-Year)**  
 Format serupa Exhibit 12, untuk P/BV.

**Implied Price Judgement**  
 Tampilkan minimal dua metode implied price secara eksplisit dalam bentuk angka: (1) implied price dari reversion ke mean 1-tahun, dan (2) implied price dari reversion ke median 1-tahun, untuk minimal dua multiple (P/E dan P/BV sebagai default, ditambah EV/EBITDA atau EV/Sales kalau sistem scoring rule-based memilih multiple tersebut sebagai paling relevan untuk emiten spesifik ini). Semua implied price dihitung dengan asumsi driver fundamental (EPS, BVPS, EBITDA, atau Revenue tergantung multiple) tetap konstan di level TTM/forward saat ini, hanya multiple yang direversi ke mean/median historis.

**Narasi (per chart/metode, bukan satu paragraf gabungan)**: untuk tiap chart, sebutkan di persentil berapa posisi multiple saat ini dari distribusi 1 tahun (contoh: "P/E saat ini berada di persentil 25 dari distribusi 1 tahun, mengindikasikan valuasi relatif murah terhadap sejarah dirinya sendiri"), lalu sebutkan angka implied price eksplisit dari reversion ke mean dan ke median secara terpisah, kalau kedua angka ini berbeda material satu sama lain, presentasikan sebagai range bukan angka tunggal supaya tidak memberi kesan false precision.

Disclaimer eksplisit wajib dicantumkan di bagian ini: implied price dari tool ini adalah cross-check mean-reversion berbasis multiple historis, bukan Target Price resmi yang sudah ditetapkan di Slide 4, dan berbasis asumsi driver fundamental konstan (bukan forecast forward earnings/BVPS), sehingga sifatnya snapshot bukan proyeksi.

---

### **SLIDE 6 — Income Statement & Balance Sheet**

Dua exhibit di-stack dalam satu slide, format tabel konsisten dengan pola BBTN Exhibit 7-8 di project (header row shading navy dengan teks putih, angka rata kanan, kolom tahun di header row).

**Exhibit 14\. Income Statement**  
 Kolom: 2024A, 2025A, 2026F, 2027F, 2028F. Baris berurutan: Revenue/Sales, Cost of Goods Sold (dalam kurung sebagai deduction), **Gross Profit** (bold subtotal), Operating Expenses/SG\&A (dalam kurung), **EBIT** (bold subtotal), Interest Income, Interest Expense (dalam kurung), Other Income/(Expense) non-operating, **Pre-tax Profit** (bold subtotal), Income Tax (dalam kurung), Minority Interest, **Net Profit** (bold, highlight sebagai baris paling penting).

**Exhibit 15\. Balance Sheet**  
 Kolom sama. Bagian Assets: Cash & Cash Equivalents, Trade Receivables, Inventory, Other Current Assets, **Total Current Assets** (subtotal), Fixed Assets (Net), Other Non-Current Assets, **Total Assets** (bold). Bagian Liabilities & Equity: Short-term Debt, Trade Payables, Other Current Liabilities, **Total Current Liabilities** (subtotal), Long-term Debt, Other Non-Current Liabilities, **Total Liabilities** (bold subtotal), Shareholders' Equity, **Total Liabilities & Equity** (bold, harus sama persis dengan Total Assets sebagai balance check).

Format ini untuk emiten non-bank/general corporate. Untuk emiten bank, struktur ini diganti total mengikuti pola BBTN (Interest Income, Interest Expense, Net Interest Income, Non-Interest Income, PPOP, Provisions & Allowances menggantikan struktur Income Statement di atas; dan struktur Balance Sheet bank pakai Gross Loans, Provisions, Net Loans, Govt Bonds, Securities, Total Earning Assets, Customer Deposits, Shareholders' Funds, sesuai pola Exhibit 7-8 BBTN persis).

---

### **SLIDE 7 — Cash Flow & Key Ratio**

**Exhibit 16\. Cash Flow Statement**  
 Kolom sama 5-tahun. Struktur tiga section:  
 *Cash Flow from Operations*: Net Profit, (+) Depreciation & Amortization, (-)/(+) Increase/Decrease in Working Capital, Other Operating Items, **Net Cash from Operations** (bold subtotal).  
 *Cash Flow from Investing*: (-) Capital Expenditure, Other Investing Items, **Net Cash from Investing** (bold subtotal, biasanya negatif).  
 *Cash Flow from Financing*: Debt Raised/(Repaid), Dividends Paid (dalam kurung), Equity Raised/(Buyback), **Net Cash from Financing** (bold subtotal).  
 Penutup: **Net Change in Cash**, Beginning Cash Balance, **Ending Cash Balance** (harus match dengan Cash & Cash Equivalents di Balance Sheet Exhibit 15 periode yang sama).  
 Baris memo tambahan di bawah garis pemisah: **Free Cash Flow** \= Net Cash from Operations \- Capital Expenditure, dipakai sebagai cross-check langsung ke FCFF di Exhibit 8 Slide 4 kalau metode DCF yang dipakai (kedua angka ini tidak identik karena FCFF pakai NOPAT bukan Net Profit, tapi harus dalam ballpark yang masuk akal, kalau selisihnya ekstrem perlu dicek ulang).

**Exhibit 17\. Key Ratio**  
 Format persis mengikuti contoh Exhibit 44 yang sudah Anda kirim, dengan tiga section:  
 *Growth (%)*: Sales, EBITDA, Operating Profit, Net Profit, masing-masing yoy growth per tahun (2024A ke 2025A adalah growth aktual, seterusnya forecast).  
 *Profitability (%)*: Gross Margin, EBITDA Margin, Operating Margin, Net Margin, ROAA, ROAE.  
 *Leverage*: Net Gearing (x) \= (Total Debt \- Cash) / Total Equity, Interest Coverage (x) \= EBIT / Interest Expense.

Format angka: satu desimal konsisten di semua baris, angka negatif ditulis dalam kurung bukan tanda minus (konsisten dengan konvensi sell-side yang sudah dipakai di contoh Anda), section header (Growth, Profitability, Leverage) bold dengan sedikit spasi ekstra sebelum section dimulai untuk visual separation.

Format ini untuk non-bank. Emiten bank sector-switch total ke pola BBTN Exhibit 9-10: Yield on Earning Assets, Cost of Funds, Interest Spread, Net Interest Margin, Cost/Income Ratio, Gross NPL Ratio, LLP/Gross NPL coverage, Cost of Credit, Loan to Deposit Ratio, CASA Mix, ROAE, ROAA, CAR, ditambah Dupont breakdown (Pre-Tax ROAA, Tax Retention Rate, Post-Tax ROAA, Leverage, ROAE) sebagai exhibit tambahan kalau ruang memungkinkan, atau dipecah jadi Exhibit terpisah kalau tidak muat satu slide dengan Cash Flow.

**Catatan tie-out wajib**: Net Profit di Exhibit 14 (Income Statement) harus identik dengan Net Profit di Exhibit 3 (Key Financials Slide 1\) dan menjadi starting point di Exhibit 16 (Cash Flow). Ending Cash Balance di Exhibit 16 harus identik dengan Cash & Equivalents di Exhibit 15 (Balance Sheet) untuk periode yang sama. Mismatch di titik manapun adalah sinyal error link antar-sheet di model Excel yang harus diperbaiki sebelum publish, bukan dianggap rounding difference kecuali memang benar-benar immaterial (di bawah 0.1%).


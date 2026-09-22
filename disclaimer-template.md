# Disclaimer template (rules §12 compliance)

> Rules §12 require that "projects must not provide financial advice. Products must position themselves as information and analysis tools, not investment recommendations. Include a disclaimer where relevant."

## F1 audit gap that motivated this file

Gap **G-8**: "Disclaimer template — Rules §12 require 'include a disclaimer where relevant'. No boilerplate disclaimer is provided. Recipe `human-agent-framework.md` recommends writing one but doesn't give wording."

## Boilerplate (Bahasa Indonesia — primary, for IDX audience)

Copy this verbatim into the footer of every product surface (web app, Telegram bot message footer, README). Adjust the "Telegram" / "aplikasi" wording to match your surface.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ INFORMASI, BUKAN SARAN INVESTASI

Asing Radar (atau nama produk lo) adalah alat informasi dan analisis
data pasar modal Indonesia berdasarkan data dari Sectors Financial API.
Semua output adalah data historis dan agregat, bukan rekomendasi,
prediksi, atau saran investasi.

Keputusan investasi sepenuhnya tanggung jawab pembaca. Selalu lakukan
riset mandiri dan konsultasikan dengan penasihat keuangan berlisensi
sebelum berinvestasi. Performa masa lalu tidak menjamin hasil di masa
depan.

Data yang ditampilkan bersumber dari Sectors (https://sectors.app) dan
IDX. Akurasi data tunduk pada kualitas data sumber.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Boilerplate (English — for non-IDX surface, fallback)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ INFORMATION, NOT INVESTMENT ADVICE

[Product Name] is an information and analysis tool for Indonesian
capital-market data sourced from the Sectors Financial API. All
outputs are historical and aggregate — not recommendations,
predictions, or investment advice.

Investment decisions are the reader's sole responsibility. Always
perform independent research and consult a licensed financial advisor
before investing. Past performance does not guarantee future results.

Data is sourced from Sectors (https://sectors.app) and IDX. Data
accuracy is subject to source quality.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Where to display

**Always:**
- Footer of any web app
- Last line of any Telegram bot message
- README.md "Disclaimer" section

**Conditionally:**
- Email reports / digests
- PDF exports (printed footer)
- Social media post (if the product has its own account)

## When NOT to display

- Internal dev logs (gak perlu diulang tiap console.log)
- Doc comments in source code
- The submission portal form fields

## Anti-patterns to avoid

- ❌ Burying the disclaimer in a Terms of Service link. Judges read the disclaimer when it's visible on the product surface.
- ❌ Generic disclaimer copied from a US/EU product ("not FDIC insured"). IDX retail doesn't relate to that.
- ❌ Disclaimer that contradicts the product's framing. If your Telegram bot says "RECOMMENDED BUY" in all caps and the disclaimer says "bukan saran investasi", judges will catch the contradiction.
- ❌ Translating the disclaimer with a machine translator. The Bahasa Indonesia wording above has been reviewed for the IDX retail audience — use it.

## Cross-link

This file is referenced from the Asing Radar recommendation in `tracks/idea-scoring.md` and from any Track 01 agent product where the LLM could be interpreted as making recommendations.

# Valuation Method Selection Framework

A structured decision logic for choosing between DCF, DDM, NAV, SOTP, and Relative Valuation before financial modeling. 6 sequential gates (0–5), evaluated in order from business-model fundamentals to output sanity.

Source: house working document on valuation method selection (archived in `references/framework-valuation.pdf`).

This document covers **why method selection matters, what each gate decides, and how our code maps to them**. The deterministic implementation lives in [`agents/valuation/gates.py`](file:///home/fadil/projects/sectors-hackathon/agents/valuation/gates.py); the orchestrator wiring is in [`agents/adk/agents/instructions.py`](file:///home/fadil/projects/sectors-hackathon/agents/adk/agents/instructions.py).

---

## 1. Intro - Why Method Selection Matters

> "These five methods are not competing alternatives to be averaged together. Each has a domain where it is structurally correct and domains where it produces a confident-looking number that has no economic meaning. The most common valuation error is forcing one method, usually DCF because it looks the most rigorous, onto a company where its core assumptions do not hold."
> - *Valuation Method Selection Framework (house working document)*

The logic is ordered from the most fundamental gate (what kind of business is this) down to finer checks (data quality, ownership structure, cyclicality, life-cycle stage, and output sanity). A company passes through every gate in sequence; failing a gate does not always mean rejection - sometimes the primary method changes, and sometimes a mandatory second method is attached alongside the first.

- **Gates 0–4** determine which method should be used as the primary valuation and attach cross-check requirements.
- **Gate 5** is applied after a DCF has already been computed, catching cases where specific assumption combinations produce unrealistic outputs.

---

## 2. The 6 Gates

| Gate | Question | Method | Source (`agents/valuation/gates.py`) |
|---|---|---|---|
| **0 - Business Model** | How does this company make money? Does the concept of "operating free cash flow" even apply? | Financials (bank/insurance/multifinance/securities) → **DDM / Excess Return**<br>REIT / property investment vehicle → **NAV**<br>Mining / oil & gas / plantation (finite reserves) → **NAV / Reserve-based**<br>Holding company with dissimilar business lines → **SOTP**<br>Non-financial single business line going concern → **FCFF/WACC DCF candidate** (proceed to Gate 1) | [`_gate0_business_model`](file:///home/fadil/projects/sectors-hackathon/agents/valuation/gates.py#L55) |
| **1 - Data Eligibility** | Do we have sufficient history, profitability, leverage sanity, and equity base to compute a defensible DCF? | **1a. Filing history ≥ 4y**: If < 4y → **DCF (shortened horizon)** + mandatory `⚠ Thin Data` disclosure banner.<br>**1b. Operating profitability**: EBIT positive in ≥ 2 of last 3y. If failed → **Relative Valuation (EV/Sales / Price/Sales)**.<br>**1c. Capital structure**: D/(D+E) ≤ 80%, Net Debt/EBITDA ≤ 6x, ICR ≥ 1x. If breached → DCF proceeds with **mandatory Relative Valuation cross-check**.<br>**1d. Equity base**: Positive shareholders' equity. If negative → **EV-based multiples only** (P/E and P/BV invalid). | [`_gate1_data_eligibility`](file:///home/fadil/projects/sectors-hackathon/agents/valuation/gates.py#L81) |
| **2 - Ownership Structure** | Is non-controlling interest (NCI) large enough that a consolidated DCF bridge diverges from real economic value? | **NCI ≤ 15%**: FCFF/WACC DCF proceeds normally.<br>**15% < NCI ≤ 40%**: DCF proceeds with **mandatory SOTP cross-check**.<br>**NCI > 40%**: **SOTP primary**; consolidated DCF is rough reference only. | [`_gate2_ownership_structure`](file:///home/fadil/projects/sectors-hackathon/agents/valuation/gates.py#L144) |
| **3 - Cyclicality Character** | Is revenue volume-driven or priced off a mean-reverting global commodity cycle? | **Unit volume-driven (consumer, manufacturing, retail)**: FCFF/WACC DCF primary.<br>**Commodity price-driven (coal, nickel, CPO, oil)**: **NAV / Reserve-based primary**, DCF with explicit long-run price deck secondary.<br>**Newly commissioned / ramping (<3y steady-state)**: **Forward Relative Valuation primary** (forward EV/EBITDA at target capacity vs mature peers). | [`_gate3_cyclicality`](file:///home/fadil/projects/sectors-hackathon/agents/valuation/gates.py#L168) |
| **4 - Life-Cycle Stage** | What is the operational maturity and growth stage of the business? | **Pre-revenue / early growth**: EV/Sales primary, long-horizon DCF secondary.<br>**High growth, pre-profit**: EV/Sales primary + DCF with margin fade to long-run target.<br>**Mature, stable, predictable**: **FCFF/WACC DCF primary**.<br>**Decline / turnaround**: **P/BV or NAV primary**, DCF secondary. | [`_gate4_life_cycle`](file:///home/fadil/projects/sectors-hackathon/agents/valuation/gates.py#L209) |
| **5 - Output Sanity Check** | Did the computed DCF produce an output that violates fundamental economic reality? | **Upside > 100% or downside < -50% vs market**: Rating **auto-overridden to "Review Required"** (points to SOTP/NAV/RelativeVal cross-checks).<br>**Terminal Value > 80% of Enterprise Value**: DCF flagged for implied exit-multiple or Relative Valuation cross-check (no rating override).<br>**Implied exit EV/EBITDA outside range**: Flagged for peer EV/EBITDA cross-check. | [`_gate5_output_sanity`](file:///home/fadil/projects/sectors-hackathon/agents/valuation/gates.py#L234) |

Top-level deterministic orchestrator: [`evaluate()`](file:///home/fadil/projects/sectors-hackathon/agents/valuation/gates.py#L277) executes gates 0 through 5 sequentially.

---

## 3. Decision Log - User-Decided Deltas

Two specific adaptations were established vs the source working paper (recorded in [`docs/DECISIONS.md`](file:///home/fadil/projects/sectors-hackathon/docs/DECISIONS.md)):

### Delta 1: Gate 1 thin-data fallback = shortened DCF + disclosure (NOT pure Relative)
- **User Decision (2026-09-04)**: When a ticker has < 4 years of filing history (e.g., CDIA), the gate runner defaults to **DCF with a shorter explicit horizon** (e.g. 5-year explicit horizon + terminal value) accompanied by a mandatory `"⚠ Thin Data"` disclosure banner on the PDF cover.
- **Rationale**: Pure Relative Valuation produces no defensible intrinsic fair value (merely reflecting peer averages); shortened DCF + honest disclosure preserves the fundamental financial math while transparently surfacing the data limitation to institutional readers.
- **Rejected Alternatives**: (a) Pure Relative Valuation - lacks an actionable intrinsic anchor; (b) Skipping DCF entirely - discards valuable projection modeling.

### Delta 2: Gate 5 auto-override rating to "Review Required" for extreme valuations
- **User Decision (2026-09-04)**: When valuation upside > 100% or downside < -50% vs observable market price, the investment rating is **automatically overridden to "Review Required"** regardless of the nominal BUY/HOLD/SELL arithmetic.
- **Rationale**: Extreme upside or downside indicates that underlying assumption combinations (e.g. WACC, perpetual growth, margin expansion) require human analyst reconciliation against SOTP, NAV, or peer multiples before release. High Terminal Value share (> 80% of EV) is explicitly flagged but does *not* override the rating.

---

## 4. Quintet Verdicts

End-to-end audit verified against the 5 benchmark hackathon tickers with realistic operational parameters:

| Ticker | Primary | Secondary | Notable |
|---|---|---|---|
| **RATU** | `FCFF/WACC DCF` | `Relative Valuation` | Mature, single-pillar oil holding with 8y filing history; passes all gates cleanly without flags. Rating override: None. |
| **CDIA** | `DCF (shortened horizon)` | `Relative Valuation` | 2y filing history fails Gate 1a (`1a_filing_history`); triggers `thin_data=True` and mandatory `⚠ Thin Data` disclosure banner. |
| **MTEL** | `FCFF/WACC DCF` | `Relative Valuation` | Infra tower operator with 25% NCI (in the 15%–40% Gate 2 band); attaches mandatory SOTP cross-check reason. |
| **BBCA** | `DDM / Excess Return` | None | Tier-1 private bank; Gate 0 short-circuits to DDM/Excess Return (debt is raw material, EV undefined). Rating override: None. |
| **ADRO** | `NAV / Reserve-based` | `FCFF/WACC DCF` | Commodity coal mining company with finite reserves; Gate 0/3 routes to NAV reserve-based primary with long-run price deck DCF secondary. |

To re-run the verification audit at any time:
```bash
.venv/bin/python scripts/audit_quintet_gates.py
.venv/bin/python -m pytest scripts/test_audit_quintet.py -v
```

---

## 5. Disclosure

> [!NOTE]
> This framework is a working practitioner framework kept inside the repo; it is not an institutional publication and does not constitute formal investment advice or a regulatory research recommendation. Valuation method selection narrows and structures where analytical judgment is required; it does not replace analyst domain expertise.

---

## 6. Institutional Typography & Presentation Standards

The research publication engine adheres to formal sell-side corporate research typography standards:

| Role | Font Family | Fallback Chain | Asset / Registration |
|---|---|---|---|
| **Serif Body** | **Source Serif 4** | Liberation Serif, DejaVu Serif | `assets/fonts/SourceSerif4-VF.ttf` |
| **Sans-serif UI & Labels** | **Inter** | Liberation Sans, DejaVu Sans | `assets/fonts/Inter-VF.ttf` |
| **Monospace / Numerics** | **JetBrains Mono** | Liberation Mono, DejaVu Sans Mono | `assets/fonts/JetBrainsMono-VF.ttf` |

Design tokens and page furniture are defined once in `server/report/house_format.py` and applied by `templates/macros.html`.



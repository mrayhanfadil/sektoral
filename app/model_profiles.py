"""Profile routing from configured or verified business metadata.

Profiles describe business economics and applicable methods; ticker symbols
never select an engine.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional


SUPPORTED_PROFILES = {
    "finite_life_mining": "LoM/SOTP",
    "going_concern_fcff": "FCFF DCF",
    "financial_ddm": "DDM/residual income",
}

Method = Literal[
    "FCFF/WACC DCF",
    "DCF (shortened horizon)",
    "DDM / Excess Return",
    "NAV / Reserve-based",
    "SOTP",
    "EV/Sales",
    "Relative Valuation",
    "P/BV",
    "unsupported",
]


@dataclass
class GateVerdict:
    primary: str
    secondary: Optional[str]
    thin_data: bool
    rating_override: Optional[str]
    reasons: list[str]
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)

    def __iter__(self):
        yield self.primary
        yield self.secondary
        yield self.thin_data
        yield self.rating_override
        yield self.reasons

    def to_dict(self) -> dict:
        return asdict(self)


def resolve(metadata: dict) -> tuple[str, str]:
    """Return ``(profile, selection_basis)`` for issuer metadata.

    A configured profile takes precedence. Otherwise, verified industry labels
    map to a supported business archetype; unknown metadata fails closed.
    """
    explicit = metadata.get("model_profile")
    if explicit:
        profile = str(explicit).strip().lower()
        if profile in SUPPORTED_PROFILES:
            return profile, "configured issuer model profile"
        return "unsupported", f"unsupported configured model profile: {explicit}"

    industry_text = " ".join(str(metadata.get(key) or "") for key in
                             ("industry", "sub_sector", "sector")).lower()
    if not industry_text.strip():
        return "unsupported", "industry metadata is missing"

    if any(term in industry_text for term in
           ("mining", "minerals", "metal", "coal")):
        return "finite_life_mining", "verified extractive industry metadata"
    if any(term in industry_text for term in
           ("bank", "insurance", "financial")):
        return "financial_ddm", "verified financial industry metadata"
    return "going_concern_fcff", "verified non-financial industry metadata"


def _secondary_for(primary: str, gates_failed: list[str], nci_pct: float) -> Optional[str]:
    if 15.0 < nci_pct <= 40.0:
        return "SOTP"
    if primary in ("FCFF/WACC DCF", "DCF (shortened horizon)"):
        return "Relative Valuation"
    if primary == "NAV / Reserve-based":
        return "FCFF/WACC DCF"
    if primary == "SOTP":
        return "FCFF/WACC DCF"
    if primary in ("DDM", "DDM / Excess Return"):
        return "Relative Valuation"
    if primary in ("EV/Sales", "Relative Valuation"):
        return "FCFF/WACC DCF"
    if primary == "P/BV":
        return "NAV / Reserve-based"
    return None


def evaluate(inputs: dict) -> GateVerdict:
    """Run Gates 0-5 and return GateVerdict(primary, secondary, thin_data, rating_override, reasons)."""
    gates_passed: list[str] = []
    gates_failed: list[str] = []
    reasons: list[str] = []
    thin_data = False
    rating_override: Optional[str] = None

    domain = inputs.get("domain") or inputs.get("model_profile")
    if not domain:
        prof, _ = resolve(inputs)
        if prof == "unsupported":
            return GateVerdict(
                primary="unsupported",
                secondary=None,
                thin_data=False,
                rating_override=None,
                reasons=["unsupported or missing business metadata"],
                gates_passed=[],
                gates_failed=["0_business_model"],
            )
        domain = prof

    domain = str(domain).strip().lower()
    if domain in ("unsupported", "unknown"):
        return GateVerdict(
            primary="unsupported",
            secondary=None,
            thin_data=False,
            rating_override=None,
            reasons=["unsupported model profile or domain"],
            gates_passed=[],
            gates_failed=["0_business_model"],
        )

    # Gate 0
    financial = {"bank", "insurance", "multifinance", "securities", "financial", "financial_ddm"}
    finite_reserves = {"mining", "finite_life_mining", "oil_gas", "plantation", "reit"}
    holding_dissimilar = {"holding_dissimilar", "conglomerate"}

    primary: str = "FCFF/WACC DCF"

    if domain in financial:
        primary = "DDM / Excess Return"
        reasons.append("0 financial institution: debt is raw material, EV undefined, FCF convention inapplicable → DDM primary")
        gates_passed.append("0_business_model")
        # Financials skip Gates 1-4, evaluate Gate 5 only
        _eval_gate5(inputs, gates_passed, gates_failed, reasons, None)
        ro = _eval_gate5_override(inputs)
        secondary = _secondary_for(primary, gates_failed, inputs.get("nci_pct", 0.0))
        return GateVerdict(
            primary=primary,
            secondary=secondary,
            thin_data=False,
            rating_override=ro,
            reasons=reasons,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
        )

    if domain in finite_reserves:
        primary = "NAV / Reserve-based"
        reasons.append("0 finite reserves: perpetual-growth DCF structurally wrong, reserve-based NAV is correct")
        gates_passed.append("0_business_model")
    elif domain in holding_dissimilar:
        segments_count = inputs.get("segments_count")
        if segments_count is None:
            segments_count = len(inputs.get("segments") or [])
        if segments_count > 1:
            primary = "SOTP"
            reasons.append("0 holding with dissimilar lines: one WACC hides value, each line needs its own method → SOTP primary")
            gates_passed.append("0_business_model")
        else:
            gates_passed.append("0_business_model")
    else:
        gates_passed.append("0_business_model")

    # Gate 1: Data eligibility
    filing_history_years = inputs.get("filing_history_years", 5)
    ebit_positive_count = inputs.get("ebit_positive_count", 3)
    d_de_ratio = inputs.get("d_de_ratio", 0.0)
    net_debt_to_ebitda = inputs.get("net_debt_to_ebitda", 0.0)
    icr = inputs.get("icr", inputs.get("interest_coverage", 10.0))
    equity_positive = inputs.get("equity_positive")
    if equity_positive is None:
        equity_positive = inputs.get("equity>0")
    if equity_positive is None:
        eq_val = inputs.get("shareholders_equity", 1.0)
        equity_positive = (eq_val > 0) if isinstance(eq_val, (int, float)) else True

    # 1a
    if filing_history_years >= 4:
        gates_passed.append("1a_filing_history")
    else:
        gates_failed.append("1a_filing_history")
        thin_data = True
        primary = "DCF (shortened horizon)"
        reasons.append(f"1a filing history {filing_history_years}y < 4y → shortened-horizon DCF + ⚠ Thin Data disclosure")

    # 1b
    if ebit_positive_count >= 2:
        gates_passed.append("1b_profitability")
    else:
        gates_failed.append("1b_profitability")
        reasons.append(f"1b EBIT positive in only {ebit_positive_count}/3y → Relative Valuation only (EV/Sales / Price/Sales)")
        primary = "Relative Valuation"

    # 1c
    if d_de_ratio <= 0.80 and net_debt_to_ebitda <= 6.0 and icr >= 1.0:
        gates_passed.append("1c_capital_structure")
    else:
        gates_failed.append("1c_capital_structure")
        reasons.append(f"1c capital structure breach (D/(D+E)={d_de_ratio:.2f}, ND/EBITDA={net_debt_to_ebitda:.2f}×, IC={icr:.2f}×) → DCF proceeds with mandatory Relative cross-check")

    # 1d
    if equity_positive:
        gates_passed.append("1d_equity_base")
    else:
        gates_failed.append("1d_equity_base")
        reasons.append("1d negative shareholders' equity → EV-based multiples only (no P/E, no P/BV)")
        primary = "Relative Valuation"

    # Gate 2: Ownership Structure
    nci_pct = float(inputs.get("nci_pct", 0.0) or 0.0)
    if nci_pct <= 15.0:
        gates_passed.append("2_nci")
    elif nci_pct <= 40.0:
        gates_passed.append("2_nci")
        reasons.append(f"2 NCI {nci_pct:.1f}% in 15–40% band → DCF + mandatory SOTP cross-check")
    else:
        gates_failed.append("2_nci")
        reasons.append(f"2 NCI {nci_pct:.1f}% > 40% → SOTP becomes primary, consolidated DCF is rough reference only")
        primary = "SOTP"

    # Gate 3: Cyclicality / Operating Stage
    revenue_drivers = inputs.get("revenue_drivers") or []
    has_steady_state_3y = inputs.get("has_steady_state_3y", True)
    commodity_tags = {"commodity_coal", "commodity_nickel", "commodity_cpo", "commodity_oil", "commodity_gold", "commodity_copper", "commodity"}
    if any(tag in commodity_tags or "commodity" in str(tag) for tag in revenue_drivers):
        gates_passed.append("3_cyclicality")
        primary = "NAV / Reserve-based"
        reasons.append("3 commodity-driven revenue → NAV/reserve-based primary + DCF as long-run price deck comparison")
    elif not has_steady_state_3y:
        gates_passed.append("3_cyclicality")
        primary = "Relative Valuation"
        reasons.append("3 newly commissioned / ramping asset (<3y steady-state) → forward Relative Valuation primary (EV/EBITDA at target capacity against mature peers)")
    else:
        gates_passed.append("3_cyclicality")

    # Gate 4: Life Cycle Stage
    life_cycle_stage = str(inputs.get("life_cycle_stage", "mature")).lower()
    gates_passed.append("4_life_cycle")
    if life_cycle_stage == "decline":
        primary = "P/BV"
        reasons.append("4 decline / turnaround → P/BV (or NAV if asset base is substantial), DCF too speculative")
    elif life_cycle_stage in ("pre_revenue", "high_growth_pre_profit", "high_growth"):
        primary = "EV/Sales"
        reasons.append(f"4 {life_cycle_stage} → EV/Sales primary")

    # Determine secondary
    secondary = _secondary_for(primary, gates_failed, nci_pct)

    # Gate 5: Output Sanity
    rating_override = _eval_gate5(inputs, gates_passed, gates_failed, reasons, rating_override)

    return GateVerdict(
        primary=primary,
        secondary=secondary,
        thin_data=thin_data,
        rating_override=rating_override,
        reasons=reasons,
        gates_passed=gates_passed,
        gates_failed=gates_failed,
    )


EXTREME_UPSIDE_RATIO = 1.0     # Gate 5: upside > +100% -> Review Required
EXTREME_DOWNSIDE_RATIO = -0.5  # Gate 5: downside < -50% -> Review Required


def is_extreme_upside(upside_ratio) -> bool:
    """Gate 5 rule on a ratio (tp / price - 1); shared by every valuation branch."""
    return (isinstance(upside_ratio, (int, float)) and not isinstance(upside_ratio, bool)
            and (upside_ratio > EXTREME_UPSIDE_RATIO or upside_ratio < EXTREME_DOWNSIDE_RATIO))


def _eval_gate5_override(inputs: dict) -> Optional[str]:
    upside = inputs.get("upside_pct", inputs.get("upside"))
    if upside is not None:
        u_pct = upside * 100.0 if abs(upside) <= 2.0 and not (upside > 1.0 and upside == int(upside)) else upside
        if u_pct > 100.0 or u_pct < -50.0:
            return "Review Required"
    return None


def _eval_gate5(inputs: dict, gates_passed: list[str], gates_failed: list[str], reasons: list[str], rating_override: Optional[str]) -> Optional[str]:
    upside = inputs.get("upside_pct", inputs.get("upside"))
    tv_share = inputs.get("terminal_value_pct_of_ev", inputs.get("tv_share"))
    implied_exit = inputs.get("implied_exit_ev_ebitda")
    peer_low = inputs.get("peer_exit_low")
    peer_high = inputs.get("peer_exit_high")

    if upside is not None:
        u_pct = upside * 100.0 if abs(upside) <= 2.0 and not (upside > 1.0 and upside == int(upside)) else upside
        if u_pct > 100.0:
            gates_failed.append("5_upside_extreme")
            rating_override = "Review Required"
            reasons.append(f"5 upside {u_pct:.1f}% > 100% → rating auto-override to Review Required")
        elif u_pct < -50.0:
            gates_failed.append("5_downside_extreme")
            rating_override = "Review Required"
            reasons.append(f"5 downside {u_pct:.1f}% < -50% → rating auto-override to Review Required")
        else:
            gates_passed.append("5_upside_band")

    if tv_share is not None:
        tv_pct = tv_share * 100.0 if tv_share <= 1.0 else tv_share
        if tv_pct > 75.0:
            gates_failed.append("5_tv_share_high")
            reasons.append(f"5 terminal value {tv_pct:.1f}% > 75% of EV → flagged for cross-check (implied exit-multiple or Relative Valuation)")
        else:
            gates_passed.append("5_tv_share")

    if implied_exit is not None and peer_low is not None and peer_high is not None:
        if not (peer_low <= implied_exit <= peer_high):
            gates_failed.append("5_exit_multiple_out_of_range")
            reasons.append(f"5 implied exit EV/EBITDA {implied_exit:.1f}× outside peer range {peer_low:.1f}-{peer_high:.1f}× → WACC/g out of sync with market pricing, cross-check vs EV/EBITDA relative valuation")
        else:
            gates_passed.append("5_exit_multiple_in_range")

    return rating_override

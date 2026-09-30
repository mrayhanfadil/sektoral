"""Stable exhibit ids: code finds an exhibit by what it is, not by its title.

An exhibit's title (``judul``) is display text and differs per report
language, so code that picks one exhibit out of a report (the cover's Key
Financials, the gallery's method chain, the rebuild's revenue chart) keys on
``exhibit_id``, set where the exhibit is built. Reports stored before the id
existed carry only the Indonesian title; they are still found by it.
"""
from __future__ import annotations

KEY_FINANCIALS = "key_financials"
METHOD_CHAIN = "method_chain"
CATALYSTS = "catalysts"
REVENUE_PANEL = "revenue_panel"

# Titles the exhibits had before they carried an id: exact, or a prefix for
# titles that end in their period ("Pendapatan dan pertumbuhan (2024A-FY28F)").
_LEGACY_TITLE = {KEY_FINANCIALS: "Key Financials",
                 METHOD_CHAIN: "Rantai metode valuasi",
                 CATALYSTS: "Katalis, risiko, dan indikator pemantauan"}
_LEGACY_PREFIX = {REVENUE_PANEL: "Pendapatan"}


def tag(exhibit: dict, exhibit_id: str) -> dict:
    """Give `exhibit` its stable id; returns it."""
    exhibit["exhibit_id"] = exhibit_id
    return exhibit


def is_exhibit(exhibit, exhibit_id: str) -> bool:
    """Whether `exhibit` is the one with `exhibit_id` (by its title if it has no id)."""
    if not isinstance(exhibit, dict):
        return False
    if exhibit.get("exhibit_id") is not None:
        return exhibit["exhibit_id"] == exhibit_id
    title = str(exhibit.get("judul") or "")
    if exhibit_id in _LEGACY_TITLE:
        return title == _LEGACY_TITLE[exhibit_id]
    prefix = _LEGACY_PREFIX.get(exhibit_id)
    return bool(prefix) and title.startswith(prefix)


def find(exhibits, exhibit_id: str) -> dict | None:
    """The first exhibit in `exhibits` with `exhibit_id`, or None."""
    return next((e for e in exhibits or [] if is_exhibit(e, exhibit_id)), None)

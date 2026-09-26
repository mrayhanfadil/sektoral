"""Report contract validator.

Adapts the validation rules from DATA_CONTRACT.md and Phase 2 of the
sectors-hackathon adoption plan:
Rule 1: Blended weights sum == 100 when valuation.blended is present;
        assert sum == 100, flag/reject if divergence > 30% without explicit thesis.
Rule 2: Every exhibit has non-empty catatan_sumber or source (internal provenance)
        AND global sequential numbering (Exhibit N / n), no duplicate or out-of-order numbering.
Rule 3: If segments > 1, share_pct must sum to 100 ± 0.5.
Rule 4: Upside recompute check: if tp and price (or harga) are present,
        assert round((tp - price) / price * 100, 1) == round(doc_upside, 1).
Rule 5: news items must have non-empty date/timestamp; sentiment gauge/score in [0, 100] if present.
Rule 6: ESG check: if found == False or esg is missing/empty, esg box must be hidden (no fabricated scores).
"""

from __future__ import annotations

import re
from typing import Any

from app import release_policy


class ValidationError(ValueError):
    """Raised when a document violates the report data contract."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        message = (
            f"Report contract validation failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {err}" for err in errors)
        )
        super().__init__(message)


ReportContractError = ValidationError


def _extract_exhibit_number(exhibit: dict[str, Any]) -> int | None:
    """Extract integer exhibit number from n, number, id, or Exhibit N in title/judul."""
    for key in ("n", "number"):
        val = exhibit.get(key)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass

    val_id = exhibit.get("id")
    if val_id is not None:
        try:
            return int(val_id)
        except (ValueError, TypeError):
            m = re.search(r"\b(\d+)\b", str(val_id))
            if m:
                return int(m.group(1))

    for title_key in ("title", "judul"):
        title = str(exhibit.get(title_key) or "")
        m = re.search(r"(?:Exhibit|Ekshibit|Lampiran)\s*(\d+)", title, re.IGNORECASE)
        if m:
            return int(m.group(1))

    return None


def check_rule_1_blended_weights(doc: dict[str, Any]) -> list[str]:
    """Rule 1: Blended weights sum == 100 (when valuation.blended is present;
    assert sum == 100, flag/reject if divergence > 30% without explicit thesis).
    """
    errors: list[str] = []
    valuation = doc.get("valuation")
    blended = None
    if isinstance(valuation, dict):
        blended = valuation.get("blended")
    if blended is None:
        blended = doc.get("blended")

    if not isinstance(blended, dict):
        return errors

    # Check weights sum == 100
    weights = blended.get("weights")
    if weights is not None:
        if isinstance(weights, dict):
            total_weight = sum(float(w) for w in weights.values() if isinstance(w, (int, float)))
        elif isinstance(weights, (list, tuple)):
            total_weight = sum(float(w) for w in weights if isinstance(w, (int, float)))
        else:
            errors.append(
                f"Rule 1: Blended weights must be a dict or list, got {type(weights).__name__}"
            )
            total_weight = None

        if total_weight is not None and abs(total_weight - 100.0) > 1e-4:
            errors.append(
                f"Rule 1: Blended weights must sum to 100, got {total_weight}"
            )

    # Check divergence > 30% without explicit thesis
    div_val: float | None = None
    # Case 1: divergence explicitly provided in blended or valuation
    for div_key in ("divergence", "divergence_pct", "gap", "method_gap"):
        val = blended.get(div_key)
        if val is None and isinstance(valuation, dict):
            val = valuation.get(div_key)
        if isinstance(val, (int, float)):
            div_val = float(val)
            if div_val > 1.0:
                div_val = div_val / 100.0
            break

    # Case 2: compute divergence from methods in valuation or blended
    if div_val is None:
        methods = None
        if isinstance(valuation, dict) and isinstance(valuation.get("methods"), list):
            methods = valuation["methods"]
        elif isinstance(blended.get("methods"), list):
            methods = blended["methods"]

        if methods and len(methods) >= 2:
            fvs: list[float] = []
            for m in methods:
                if isinstance(m, dict):
                    fv = (
                        m.get("fv")
                        or m.get("fair_value")
                        or m.get("tp")
                        or m.get("target_price")
                        or m.get("value")
                    )
                    if isinstance(fv, (int, float)):
                        fvs.append(float(fv))
            if len(fvs) >= 2:
                max_fv, min_fv = max(fvs), min(fvs)
                denom = max(abs(max_fv), abs(min_fv), 1.0)
                div_val = abs(max_fv - min_fv) / denom

    # Case 3: ps_gordon and ps_exit in valuation
    if div_val is None and isinstance(valuation, dict):
        ps_g = valuation.get("ps_gordon")
        ps_x = valuation.get("ps_exit")
        if isinstance(ps_g, (int, float)) and isinstance(ps_x, (int, float)):
            denom = max(abs(ps_g), abs(ps_x), 1.0)
            div_val = abs(ps_g - ps_x) / denom

    if div_val is not None and div_val > 0.30:
        # Check if an explicit thesis is provided
        has_thesis = bool(
            blended.get("thesis")
            or blended.get("explicit_thesis")
            or blended.get("reason")
            or (isinstance(valuation, dict) and (valuation.get("thesis") or valuation.get("explicit_thesis")))
            or doc.get("thesis")
            or (isinstance(doc.get("meta"), dict) and doc["meta"].get("thesis"))
        )
        if not has_thesis:
            errors.append(
                f"Rule 1: Valuation divergence ({div_val * 100:.1f}%) exceeds 30% without explicit thesis"
            )

    return errors


def check_rule_2_exhibit_provenance_and_numbering(doc: dict[str, Any]) -> list[str]:
    """Rule 2: Every exhibit has non-empty catatan_sumber or source (internal provenance)
    AND global sequential numbering (Exhibit N / n), no duplicate or out-of-order numbering.
    """
    errors: list[str] = []

    # Collect exhibits list
    # Prefer top-level doc["exhibits"] if available; otherwise extract from doc["bagian"]
    exhibits = doc.get("exhibits")
    if (not exhibits) and isinstance(doc.get("bagian"), list):
        bagian_exs: list[dict[str, Any]] = []
        for sec in doc["bagian"]:
            if isinstance(sec, dict) and isinstance(sec.get("exhibit"), list):
                bagian_exs.extend(sec["exhibit"])
        if bagian_exs:
            exhibits = bagian_exs

    if not isinstance(exhibits, list) or len(exhibits) == 0:
        return errors

    seen_numbers: set[int] = set()
    prev_number: int | None = None

    for idx, e in enumerate(exhibits):
        if not isinstance(e, dict):
            errors.append(f"Rule 2: Exhibit at index {idx} must be a dict")
            continue

        # 1. Check internal provenance source / catatan_sumber
        source = e.get("catatan_sumber") or e.get("source")
        if not source or not str(source).strip():
            title = e.get("title") or e.get("judul") or f"at position {idx + 1}"
            errors.append(
                f"Rule 2: Exhibit '{title}' missing non-empty source/catatan_sumber (internal provenance)"
            )

        # 2. Check global sequential numbering
        num = _extract_exhibit_number(e)
        expected_num = idx + 1
        if num is None:
            errors.append(
                f"Rule 2: Exhibit at position {idx + 1} missing global sequential numbering (`Exhibit N` / `n`)"
            )
        else:
            if num in seen_numbers:
                errors.append(
                    f"Rule 2: Duplicate exhibit number {num} at position {idx + 1}"
                )
            elif prev_number is not None and num < prev_number:
                errors.append(
                    f"Rule 2: Out-of-order exhibit number {num} after {prev_number} at position {idx + 1}"
                )
            elif num != expected_num:
                errors.append(
                    f"Rule 2: Non-sequential exhibit number {num} at position {idx + 1}, expected {expected_num}"
                )
            seen_numbers.add(num)
            prev_number = num

    return errors


def check_rule_3_segments_share(doc: dict[str, Any]) -> list[str]:
    """Rule 3: If segments > 1, share_pct must sum to 100 ± 0.5."""
    errors: list[str] = []

    segments = doc.get("segments")
    if not isinstance(segments, list) and isinstance(doc.get("cover"), dict):
        segments = doc["cover"].get("segments")
    if not isinstance(segments, list) and isinstance(doc.get("performance"), dict):
        segments = doc["performance"].get("segments")

    if not isinstance(segments, list) or len(segments) <= 1:
        return errors

    total_share = 0.0
    has_invalid_share = False

    for idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            errors.append(f"Rule 3: Segment at index {idx} must be a dict")
            has_invalid_share = True
            continue

        share = (
            seg.get("share_pct")
            if seg.get("share_pct") is not None
            else seg.get("share")
            if seg.get("share") is not None
            else seg.get("pct")
            if seg.get("pct") is not None
            else seg.get("porsi")
        )

        if share is None or not isinstance(share, (int, float)):
            name = seg.get("name") or f"at index {idx}"
            errors.append(f"Rule 3: Segment '{name}' missing numeric share_pct")
            has_invalid_share = True
        else:
            total_share += float(share)

    if not has_invalid_share:
        if not release_policy.segment_share_sum_is_valid(total_share):
            errors.append(
                f"Rule 3: Segments share_pct must sum to 100 ± 0.5, got {total_share:.2f}"
            )

    return errors


def check_rule_4_upside_recompute(doc: dict[str, Any]) -> list[str]:
    """Rule 4: Upside recompute check: if tp and price (or harga) are present,
    assert round((tp - price) / price * 100, 1) == round(doc_upside, 1).
    """
    errors: list[str] = []

    # Resolve tp
    tp: float | None = None
    cover = doc.get("cover") if isinstance(doc.get("cover"), dict) else {}
    rating_box = cover.get("rating_box") if isinstance(cover.get("rating_box"), dict) else {}
    meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
    data_pasar = cover.get("data_pasar") if isinstance(cover.get("data_pasar"), dict) else {}

    for val in (rating_box.get("tp"), meta.get("tp"), data_pasar.get("tp"), doc.get("tp")):
        if val is not None and isinstance(val, (int, float)):
            tp = float(val)
            break

    # Resolve price / harga
    price: float | None = None
    for val in (
        rating_box.get("price"),
        rating_box.get("harga"),
        meta.get("harga"),
        meta.get("price"),
        data_pasar.get("harga"),
        data_pasar.get("price"),
        doc.get("price"),
        doc.get("harga"),
    ):
        if val is not None and isinstance(val, (int, float)):
            price = float(val)
            break

    # If tp and price are present, assert recompute
    if tp is not None and price is not None:
        if price <= 0:
            errors.append(f"Rule 4: Price must be positive to compute upside, got {price}")
            return errors

        expected_upside = round((tp - price) / price * 100, 1)

        # Resolve doc_upside
        doc_upside: float | None = None
        for val in (
            rating_box.get("upside_pct"),
            rating_box.get("upside"),
            meta.get("upside_persen"),
            meta.get("upside_pct"),
            meta.get("upside"),
            cover.get("upside_pct"),
            cover.get("upside_persen"),
            cover.get("upside"),
            doc.get("upside_pct"),
            doc.get("upside_persen"),
            doc.get("upside"),
        ):
            if val is not None and isinstance(val, (int, float)):
                doc_upside = float(val)
                break

        if doc_upside is None:
            errors.append(
                "Rule 4: Upside percentage missing in document when tp and price are present"
            )
        else:
            # Handle fraction form (e.g. 0.38 for 38%)
            if round(doc_upside, 1) == expected_upside:
                matched = True
            elif round(doc_upside * 100, 1) == expected_upside:
                matched = True
            else:
                matched = False

            if not matched:
                errors.append(
                    f"Rule 4: Upside recompute mismatch: expected {expected_upside}%, got {round(doc_upside, 1)}%"
                )

    return errors


def check_rule_5_news_and_sentiment(doc: dict[str, Any]) -> list[str]:
    """Rule 5: news items must have non-empty date/timestamp;
    sentiment gauge/score must be in [0, 100] if present.
    """
    errors: list[str] = []

    # Check news items
    news = doc.get("news")
    if not isinstance(news, list) and isinstance(doc.get("cover"), dict):
        news = doc["cover"].get("news")

    if isinstance(news, list):
        for idx, item in enumerate(news):
            if not isinstance(item, dict):
                errors.append(f"Rule 5: News item at index {idx} must be a dict")
                continue
            date_val = (
                item.get("date")
                or item.get("timestamp")
                or item.get("datetime")
                or item.get("time")
            )
            if not date_val or not str(date_val).strip():
                title = item.get("title") or f"at index {idx}"
                errors.append(f"Rule 5: News item '{title}' missing non-empty date/timestamp")
            if "url" in item:
                url_val = item.get("url")
                if url_val is not None and not str(url_val).strip():
                    title = item.get("title") or f"at index {idx}"
                    errors.append(f"Rule 5: News item '{title}' has empty url")

    # Check sentiment gauge/score
    sentiment = doc.get("sentiment")
    if sentiment is None and isinstance(doc.get("cover"), dict):
        sentiment = doc["cover"].get("sentiment")

    if isinstance(sentiment, dict):
        for key in ("gauge", "score", "sentiment_score", "sentiment_gauge"):
            if key in sentiment and sentiment[key] is not None:
                val = sentiment[key]
                if not isinstance(val, (int, float)):
                    errors.append(
                        f"Rule 5: Sentiment {key} must be a number, got {type(val).__name__}"
                    )
                elif val < 0 or val > 100:
                    errors.append(
                        f"Rule 5: Sentiment {key} must be in [0, 100], got {val}"
                    )
    elif isinstance(sentiment, (int, float)):
        if sentiment < 0 or sentiment > 100:
            errors.append(
                f"Rule 5: Sentiment score must be in [0, 100], got {sentiment}"
            )

    # Check standalone keys in doc or cover
    for standalone_key in ("sentiment_gauge", "sentiment_score"):
        for container in (doc, doc.get("cover")):
            if isinstance(container, dict) and standalone_key in container:
                val = container[standalone_key]
                if val is not None:
                    if not isinstance(val, (int, float)):
                        errors.append(
                            f"Rule 5: {standalone_key} must be a number, got {type(val).__name__}"
                        )
                    elif val < 0 or val > 100:
                        errors.append(
                            f"Rule 5: {standalone_key} must be in [0, 100], got {val}"
                        )

    return errors


def check_rule_6_esg(doc: dict[str, Any]) -> list[str]:
    """Rule 6: ESG check: if found == False or esg is missing/empty,
    esg box must be hidden (no fabricated scores).
    """
    errors: list[str] = []

    cover = doc.get("cover") if isinstance(doc.get("cover"), dict) else {}
    esg = cover.get("esg") if "esg" in cover else doc.get("esg")

    # Case A: esg missing or empty
    if not esg:
        # If missing/empty, ensure ESG box is not explicitly shown
        for key in ("show_esg", "show_esg_box", "esg_visible"):
            if doc.get(key) is True or cover.get(key) is True:
                errors.append(
                    "Rule 6: ESG box must be hidden when ESG data is missing or empty"
                )
        if doc.get("esg_scores") or cover.get("esg_scores"):
            errors.append(
                "Rule 6: Fabricated ESG scores present when ESG data is missing or empty"
            )
        return errors

    if not isinstance(esg, dict):
        errors.append(f"Rule 6: esg must be a dict, got {type(esg).__name__}")
        return errors

    found = esg.get("found")

    # Case B: found == False (or found is not True)
    if found is False or not found:
        scores = esg.get("scores") or esg.get("score")
        if scores:
            if isinstance(scores, dict) and len(scores) > 0:
                errors.append(
                    "Rule 6: Fabricated ESG scores present when found is False"
                )
            elif isinstance(scores, (int, float, list, str)):
                errors.append(
                    "Rule 6: Fabricated ESG scores present when found is False"
                )

        if esg.get("visible") is True or esg.get("show_box") is True:
            errors.append(
                "Rule 6: ESG box must be hidden when found is False"
            )
        if esg.get("hide_box") is False:
            errors.append(
                "Rule 6: ESG box must be hidden (hide_box=True) when found is False"
            )
        for key in ("show_esg", "show_esg_box", "esg_visible"):
            if doc.get(key) is True or cover.get(key) is True:
                errors.append(
                    "Rule 6: ESG box must be hidden when found is False"
                )

    return errors


def validate(doc: dict[str, Any]) -> list[str]:
    """Validate a report contract document against all 6 rules.

    Returns:
        A list of error message strings. Empty list indicates full compliance.
    """
    if not isinstance(doc, dict):
        return ["Report document must be a dictionary"]

    errors: list[str] = []
    errors.extend(check_rule_1_blended_weights(doc))
    errors.extend(check_rule_2_exhibit_provenance_and_numbering(doc))
    errors.extend(check_rule_3_segments_share(doc))
    errors.extend(check_rule_4_upside_recompute(doc))
    errors.extend(check_rule_5_news_and_sentiment(doc))
    errors.extend(check_rule_6_esg(doc))
    return errors


def validate_or_raise(doc: dict[str, Any]) -> None:
    """Validate a report contract document and raise ValidationError if any violation occurs."""
    errors = validate(doc)
    if errors:
        raise ValidationError(errors)

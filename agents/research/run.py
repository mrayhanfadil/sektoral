"""Bounded research agent that can only inspect the local Sectors cache.

This agent produces a qualitative, source-linked research brief. It does not
create valuation or forecast outputs, and it never accesses upstream sources.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.estimator import tools as cache_tools
from agents.estimator.run import _chat, _parse_json, _response_text
from app.progress import emit

MAX_TOOL_CALLS = 6
MAX_INSIGHTS = 3
_INVESTMENT_ACTION = re.compile(
    r"\b(buy|sell|hold|recommend\w*|strong buy|strong sell|target price|price target|"
    r"beli|jual|tahan|rekomendasi|target harga|harga target|nilai wajar|fair value)\b",
    re.I,
)
_NARRATIVE_DIGIT = re.compile(r"\d")
_TREND = re.compile(
    r"\b(increas(?:e|ed|es|ing)|decreas(?:e|ed|es|ing)|improv(?:e|ed|es|ing)|"
    r"worsen(?:ed|s|ing)?|rose|risen|rise|rising|grew|grown|grow|grew|"
    r"declin(?:e|ed|es|ing)|fell|fallen|fall|falling|higher|lower|trend|trending|tren|momentum|trajectory|kecenderungan|"
    r"rebound(?:ed|s|ing)?|recover(?:ed|s|ing)?|volatile|volatility|fluctuat(?:e|ed|es|ing)|"
    r"negative.{0,30}positive|positive.{0,30}negative|"
    r"naik|meningkat|meningkatkan|membaik|memburuk|turun|menurun|penurunan|"
    r"kenaikan|lonjakan|melonjak|anjlok|berbalik|pulih|fluktuatif|berfluktuasi)\b",
    re.I,
)
_UP_TREND = re.compile(r"\b(increas|improv|rose|risen|rise|rising|grew|grown|grow|higher|rebound|recover|naik|meningkat|membaik|kenaikan|lonjakan|melonjak|pulih)\w*\b|negative.{0,30}positive", re.I)
_DOWN_TREND = re.compile(r"\b(decreas|worsen|declin|fell|fallen|fall|lower|turun|menurun|penurunan|memburuk|anjlok)\w*\b|positive.{0,30}negative", re.I)
_VOLATILE_TREND = re.compile(r"\b(volatile|volatility|fluctuat|fluktuatif|berfluktuasi)\w*\b", re.I)
_TEMPORAL_REPETITION = re.compile(
    r"\b(several|multiple|repeated|repeatedly|recurring|recurrently|repeatedly appeared|"
    r"consistently|over time|across periods|across quarters|month after month|"
    r"quarter after quarter|beberapa (?:kali|triwulan|kuartal|periode)|berulang(?: kali)?|"
    r"berkali-kali|sering|konsisten|dari waktu ke waktu|selama beberapa periode|"
    r"beberapa waktu terakhir)\b", re.I)
_SEARCH_COVERAGE_CLAIM = re.compile(
    r"(?:\b(?:search|hasil pencarian)\b.{0,50}\b(?:page|halaman|complete|incomplete|"
    r"coverage|cakupan|only|single|first|partial|all|complete|incomplete|awal|"
    r"tersedia|lengkap|seluruh|terbatas)\b|"
    r"\b(?:page|halaman)\b.{0,50}\b(?:search|hasil|available|tersedia|awal|pertama)\b|"
    r"\b(?:only|single|first|partial|complete|incomplete|all|hanya|satu|awal|pertama)\b"
    r".{0,45}\b(?:search results|hasil pencarian|results page|halaman hasil)\b)", re.I)
_POSITIVE_FLOW = re.compile(
    r"\b(accumulat\w*|inflow\w*|net buy\w*|foreign buy\w*|buying pressure|"
    r"bought|destination|destinasi|arus masuk|akumulasi|pembelian asing|membeli)\b", re.I)
_NEGATIVE_FLOW = re.compile(
    r"\b(outflow\w*|net sell\w*|foreign sell\w*|selling pressure|pressure|"
    r"under pressure|sold|arus keluar|tekanan(?:\s+jual)?|penjualan asing|"
    r"penjualan bersih)\b", re.I)
_METRIC_ALIASES = {
    "revenue": ("pendapatan", "revenue", "penjualan", "sales"),
    "gross_loan": ("kredit bruto", "pinjaman bruto", "gross loan"),
    "net_loan": ("kredit bersih", "pinjaman bersih", "net loan"),
    "loans": ("loans", "loan balance", "pinjaman", "kredit"),
    "total_deposit": ("total simpanan", "total deposito", "total deposit", "total deposits"),
    "interest_income": ("pendapatan bunga", "penghasilan bunga", "interest income"),
    "net_interest_income": ("pendapatan bunga bersih", "net interest income"),
    "non_interest_income": ("pendapatan non-bunga", "non-interest income", "non interest income"),
    "interest_expense": ("beban bunga", "biaya bunga", "interest expense"),
    "net_profit": ("net profit", "net income", "laba bersih"),
    "net_income": ("net income", "net profit", "laba bersih"),
    "operating_cash_flow": ("operating cash flow", "cash flow from operations",
                             "arus kas operasi", "arus kas operasional"),
    "cash_flow_from_operations": ("cash flow from operations", "operating cash flow",
                                  "arus kas operasi", "arus kas operasional"),
    "capex": ("capex", "capital expenditure", "belanja modal"),
    "production": ("production", "produksi"),
    "volume": ("volume", "volume produksi"),
    "ebitda": ("ebitda",),
}
_ARTICLE_SUBJECT_ALIASES = {
    "global": ("global", "dunia", "internasional"),
    "pressure": ("pressure", "tekanan"),
    "market": ("market", "pasar"),
    "lending": ("lending", "pinjaman", "kredit", "penyaluran kredit"),
    "loan": ("loan", "pinjaman", "kredit"),
    "deposit": ("deposit", "simpanan", "deposito"),
    "foreign": ("foreign", "asing"),
    "flow": ("flow", "arus"),
    "rate": ("rate", "rates", "suku bunga"),
    "risk": ("risk", "risiko"),
    "commodity": ("commodity", "commodities", "komoditas"),
    "earnings": ("earnings", "laba", "pendapatan"),
    "inflation": ("inflation", "inflasi"),
}
_COMPOSITE_ARTICLE_SUBJECTS = (
    ("tekanan pasar global", ("global", "dunia", "internasional"),
     ("pressure", "tekanan"),
     ("tekanan pasar global", "tekanan global", "global market pressure",
      "pressure in global markets", "global pressure")),
    ("penjualan bersih asing", ("foreign", "asing"),
     ("net sell", "net-selling", "net selling", "outflow", "jual bersih",
      "penjualan bersih", "arus keluar"),
     ("penjualan bersih asing", "asing net sell", "foreign net sell",
      "foreign net selling", "foreign outflow", "arus keluar asing")),
    ("pembelian bersih asing", ("foreign", "asing"),
     ("net buy", "net-buying", "net buying", "inflow", "beli bersih",
      "pembelian bersih", "arus masuk"),
     ("pembelian bersih asing", "asing net buy", "foreign net buy",
      "foreign net buying", "foreign inflow", "arus masuk asing")),
    ("kredit dan simpanan", ("lending", "loan", "kredit"),
     ("deposit", "deposits", "simpanan", "deposito"),
     ("kredit dan simpanan", "pinjaman dan simpanan", "loans and deposits",
      "lending and deposits")),
)


def _pointer(payload, pointer):
    """Resolve an RFC6901 JSON pointer; the empty pointer selects the root."""
    if pointer == "":
        return payload
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("citation field_path must be a JSON Pointer")
    value = payload
    for raw in pointer[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not key.isdigit():
                raise ValueError("array path segment must be an integer")
            value = value[int(key)]
        elif isinstance(value, dict) and key in value:
            value = value[key]
        else:
            raise ValueError("citation path does not exist")
    return value


def _resolve_or_recover_pointer(payload, pointer, endpoint=None):
    """Resolve a path, or uniquely recover its terminal scalar key.

    Recovery is confined to the already-read endpoint payload. It is accepted
    only for one exact key-name match and returns the canonical pointer.
    """
    try:
        return _pointer(payload, pointer), pointer
    except (ValueError, IndexError, TypeError, KeyError):
        if not isinstance(pointer, str) or not pointer:
            raise ValueError("citation path cannot be recovered")
        submitted_parts = [part.replace("~1", "/").replace("~0", "~")
                           for part in pointer.split("/")[1:]]
        if endpoint and re.fullmatch(r"/financials/quarterly/[A-Z0-9.-]+/", endpoint):
            metric_paths = _quarterly_metric_paths(payload, limit=10000)
            ordered_matches = []
            for canonical in metric_paths:
                canonical_parts = [part.replace("~1", "/").replace("~0", "~")
                                   for part in canonical.split("/")[1:]]
                cursor = 0
                for part in canonical_parts:
                    if cursor < len(submitted_parts) and part == submitted_parts[cursor]:
                        cursor += 1
                if submitted_parts and cursor == len(submitted_parts):
                    ordered_matches.append(canonical)
            if ordered_matches:
                if len(ordered_matches) != 1:
                    raise ValueError("quarterly metric path is ambiguous")
                canonical = ordered_matches[0]
                return _pointer(payload, canonical), canonical
            # Some model outputs preserve the correct array row and metric name
            # but hallucinate an intermediate object name. Permit that only
            # when those anchors identify one recognized quarterly metric leaf.
            numeric_anchors = [part for part in submitted_parts if part.isdigit()]
            metric_leaf = submitted_parts[-1] if submitted_parts else ""
            anchored_matches = []
            if numeric_anchors and metric_leaf:
                for canonical in metric_paths:
                    canonical_parts = [part.replace("~1", "/").replace("~0", "~")
                                       for part in canonical.split("/")[1:]]
                    canonical_indices = [part for part in canonical_parts if part.isdigit()]
                    if (canonical_parts[-1] == metric_leaf and
                            canonical_indices == numeric_anchors):
                        anchored_matches.append(canonical)
            if anchored_matches:
                if len(anchored_matches) != 1:
                    raise ValueError("quarterly row and metric anchors are ambiguous")
                canonical = anchored_matches[0]
                return _pointer(payload, canonical), canonical
        suffix_matches = []

        def walk_suffix(node, parts):
            if isinstance(node, dict):
                for key, value in node.items():
                    next_parts = parts + [str(key)]
                    if (value is not None and not isinstance(value, (dict, list)) and
                            submitted_parts and len(next_parts) >= len(submitted_parts) and
                            next_parts[-len(submitted_parts):] == submitted_parts):
                        canonical = "/" + "/".join(
                            part.replace("~", "~0").replace("/", "~1")
                            for part in next_parts)
                        suffix_matches.append((value, canonical))
                    walk_suffix(value, next_parts)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    next_parts = parts + [str(index)]
                    if (value is not None and not isinstance(value, (dict, list)) and
                            submitted_parts and len(next_parts) >= len(submitted_parts) and
                            next_parts[-len(submitted_parts):] == submitted_parts):
                        canonical = "/" + "/".join(
                            part.replace("~", "~0").replace("/", "~1")
                            for part in next_parts)
                        suffix_matches.append((value, canonical))
                    walk_suffix(value, next_parts)

        walk_suffix(payload, [])
        if suffix_matches:
            if len(suffix_matches) != 1:
                raise ValueError("citation structural suffix is ambiguous")
            return suffix_matches[0]

        terminal = pointer.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
        if not terminal:
            raise ValueError("citation path cannot be recovered")
        matches = []

        def walk(node, parts):
            if isinstance(node, dict):
                for key, value in node.items():
                    next_parts = parts + [str(key)]
                    if str(key) == terminal and value is not None and not isinstance(value, (dict, list)):
                        canonical = "/" + "/".join(
                            part.replace("~", "~0").replace("/", "~1")
                            for part in next_parts)
                        matches.append((value, canonical))
                    walk(value, next_parts)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, parts + [str(index)])

        walk(payload, [])
        if len(matches) != 1:
            raise ValueError("citation terminal key is absent or ambiguous")
        return matches[0]


def _numeric_values(value):
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, (int, float)):
        return {float(value)}
    if isinstance(value, str):
        # Treat punctuation as formatting, so "1,250" supports 1250.
        found = set()
        for match in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?", value):
            try:
                found.add(float(match.replace(",", "")))
            except ValueError:
                pass
        return found
    if isinstance(value, list):
        found = set()
        for item in value:
            found.update(_numeric_values(item))
        return found
    if isinstance(value, dict):
        found = set()
        for item in value.values():
            found.update(_numeric_values(item))
        return found
    return set()


def _numbers_in_text(value):
    # Ignore ISO dates; they are metadata and are independently checked.
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", str(value))
    text = re.sub(r"\b\d{4}-Q[1-4]\b", "", text, flags=re.I)
    return _numeric_values(text)


def _as_of(evidence):
    for item in evidence:
        payload = item["payload"]
        if item["endpoint"].startswith("/company/report/"):
            overview = payload.get("overview") or {}
            valuation = payload.get("valuation") or {}
            value = overview.get("latest_close_date") or valuation.get("latest_close_date")
            if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return value
    return None


def _clean_text(value, limit=1200):
    if not isinstance(value, str):
        return ""
    # Remove control characters and cap untrusted model output before saving.
    return "".join(ch for ch in value.strip() if ch >= " " or ch in "\n\t")[:limit]


def _narrative_problems(document):
    """Narrative text is qualitative; all observed figures live in citations."""
    problems = []
    parts = []
    for key in ("summary",):
        if isinstance(document.get(key), str):
            parts.append((key, document[key]))
    if isinstance(document.get("limitations"), list):
        parts.extend((f"limitations[{i}]", value)
                     for i, value in enumerate(document["limitations"])
                     if isinstance(value, str))
    if isinstance(document.get("insights"), list):
        for i, insight in enumerate(document["insights"]):
            if not isinstance(insight, dict):
                continue
            for key in ("title", "observation", "implication", "caveat"):
                if isinstance(insight.get(key), str):
                    parts.append((f"insights[{i}].{key}", insight[key]))
    for path, value in parts:
        problems.extend(_text_problems(path, value))
    return problems


def _text_problems(path, value):
    problems = []
    if any(ch.isdigit() for ch in value):
        problems.append(f"{path} must not contain digits; put exact figures in citations")
    if _INVESTMENT_ACTION.search(value):
        problems.append(f"{path} contains prohibited investment action or target-price language")
    if any(ch.isalpha() and "LATIN" not in unicodedata.name(ch, "") for ch in value):
        problems.append(f"{path} must use Latin-script narrative")
    return problems


# An insight's prose fields; each may carry an English twin ``<key>_en``
# written in the same call. The twin shares the insight's citations.
_PROSE_KEYS = ("title", "observation", "implication", "caveat")
_PROSE_LIMITS = {"title": 240}


def _english_problems(ticker, insight, payload_by_endpoint):
    """Problems with one insight's English twin; [] when it has none.

    A twin passes the Indonesian narrative rules (no digits, no investment
    action, Latin script), reads English, and makes no trend, repetition,
    flow-direction or search-coverage claim that the shared citations do not
    support. The cross-link quality rule (naming the ticker, metric and article
    subject) stays with the Indonesian: it checks which evidence the card is
    about, and a faithful translation of a passing card is about the same
    evidence, while its article-title keyword may rightly be translated away."""
    from app import prose_lang
    if not isinstance(insight, dict) or not any(f"{key}_en" in insight for key in _PROSE_KEYS):
        return []
    problems = []
    for key in _PROSE_KEYS:
        id_text, en_text = insight.get(key), insight.get(f"{key}_en")
        path = f"{key}_en"
        if not isinstance(id_text, str) or not id_text.strip():
            continue  # _clean_english keeps no twin without its Indonesian
        if not isinstance(en_text, str) or not en_text.strip():
            problems.append(f"{path} missing")
            continue
        problems.extend(_text_problems(path, en_text))
        if en_text.strip() == id_text.strip() or prose_lang.mixed(en_text):
            problems.append(f"{path} must be an English translation, not Indonesian")
    english = {key: insight.get(f"{key}_en") for key in _PROSE_KEYS}
    english["citations"] = insight.get("citations") or []
    claims = _trend_problems(english, payload_by_endpoint)
    if _TEMPORAL_REPETITION.search(" ".join(str(english.get(key) or "") for key in _PROSE_KEYS)) and \
            _repetition_anchor_count(english, payload_by_endpoint) < 2:
        claims.append("repetition claim requires at least two distinct cited article or period anchors")
    claims += _news_flow_direction_problems(ticker, english, payload_by_endpoint)
    claims += _search_coverage_problems(english, payload_by_endpoint)
    problems.extend(f"English {claim}" for claim in claims)
    return problems


def _document_english_problems(ticker, document, payload_by_endpoint):
    """Every English-twin problem in `document`, prefixed with its insight."""
    return [f"insights[{index}].{problem}"
            for index, insight in enumerate(document.get("insights") or [])
            for problem in _english_problems(ticker, insight, payload_by_endpoint)]


def _drop_bad_english(ticker, document, payload_by_endpoint):
    """Drop every English twin of an insight whose twin fails; return notes.

    A missing or invalid twin never fails the brief: the insight keeps its
    validated Indonesian and the report falls back to it."""
    notes = []
    for index, insight in enumerate(document.get("insights") or []):
        if not isinstance(insight, dict):
            continue
        if not any(f"{key}_en" in insight for key in _PROSE_KEYS):
            notes.append(f"insights[{index}] has no English twin")
            continue
        problems = _english_problems(ticker, insight, payload_by_endpoint)
        if problems:
            for key in _PROSE_KEYS:
                insight.pop(f"{key}_en", None)
            notes.append(f"insights[{index}] English twin dropped: " + "; ".join(problems[:3]))
    return notes


def _clean_english(row):
    """The cleaned English twins of a model insight row."""
    out = {}
    for key in _PROSE_KEYS:
        text = _clean_text(row.get(f"{key}_en"), _PROSE_LIMITS.get(key, 1200))
        if text and _clean_text(row.get(key)):
            out[f"{key}_en"] = text
    return out


def _host_enrich_citations(ticker, final, evidence):
    """Replace model-authored citation values with exact scalar cache values."""
    if not isinstance(final, dict) or not isinstance(final.get("insights"), list):
        return final, ["final.insights must be a list"]
    payloads = {item["endpoint"]: item["payload"] for item in evidence}
    enriched = dict(final)
    enriched_rows = []
    problems = []
    # Publish at most three claims. Discarding extras is safe because every
    # retained claim still passes the full citation and narrative validator.
    for i, row in enumerate(final["insights"][:MAX_INSIGHTS]):
        if not isinstance(row, dict):
            enriched_rows.append(row)
            continue
        clean = dict(row)
        citations = row.get("citations")
        if not isinstance(citations, list):
            enriched_rows.append(clean)
            continue
        clean_citations = []
        for j, citation in enumerate(citations):
            if not isinstance(citation, dict):
                clean_citations.append(citation)
                continue
            endpoint, field_path = citation.get("endpoint"), citation.get("field_path")
            if not isinstance(endpoint, str) or endpoint not in payloads:
                problems.append(f"insights[{i}].citations[{j}] endpoint was not read")
                continue
            try:
                value, canonical_path = _resolve_or_recover_pointer(
                    payloads[endpoint], field_path, endpoint=endpoint)
            except (ValueError, IndexError, TypeError):
                problems.append(
                    f"insights[{i}].citations[{j}] path does not resolve uniquely: "
                    f"{field_path!r} in {endpoint}")
                continue
            if isinstance(value, (dict, list)) or value is None:
                problems.append(f"insights[{i}].citations[{j}] must point to a scalar cache value")
                continue
            clean_citations.append({"endpoint": endpoint, "field_path": canonical_path,
                                    "value": value})
        clean["citations"] = clean_citations
        enriched_rows.append(clean)
    enriched["insights"] = enriched_rows
    return enriched, problems


def _citation_anchor(payload, pointer):
    """Return (metric leaf, period anchor, is_explicit) for a cache pointer."""
    parts = pointer[1:].split("/") if isinstance(pointer, str) and pointer.startswith("/") else []
    parts = [part.replace("~1", "/").replace("~0", "~") for part in parts]
    value = payload
    anchors = []
    for part in parts:
        if isinstance(value, dict):
            for key, item in value.items():
                if re.search(r"(period|date|year|quarter|timestamp|as.of|fiscal)", str(key), re.I) and \
                        isinstance(item, (str, int)):
                    anchors.append(str(item))
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            break
    leaf = parts[-1].lower() if parts else ""
    explicit = bool(anchors)
    anchor = anchors[-1] if anchors else ""
    if not anchor:
        # Array order is a useful fallback for date-indexed cache series.
        index_parts = [(i, int(part)) for i, part in enumerate(parts) if part.isdigit()]
        if index_parts:
            anchor = f"array:{index_parts[-1][1]:012d}"
    return leaf, anchor, explicit


def _anchor_key(anchor):
    if anchor.startswith("array:"):
        return ("array", int(anchor.split(":", 1)[1]))
    value = anchor.strip().lower()
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[t ].*)?", value)
    if iso:
        return ("date", *(int(x) for x in iso.groups()))
    quarter = re.fullmatch(r"(?:fy\s*)?(\d{4})[- /]?q([1-4])", value)
    if quarter:
        return ("period", int(quarter.group(1)), int(quarter.group(2)))
    year = re.fullmatch(r"(?:fy\s*)?(\d{4})", value)
    if year:
        return ("year", int(year.group(1)))
    return None


def _trend_problems(insight, payload_by_endpoint):
    text = " ".join(str(insight.get(key) or "") for key in
                    ("title", "observation", "implication", "caveat"))
    trend_text = re.sub(
        r"(?:does not|doesn't|cannot|can not|no|not)\s+(?:establish|show|prove|indicate)?\s*"
        r"(?:a\s+)?(?:trend|momentum|trajectory)|"
        r"(?:tidak|belum)\s+(?:menunjukkan|membuktikan|mencerminkan)?\s*(?:tren|momentum|kecenderungan)",
        "", text, flags=re.I)
    if not _TREND.search(trend_text):
        return []
    points = []
    for citation in insight.get("citations", []):
        if not isinstance(citation, dict):
            continue
        endpoint = citation.get("endpoint")
        if not isinstance(endpoint, str):
            continue
        payload = payload_by_endpoint.get(endpoint)
        if payload is None:
            continue
        value = citation.get("value")
        numeric = _numeric_values(value)
        if not numeric:
            continue
        leaf, anchor, explicit = _citation_anchor(payload, citation.get("field_path"))
        if leaf:
            points.append((endpoint, leaf, citation.get("field_path"),
                          next(iter(numeric)), anchor, explicit))
    # Compare only one metric from one endpoint; separate metrics/endpoints
    # cannot be stitched into a time series by the narrative.
    groups = {}
    for point in points:
        groups.setdefault((point[0], point[1]), []).append(point)
    valid_pairs = []
    for group in groups.values():
        distinct = {p[2]: p for p in group}
        ordered = sorted(distinct.values(), key=lambda p: _anchor_key(p[4]) or ("unknown", p[4]))
        if len(ordered) >= 2 and ordered[0][4] != ordered[-1][4]:
            keys = [_anchor_key(p[4]) for p in ordered]
            comparable = all(keys) and len({key[0] for key in keys}) == 1
            if comparable and (not (ordered[0][5] or ordered[-1][5]) or all(p[5] for p in ordered[:2])):
                valid_pairs.append(ordered)
    if not valid_pairs:
        return ["trend/change claim requires at least two distinct period-anchored numeric citations for the same metric"]
    normalized_text = re.sub(r"[^a-z0-9]+", " ", trend_text.lower())
    normalized_tokens = normalized_text.split()
    named_pairs = []
    for pair in valid_pairs:
        leaf = pair[0][1]
        base = re.sub(r"[^a-z0-9]+", " ", leaf).strip()
        aliases = _METRIC_ALIASES.get(leaf, (base,))
        names_metric = False
        for alias in aliases:
            tokens = re.sub(r"[^a-z0-9]+", " ", alias.lower()).split()
            if tokens and any(normalized_tokens[i:i + len(tokens)] == tokens
                              for i in range(len(normalized_tokens) - len(tokens) + 1)):
                names_metric = True
                break
        if names_metric:
            named_pairs.append(pair)
    if not named_pairs:
        return ["trend claim does not identify which cited metric is changing"]
    valid_pairs = named_pairs
    values = valid_pairs[0]
    if _VOLATILE_TREND.search(trend_text):
        if len(values) < 3 or not any((values[i + 1][3] - values[i][3]) *
                                      (values[i + 2][3] - values[i + 1][3]) < 0
                                      for i in range(len(values) - 2)):
            return ["volatility claim is not supported by a direction-changing cited series"]
    elif _UP_TREND.search(trend_text) and _DOWN_TREND.search(trend_text):
        changes = [values[i + 1][3] - values[i][3] for i in range(len(values) - 1)]
        if not (any(change > 0 for change in changes) and
                any(change < 0 for change in changes)):
            return ["mixed-direction trend claim does not match a rising and falling cited series"]
    elif _UP_TREND.search(trend_text) and values[-1][3] <= values[0][3]:
        return ["upward trend claim conflicts with cited values"]
    elif _DOWN_TREND.search(trend_text) and values[-1][3] >= values[0][3]:
        return ["downward trend claim conflicts with cited values"]
    return []


def _repetition_anchor_count(insight, payload_by_endpoint):
    news_articles = set()
    period_groups = {}
    for citation in insight.get("citations", []):
        if not isinstance(citation, dict) or not isinstance(citation.get("endpoint"), str):
            continue
        endpoint = citation["endpoint"]
        path = citation.get("field_path")
        payload = payload_by_endpoint.get(endpoint)
        if payload is None or not isinstance(path, str):
            continue
        if endpoint == "/news/":
            match = re.match(r"^/results/(\d+)/(timestamp|title|body|source)$", path)
            if match:
                news_articles.add(match.group(1))
            continue
        leaf, anchor, explicit = _citation_anchor(payload, path)
        if leaf and anchor:
            period_groups.setdefault((endpoint, leaf), set()).add(anchor)
    if len(news_articles) >= 2:
        return len(news_articles)
    return max((len(anchors) for anchors in period_groups.values()), default=0)


def _near_entity_term(text, entities, terms):
    entity_patterns = []
    for name in entities:
        if not isinstance(name, str) or not name.strip():
            continue
        # Company names often vary in whitespace or omit the legal prefix.
        words = name.strip().split()
        entity_patterns.append(r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b")
    if not entity_patterns:
        return False
    entity = "(?:" + "|".join(entity_patterns) + ")"
    pattern = re.compile(rf"(?:{entity}.{{0,55}}(?:{terms})|(?:{terms}).{{0,55}}{entity})", re.I | re.S)
    entity_alternatives = "|".join(entity_patterns)
    other_entity = re.compile(
        r"\b(other stocks?|other commodities|other sectors|elsewhere|"
        r"saham lain|komoditas lain|sektor lain|emiten lain|bukan\s+(?:" +
        entity_alternatives + r"))\b", re.I)
    clauses = re.split(r"[.;!?\n]|\b(?:while|whereas|but|although|however|sedangkan|sementara|namun)\b",
                       text, flags=re.I)
    return any(pattern.search(clause) and not other_entity.search(clause)
               for clause in clauses)


def _news_flow_direction_problems(ticker, insight, payload_by_endpoint):
    narrative = " ".join(str(insight.get(key) or "") for key in
                         ("title", "observation", "implication", "caveat"))
    narrative_positive = bool(_POSITIVE_FLOW.search(narrative))
    narrative_negative = bool(_NEGATIVE_FLOW.search(narrative))
    if not (narrative_positive or narrative_negative):
        return []
    rows = (payload_by_endpoint.get("/news/") or {}).get("results") or []
    report = payload_by_endpoint.get(f"/company/report/{ticker.upper()}/") or {}
    company_name = report.get("company_name") or (report.get("overview") or {}).get("company_name")
    entities = [ticker.upper()]
    if isinstance(company_name, str):
        entities.append(company_name)
        normalized_name = re.sub(r"\s+", " ", company_name.strip())
        if normalized_name.lower().startswith("pt "):
            entities.append(normalized_name[3:])
    cited_indices = {match.group(1) for citation in insight.get("citations", [])
                     if isinstance(citation, dict) and citation.get("endpoint") == "/news/"
                     and isinstance(citation.get("field_path"), str)
                     if (match := re.match(r"^/results/(\d+)/", citation["field_path"]))}
    for index in cited_indices:
        try:
            article = rows[int(index)]
        except (ValueError, IndexError, TypeError):
            continue
        symbols = {str(symbol).upper() for symbol in article.get("symbols", [])}
        if ticker.upper() not in symbols and f"{ticker.upper()}.JK" not in symbols:
            continue
        source_text = "\n".join(str(article.get(key) or "")
                               for key in ("title", "body", "summary"))
        negative_near_entity = _near_entity_term(source_text, entities, _NEGATIVE_FLOW.pattern)
        positive_near_entity = _near_entity_term(source_text, entities, _POSITIVE_FLOW.pattern)
        if narrative_positive and negative_near_entity and not positive_near_entity:
            return ["positive ticker-specific flow claim conflicts with cited article's ticker-specific outflow/pressure"]
        if narrative_negative and positive_near_entity and not negative_near_entity:
            return ["negative ticker-specific flow claim conflicts with cited article's ticker-specific inflow/accumulation"]
    return []


def _search_coverage_problems(insight, payload_by_endpoint):
    narrative = " ".join(str(insight.get(key) or "") for key in
                         ("title", "observation", "implication", "caveat"))
    if not _SEARCH_COVERAGE_CLAIM.search(narrative):
        return []
    for citation in insight.get("citations", []):
        if not isinstance(citation, dict) or not isinstance(citation.get("endpoint"), str):
            continue
        endpoint = citation["endpoint"]
        path = citation.get("field_path")
        payload = payload_by_endpoint.get(endpoint)
        if payload is None or not isinstance(path, str):
            continue
        if not re.search(r"(?:^|/)(?:pagination|page_info|paging)(?:/|$)", path, re.I):
            continue
        try:
            value = _pointer(payload, path)
        except (ValueError, IndexError, TypeError):
            continue
        leaf = path.rsplit("/", 1)[-1].lower()
        if leaf in {"page", "page_size", "limit", "offset", "showing", "total_count",
                    "total_pages", "has_next", "has_previous", "next_page", "next_offset"} and \
                value is not None:
            return []
    return ["search-page or result-completeness claim requires an exact cited cache pagination field"]


def _contains_quarterly_metric(payload):
    # Only operational/financial leaves count as useful quarter evidence. Do not
    # treat arbitrary numeric metadata (row IDs, periods, counts, pagination) as
    # a metric that forces a cross-reference.
    metric_keys = {
        "revenue", "gross_loan", "net_loan", "loans", "loan", "total_loans",
        "total_deposit", "deposits", "deposit", "current_account", "savings_account",
        "time_deposit", "interest_income", "interest_expense", "net_interest_income",
        "non_interest_income", "operating_expense", "operating_pnl", "earnings",
        "earnings_before_tax", "net_income", "net_profit", "gross_profit", "ebit",
        "ebitda", "operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
        "net_cash_flow", "free_cash_flow", "total_assets", "total_liabilities",
        "total_equity", "production", "production_volume", "sales_volume", "capacity",
        "utilization", "operating_margin", "net_margin",
    }

    def walk(value, key=""):
        if isinstance(value, bool) or value is None:
            return False
        if isinstance(value, (int, float)):
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            return normalized in metric_keys
        if isinstance(value, dict):
            return any(walk(child, str(child_key)) for child_key, child in value.items())
        if isinstance(value, list):
            return any(walk(child, key) for child in value)
        return False

    return walk(payload)


def _has_news_and_quarterly_citation(insights, quarterly_endpoint):
    if not isinstance(insights, list):
        return False
    for insight in insights:
        if not isinstance(insight, dict):
            continue
        endpoints = {citation.get("endpoint") for citation in
                     (insight.get("citations") or []) if isinstance(citation, dict)}
        if "/news/" in endpoints and quarterly_endpoint in endpoints:
            return True
    return False


def _has_relevant_ticker_news(ticker, news_payload, as_of):
    """Whether cached news has an in-date article explicitly tagged to ticker."""
    if not isinstance(news_payload, dict) or not isinstance(as_of, str):
        return False
    rows = news_payload.get("results")
    if not isinstance(rows, list):
        return False
    symbols = {ticker.upper(), f"{ticker.upper()}.JK"}
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_symbols = row.get("symbols")
        stamp = str(row.get("timestamp") or "")
        if (isinstance(row_symbols, list) and symbols.intersection(
                str(symbol).upper() for symbol in row_symbols) and
                re.match(r"^\d{4}-\d{2}-\d{2}", stamp) and stamp[:10] <= as_of):
            return True
    return False


def _relevant_news_indices(ticker, news_payload, as_of):
    rows = news_payload.get("results") if isinstance(news_payload, dict) else None
    if not isinstance(rows, list) or not isinstance(as_of, str):
        return []
    symbols = {ticker.upper(), f"{ticker.upper()}.JK"}
    return [index for index, row in enumerate(rows)
            if isinstance(row, dict) and isinstance(row.get("symbols"), list) and
            symbols.intersection(str(symbol).upper() for symbol in row["symbols"]) and
            re.match(r"^\d{4}-\d{2}-\d{2}", str(row.get("timestamp") or "")) and
            str(row["timestamp"])[:10] <= as_of]


def _quarterly_metric_paths(payload, limit=8):
    paths = []

    def escape(segment):
        return str(segment).replace("~", "~0").replace("/", "~1")

    def walk(value, path=""):
        if len(paths) >= limit:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}/{escape(key)}"
                if (not isinstance(child, (dict, list, bool)) and child is not None and
                        _contains_quarterly_metric({str(key): child})):
                    paths.append(child_path)
                else:
                    walk(child, child_path)
                if len(paths) >= limit:
                    break
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}/{index}")
                if len(paths) >= limit:
                    break

    walk(payload)
    return paths


def _has_phrase(text, phrase):
    words = re.sub(r"[^a-z0-9]+", " ", str(phrase).lower()).strip()
    if not words:
        return False
    return re.search(r"(?:^|\s)" + re.escape(words) + r"(?:$|\s)",
                     re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()) is not None


def _article_subject_hint(article, ticker):
    article_text = " ".join(str(article.get(key) or "") for key in ("title", "body"))
    for canonical, first_group, second_group, _aliases in _COMPOSITE_ARTICLE_SUBJECTS:
        first_found = any(_has_phrase(article_text, alias) for alias in first_group)
        second_found = any(_has_phrase(article_text, alias) for alias in second_group)
        if first_found and second_found:
            return canonical
    for aliases in _ARTICLE_SUBJECT_ALIASES.values():
        for alias in aliases:
            if _has_phrase(article_text, alias):
                return alias
    stopwords = {"about", "after", "also", "article", "bank", "company", "context",
                 "from", "into", "market", "news", "report", "that", "their", "this",
                 "with", "yang", "dalam", "untuk", "pada", "terkait", "tentang",
                 ticker.lower()}
    candidates = [word for word in re.findall(r"[a-z]{4,}", str(article.get("title") or "").lower())
                  if word not in stopwords]
    return candidates[0] if candidates else ""


def _article_subject_aliases(hint):
    for canonical, _first, _second, aliases in _COMPOSITE_ARTICLE_SUBJECTS:
        if hint == canonical:
            return aliases
    return next((aliases for aliases in _ARTICLE_SUBJECT_ALIASES.values()
                 if hint in aliases), (hint,))


def _quarter_news_context(ticker, quarterly_endpoint, news_payload, quarter_payload, as_of_date):
    indices = _relevant_news_indices(ticker, news_payload, as_of_date)
    quarter_paths = _quarterly_metric_paths(quarter_payload, limit=1)
    if not indices or not quarter_paths:
        return "", []
    article_index = indices[0]
    article = news_payload["results"][article_index]
    metric_path = quarter_paths[0]
    metric_leaf = metric_path.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
    metric_aliases = _METRIC_ALIASES.get(metric_leaf, (re.sub(r"[_-]+", " ", metric_leaf),))
    metric_label = metric_aliases[0] if metric_aliases else metric_leaf
    subject_hint = _article_subject_hint(article, ticker) or "operasi"
    news_paths = [f"/results/{article_index}/{field}"
                  for field in ("title", "body", "timestamp", "source")]
    example_card = {
        "title": f"Konteks {subject_hint} dan {metric_label}",
        "observation": f"Cache mengaitkan {ticker} dengan artikel tentang {subject_hint}.",
        "implication": f"Catatan kuartalan {ticker} mencatat {metric_label}; ini memberi konteks untuk membaca bahasan {subject_hint}.",
        "caveat": "Artikel tidak mengukur dampak pada kinerja emiten.",
        "title_en": "Article context and quarterly metric",
        "observation_en": f"The cache links {ticker} to an article on the subject named in its title.",
        "implication_en": (f"The {ticker} quarterly record states the cited metric; this gives "
                           "context for reading the article's subject."),
        "caveat_en": "The article does not measure the effect on the issuer's performance.",
        "citations": ([{"endpoint": "/news/", "field_path": path} for path in news_paths] +
                      [{"endpoint": quarterly_endpoint, "field_path": metric_path}]),
    }
    context = (
        "KONTEKS WAJIB CROSS-LINK: keluarkan tepat SATU insight, tanpa insight lain. "
        "Judul artikel yang harus diangkat: " + json.dumps(article.get("title"), ensure_ascii=False) +
        "; label metric kuartalan yang harus disebut: " + json.dumps(metric_label, ensure_ascii=False) +
        ". Jembatan deskriptif: metric ini memberi konteks untuk membaca subjek artikel, bukan bukti sebab-akibat. "
        "Gunakan tepat object JSON contoh berikut; pertahankan pointer persis dan jangan menghapus segmen path: " +
        json.dumps(example_card, ensure_ascii=False) + ". Pointer berita wajib persis: " +
        json.dumps(news_paths, ensure_ascii=False) + "; pointer metrik kuartalan wajib persis: " +
        json.dumps(quarter_paths, ensure_ascii=False) + ". Jangan menebak atau mengubah path. Semua prose tanpa digit, "
        "tahun/periode, bahasa Buy/Sell/Hold/target, klaim arus positif/negatif, atau klaim sebab-akibat. "
        "Jangan membuat klaim arah arus kecuali dinyatakan eksplisit untuk ticker ini dalam artikel yang dicite. "
        "Deskripsikan konteks saja. Field _en adalah terjemahan Inggris setia dari field Indonesia "
        "yang sama, menyebut subjek dan metric yang sama dalam bahasa Inggris.")
    article_fields = {field: article.get(field) for field in ("title", "body", "timestamp", "source")}
    metric_value = _pointer(quarter_payload, metric_path)
    compact = [
        {"role": "system", "content": (
            "Return JSON only as {\"final\":{...}}. The selected cache facts below are the entire allowed evidence. "
            "Produce exactly one insight, cite only exact supplied pointers, and write prose without digits, "
            "investment-action language, unsupported flow direction, or causal claims. Do not add claims or a second insight. "
            "The insight also carries title_en, observation_en, implication_en and caveat_en: a faithful English "
            "translation of the Indonesian fields under the same rules, with no citations of its own.")},
        {"role": "user", "content": (
            "Selected relevant article fields: " + json.dumps(article_fields, ensure_ascii=False) +
            ". Selected quarterly metric: " +
            json.dumps({"field_path": metric_path, "value": metric_value}, ensure_ascii=False) +
            ". " + context)},
    ]
    return context, compact


def _crosslink_quality_problems(ticker, insight, payload_by_endpoint):
    citations = insight.get("citations") if isinstance(insight, dict) else None
    if not isinstance(citations, list):
        return []
    narrative = " ".join(str(insight.get(key) or "") for key in
                         ("title", "observation", "implication", "caveat"))
    news_citations = [citation for citation in citations if isinstance(citation, dict) and
                      citation.get("endpoint") == "/news/"]
    quarter_citations = [citation for citation in citations if isinstance(citation, dict) and
                         isinstance(citation.get("endpoint"), str) and
                         citation.get("endpoint", "").startswith("/financials/quarterly/")]
    if not news_citations or not quarter_citations:
        return []
    problems = []
    report = payload_by_endpoint.get(f"/company/report/{ticker.upper()}/") or {}
    company = report.get("company_name") or (report.get("overview") or {}).get("company_name")
    entities = [ticker.upper()]
    if isinstance(company, str):
        entities.append(company)
        short = re.sub(r"\s+", " ", company.strip())
        if short.lower().startswith("pt "):
            entities.append(short[3:])
    if not any(_has_phrase(narrative, entity) for entity in entities if entity):
        problems.append("cross-linked insight must name the ticker or cached company name")

    quarterly_endpoint = quarter_citations[0].get("endpoint")
    metric_leaf = ""
    for citation in quarter_citations:
        try:
            value = _pointer(payload_by_endpoint[quarterly_endpoint], citation.get("field_path"))
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if isinstance(value, (dict, list)) or value is None:
            continue
        metric_leaf = citation["field_path"].rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
        break
    if metric_leaf:
        metric_aliases = _METRIC_ALIASES.get(
            metric_leaf, (re.sub(r"[_-]+", " ", metric_leaf),))
        if not any(_has_phrase(narrative, alias) for alias in metric_aliases):
            problems.append("cross-linked insight must describe the cited quarterly metric")
    else:
        problems.append("cross-linked insight must cite one usable quarterly metric")

    news_payload = payload_by_endpoint.get("/news/") or {}
    rows = news_payload.get("results") or []
    article_indices = {match.group(1) for citation in news_citations
                       if isinstance(citation.get("field_path"), str)
                       if (match := re.match(r"^/results/(\d+)/", citation["field_path"]))}
    article = None
    for article_index in article_indices:
        try:
            article = rows[int(article_index)]
            break
        except (ValueError, IndexError, TypeError):
            continue
    if isinstance(article, dict):
        subject_hint = _article_subject_hint(article, ticker)
        aliases = _article_subject_aliases(subject_hint)
        subject_named = any(_has_phrase(narrative, alias) for alias in aliases if alias)
        if not subject_named:
            problems.append("cross-linked insight must identify a meaningful subject from the cited article")
    else:
        problems.append("cross-linked insight has no resolvable cited article")
    return problems


_NO_EVIDENCE_LIMITATION = "Belum ada bukti cache yang lolos validasi."
_NEWS_LIMITATION = "Konteks media tidak mengukur pendapatan atau arus kas emiten secara langsung."
_QUARTERLY_LIMITATION = "Angka kuartalan historis tidak membuktikan hubungan sebab-akibat atau kinerja mendatang."
_FLOW_LIMITATION = "Arus historis tidak memastikan arus mendatang atau dampak pada laba emiten."
_COMPANY_LIMITATION = "Snapshot perusahaan hanya menggambarkan data pada tanggal laporan."
_WITHHELD_QUARTERLY_LIMITATION = "The quarterly cross-reference was withheld because its citation did not pass validation."


def _expected_limitations(insights, cross_reference=None):
    endpoints = {citation.get("endpoint") for insight in insights
                 if isinstance(insight, dict)
                 for citation in (insight.get("citations") or [])
                 if isinstance(citation, dict) and isinstance(citation.get("endpoint"), str)}
    limitations = []
    if "/news/" in endpoints:
        limitations.append(_NEWS_LIMITATION)
    if any(endpoint.startswith("/financials/quarterly/") for endpoint in endpoints):
        limitations.append(_QUARTERLY_LIMITATION)
    if any(endpoint.startswith("/foreign-flow/") for endpoint in endpoints):
        limitations.append(_FLOW_LIMITATION)
    if any(endpoint.startswith("/company/report/") for endpoint in endpoints):
        limitations.append(_COMPANY_LIMITATION)
    if not limitations:
        limitations.append(_NO_EVIDENCE_LIMITATION)
    if isinstance(cross_reference, dict) and cross_reference.get("status") == "withheld":
        limitations.append(_WITHHELD_QUARTERLY_LIMITATION)
    return limitations


def _validate_document(ticker, document, evidence):
    problems = []
    if not isinstance(document, dict):
        return ["document must be an object"]
    if str(document.get("ticker", "")).upper() != ticker.upper():
        problems.append("ticker mismatch")
    if not isinstance(document.get("summary"), str) or not document["summary"].strip():
        problems.append("summary missing")
    expected_summary = ("Brief ini merangkum temuan cache yang lolos validasi."
                        if document.get("insights") else
                        "Belum ada temuan yang lolos validasi.")
    if document.get("summary") != expected_summary:
        problems.append("summary must be deterministic host text")
    problems.extend(_narrative_problems(document))
    insights = document.get("insights")
    if not isinstance(insights, list) or len(insights) > MAX_INSIGHTS:
        problems.append("insights must be a list with at most three items")
        return problems
    trace = document.get("agent_trace") if isinstance(document.get("agent_trace"), dict) else {}
    validation_trace = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
    cross_reference = validation_trace.get("cross_reference")
    if isinstance(cross_reference, dict) and cross_reference.get("status") == "withheld":
        expected_quarterly = f"/financials/quarterly/{ticker.upper()}/"
        if cross_reference.get("endpoint") != expected_quarterly:
            problems.append("withheld cross-reference endpoint is invalid")
        if expected_quarterly not in trace.get("selected_cache_endpoints", []):
            problems.append("withheld cross-reference endpoint was not read")
    expected_limitations = _expected_limitations(insights, cross_reference)
    if document.get("limitations") != expected_limitations:
        problems.append("limitations must be deterministic and derived from cited endpoint types")
    payload_by_endpoint = {item["endpoint"]: item["payload"] for item in evidence}
    for index, insight in enumerate(insights):
        prefix = f"insights[{index}]"
        if not isinstance(insight, dict):
            problems.append(f"{prefix} must be an object")
            continue
        for field in ("observation", "implication", "caveat"):
            if not isinstance(insight.get(field), str) or not insight[field].strip():
                problems.append(f"{prefix}.{field} missing")
        citations = insight.get("citations")
        if not isinstance(citations, list) or not citations:
            problems.append(f"{prefix} requires a cache citation")
            continue
        cited_numbers = set()
        for ci, citation in enumerate(citations):
            cp = f"{prefix}.citations[{ci}]"
            if not isinstance(citation, dict):
                problems.append(f"{cp} must be an object")
                continue
            endpoint = citation.get("endpoint")
            path = citation.get("field_path")
            if not isinstance(endpoint, str) or endpoint not in payload_by_endpoint:
                problems.append(f"{cp} endpoint was not read")
                continue
            try:
                exact_value = _pointer(payload_by_endpoint[endpoint], path)
            except (ValueError, IndexError, TypeError):
                problems.append(f"{cp} path does not resolve")
                continue
            if isinstance(exact_value, (dict, list)) or exact_value is None:
                problems.append(f"{cp} must cite a scalar cache value")
                continue
            if "value" not in citation:
                problems.append(f"{cp} citation value was not host-enriched")
                continue
            if exact_value != citation.get("value"):
                problems.append(f"{cp} value does not match cache")
                continue
            cited_numbers.update(_numeric_values(exact_value))
        news_paths = [c.get("field_path", "") for c in citations
                      if isinstance(c, dict) and c.get("endpoint") == "/news/"]
        if news_paths:
            article_indices = {m.group(1) for path in news_paths
                               if (m := re.match(r"^/results/(\d+)/", path))}
            complete = False
            news_payload = payload_by_endpoint.get("/news/") or {}
            results = news_payload.get("results") or []
            for article_index in article_indices:
                article_prefix = f"/results/{article_index}/"
                required = {article_prefix + field
                            for field in ("title", "body", "timestamp", "source")}
                if not required.issubset(set(news_paths)):
                    continue
                try:
                    article = results[int(article_index)]
                except (ValueError, IndexError, TypeError):
                    continue
                symbols = {str(x).upper() for x in article.get("symbols", [])}
                stamp = str(article.get("timestamp") or "")
                if (document.get("as_of") and
                        (ticker.upper() in symbols or f"{ticker.upper()}.JK" in symbols) and
                        stamp[:10] <= document["as_of"]):
                    complete = True
                    break
            if not complete:
                problems.append(f"{prefix} news citation requires exact title, body, timestamp, and source for the same in-date ticker article")
        problems.extend(f"{prefix} {problem}" for problem in
                        _trend_problems(insight, payload_by_endpoint))
        insight_text = " ".join(str(insight.get(key) or "") for key in
                                ("title", "observation", "implication", "caveat"))
        if _TEMPORAL_REPETITION.search(insight_text) and \
                _repetition_anchor_count(insight, payload_by_endpoint) < 2:
            problems.append(f"{prefix} repetition claim requires at least two distinct cited article or period anchors")
        problems.extend(f"{prefix} {problem}" for problem in
                        _news_flow_direction_problems(ticker, insight, payload_by_endpoint))
        problems.extend(f"{prefix} {problem}" for problem in
                        _crosslink_quality_problems(ticker, insight, payload_by_endpoint))
        problems.extend(f"{prefix} {problem}" for problem in
                        _search_coverage_problems(insight, payload_by_endpoint))
        claim_text = " ".join(str(insight.get(k) or "") for k in
                              ("title", "observation", "implication", "caveat"))
        for number in _numbers_in_text(claim_text):
            if not any(abs(number - supported) <= max(1e-9, abs(number) * 1e-8)
                       for supported in cited_numbers):
                problems.append(f"{prefix} has unsupported numeric claim: {number:g}")
    quarterly_endpoint = f"/financials/quarterly/{ticker.upper()}/"
    quarter_payload = payload_by_endpoint.get(quarterly_endpoint)
    news_payload = payload_by_endpoint.get("/news/")
    report_payload = payload_by_endpoint.get(f"/company/report/{ticker.upper()}/")
    news_relevant = _has_relevant_ticker_news(ticker, news_payload, _as_of(
        [{"endpoint": f"/company/report/{ticker.upper()}/", "payload": report_payload}]
        if report_payload is not None else []))
    if (news_relevant and quarter_payload is not None and
            _contains_quarterly_metric(quarter_payload) and
            not _has_news_and_quarterly_citation(insights, quarterly_endpoint)):
        problems.append("relevant cached news and quarterly evidence must be connected in the same insight")
    as_of = document.get("as_of")
    if as_of is not None and (not isinstance(as_of, str) or
                              not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of)):
        problems.append("as_of must be an ISO date or null")
    return problems


def validate_against_cache(ticker, document, as_of=None):
    """Return ``(sanitized_document, problems)`` after current-cache checks.

    `as_of`, when provided by report intake, must match the cached report date.
    No writes or upstream reads occur during this validation.
    """
    ticker = ticker.strip().upper()
    if not isinstance(document, dict):
        return None, ["document must be an object"]
    allowed = set(cache_tools.cache_endpoints(ticker))
    evidence = []
    report_endpoint = f"/company/report/{ticker}/"
    if report_endpoint in allowed:
        report_payload = cache_tools.cache_get(ticker, report_endpoint)
        if report_payload is not None:
            evidence.append({"endpoint": report_endpoint, "payload": report_payload})
    for endpoint in sorted({c.get("endpoint") for insight in
                            (document.get("insights") or [])
                            if isinstance(insight, dict)
                            for c in (insight.get("citations") or [])
                            if isinstance(c, dict) and isinstance(c.get("endpoint"), str)}):
        if endpoint not in allowed:
            continue
        payload = cache_tools.cache_get(ticker, endpoint)
        if payload is not None:
            evidence.append({"endpoint": endpoint, "payload": payload})
    # The run trace records cache endpoints read even if the model omitted a
    # citation. Re-read a valid quarter endpoint so persisted artifacts cannot
    # evade the news/quarter same-card rule by omitting that citation.
    trace = document.get("agent_trace") if isinstance(document.get("agent_trace"), dict) else {}
    selected = trace.get("selected_cache_endpoints")
    quarterly_endpoint = f"/financials/quarterly/{ticker}/"
    if isinstance(selected, list) and quarterly_endpoint in selected:
        for endpoint in (quarterly_endpoint, "/news/"):
            if endpoint not in allowed or endpoint in {item["endpoint"] for item in evidence}:
                continue
            payload = cache_tools.cache_get(ticker, endpoint)
            if payload is not None:
                evidence.append({"endpoint": endpoint, "payload": payload})
    problems = _validate_document(ticker, document, evidence)
    current_as_of = _as_of(evidence)
    requested_as_of = as_of or current_as_of
    if as_of is not None and as_of != current_as_of:
        problems.append("report as_of does not match current cached close date")
    if document.get("as_of") != requested_as_of:
        problems.append("document as_of does not match current report as_of")
    if problems:
        return None, problems
    # Rebuild the public contract so unexpected persisted fields do not leak.
    clean = {
        "ticker": ticker,
        "as_of": requested_as_of,
        "status": document.get("status"),
        "summary": _clean_text(document.get("summary"), 1800),
        "insights": [],
        "limitations": [_clean_text(x, 500) for x in document.get("limitations", [])
                        if isinstance(x, str) and _clean_text(x, 500)][:8],
        "agent_trace": document.get("agent_trace") if isinstance(document.get("agent_trace"), dict) else {},
    }
    for insight in document.get("insights", []):
        item = {key: _clean_text(insight.get(key), 1200)
                for key in ("observation", "implication", "caveat")}
        if isinstance(insight.get("title"), str):
            item["title"] = _clean_text(insight["title"], 240)
        item.update(_clean_english(insight))
        item["citations"] = [{"endpoint": c["endpoint"],
                              "field_path": c["field_path"],
                              "value": c["value"]}
                             for c in insight["citations"]]
        clean["insights"].append(item)
    # English twins are checked again on the current cache; one that no longer
    # passes is dropped, never failing the brief.
    payload_by_endpoint = {item["endpoint"]: item["payload"] for item in evidence}
    if any(_english_problems(ticker, insight, payload_by_endpoint) for insight in clean["insights"]):
        notes = [note for note in _drop_bad_english(ticker, clean, payload_by_endpoint)
                 if "dropped" in note]
        trace = dict(clean["agent_trace"])
        validation = dict(trace.get("validation") or {})
        validation["english_problems"] = list(validation.get("english_problems") or []) + notes
        trace["validation"] = validation
        clean["agent_trace"] = trace
    return clean, []


def _fallback_document(ticker, evidence, reason, repair_attempts=0, rejected=None):
    endpoints = [item["endpoint"] for item in evidence]
    limitations = _expected_limitations([])
    return {"ticker": ticker, "as_of": _as_of(evidence),
            "status": "insufficient_evidence", "summary": "Belum ada temuan yang lolos validasi.",
            "insights": [], "limitations": limitations,
            "agent_trace": {"selected_cache_endpoints": endpoints,
                            "tool_calls": [{"endpoint": ep, "cache_hit": True}
                                           for ep in endpoints],
                            "validation": {"accepted": False,
                                           "rejected_claims": list(rejected or []) + [reason],
                                           "repair_attempted": repair_attempts > 0,
                                           "repair_attempts": repair_attempts}}}


def _candidate_document(ticker, final, evidence, rejected=None, repair_attempts=0):
    source_insights = final.get("insights") if isinstance(final, dict) else None
    discarded_insights = max(0, len(source_insights) - MAX_INSIGHTS) \
        if isinstance(source_insights, list) else 0
    enriched, enrichment_problems = _host_enrich_citations(ticker, final, evidence)
    source_rows = enriched.get("insights") if isinstance(enriched.get("insights"), list) else []
    raw_insights = []
    for row in source_rows[:MAX_INSIGHTS]:
        if not isinstance(row, dict):
            raw_insights.append(row)
            continue
        clean_row = {key: _clean_text(row.get(key))
                     for key in ("observation", "implication", "caveat")}
        if isinstance(row.get("title"), str):
            clean_row["title"] = _clean_text(row["title"], 240)
        clean_row.update(_clean_english(row))
        clean_row["citations"] = [
            {"endpoint": citation.get("endpoint"),
             "field_path": citation.get("field_path"),
             "value": citation.get("value")}
            for citation in (row.get("citations") or [])
            if isinstance(citation, dict)
        ]
        raw_insights.append(clean_row)
    doc = {
        "ticker": ticker,
        "as_of": _as_of(evidence),
        "status": "research_brief" if raw_insights else "insufficient_evidence",
        "summary": ("Brief ini merangkum temuan cache yang lolos validasi."
                    if raw_insights else "Belum ada temuan yang lolos validasi."),
        "insights": raw_insights,
        "limitations": _expected_limitations(raw_insights),
    }
    problems = enrichment_problems + _validate_document(ticker, doc, evidence)
    endpoints = [item["endpoint"] for item in evidence]
    doc["agent_trace"] = {
        "selected_cache_endpoints": endpoints,
        "tool_calls": [{"endpoint": ep, "cache_hit": True} for ep in endpoints],
        "validation": {"accepted": not problems and bool(doc["insights"]),
                       "rejected_claims": list(rejected or []) + problems[:20] +
                       ([f"host capped insight list at {MAX_INSIGHTS}; extras were discarded"]
                        if discarded_insights else []),
                       "repair_attempted": repair_attempts > 0,
                       "repair_attempts": repair_attempts},
    }
    return doc, problems


_ENGLISH_REPAIR = (
    "Pertahankan title_en, observation_en, implication_en, caveat_en tiap insight sebagai "
    "terjemahan Inggris setia dari field Indonesia yang sama, dengan aturan narasi yang sama. "
    "Masalah yang menyebut field _en atau English hanya menyangkut terjemahan Inggris: perbaiki "
    "terjemahannya dan pertahankan narasi Indonesia yang sudah lolos. ")


def _useful_unread_endpoints(ticker, allowlist, seen):
    quarterly = f"/financials/quarterly/{ticker}/"
    ranked = []
    for endpoint in allowlist - seen:
        if endpoint == quarterly:
            rank = 0
        elif endpoint == "/news/":
            rank = 1
        elif endpoint.startswith(("/mining/companies/", "/foreign-flow/")):
            rank = 2
        elif any(tag in endpoint for tag in ("/financials/", "/company/corporate-actions/")):
            rank = 3
        else:
            rank = 5
        if rank < 5:
            ranked.append((rank, endpoint))
    return [endpoint for _, endpoint in sorted(ranked)]


def _emit_read(endpoint, payload):
    emit("research", f"{endpoint} terbaca" if payload is not None else f"{endpoint} kosong",
         status="ok" if payload is not None else "warn", tool="cache_get", agent="riset")


def run_live(ticker, *, max_tool_calls=MAX_TOOL_CALLS, persist=True,
             db=None):
    """Run the bounded cache-only agent and persist its sanitized brief.

    The returned object includes the research document and a machine-readable
    trace. `persist=False` is useful for callers that only need a preview.
    """
    ticker = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.-]{1,12}", ticker):
        raise ValueError("ticker format is invalid")
    endpoints = cache_tools.cache_endpoints(ticker)
    allowlist = set(endpoints)
    evidence = []
    messages = [
        {"role": "system", "content": (
            "Kamu analis riset emiten. Host hanya menyediakan tool cache_get; "
            "kamu tidak punya akses web, PDF, dokumen lokal, atau sumber lain. "
            "Minta satu endpoint dari allowlist per giliran dengan JSON "
            "{\"tool\":\"cache_get\",\"args\":[TICKER,ENDPOINT]}. Setelah data "
            "diberikan, kamu boleh memilih endpoint berikutnya. Maksimal tiga insight. "
            "Akhiri dengan {\"final\":{...}} berisi ticker, as_of (tanggal atau null), "
            "status, summary kosong, insights, limitations. Host membuat summary sendiri. "
            "Setiap insight punya observation, "
            "implication, caveat, citations. Setiap citation hanya {endpoint, field_path}; "
            "field_path adalah RFC6901 JSON Pointer ke payload yang dibaca. "
            "Saat memberi final, citations hanya berisi endpoint dan field_path; jangan "
            "mengeluarkan value karena host akan mengisinya dari cache. Semua narasi "
            "(summary, limitations, title, observation, implication, caveat) dilarang "
            "memuat digit atau bahasa tindakan investasi, penilaian harga, dan disclaimer "
            "kepatuhan. Jangan menyebutkan bahwa kamu tidak memberi saran; caveat harus "
            "menjelaskan batas bukti saja. Angka hanya boleh berada di value citation yang "
            "diisi host. Default gunakan satu snapshot: observation menyebut kategori "
            "fakta yang tercatat, implication menjelaskan konteks bisnis secara kualitatif, "
            "caveat menyebut batas data, bukan batas produk. Contoh aman: observation "
            "'Cache mencatat pendapatan perusahaan pada catatan terbaru.'; implication "
            "'Catatan ini memberi konteks untuk memahami aktivitas usaha.'; caveat "
            "'Satu catatan belum menjelaskan dampak terhadap laba atau arus kas.' "
            "Jangan mengklaim jumlah halaman, kelengkapan hasil pencarian, atau bahwa hanya "
            "halaman awal yang tersedia kecuali cache memiliki metadata pagination yang "
            "secara eksplisit dicite. Gunakan caveat berbasis isi, misalnya berita tidak "
            "mengukur dampak pada pendapatan, laba, atau arus kas emiten. "
            "Hindari semua kata yang mengklaim perubahan waktu seperti naik, turun, "
            "membaik, menurun, meningkat, memburuk, trend, momentum, improve, increase, "
            "decline, volatile atau rebound kecuali mencantumkan dua atau lebih citation "
            "angka untuk metric yang sama, periode pembanding yang jelas, dan nama metric "
            "tersebut di kalimat. Lebih aman tidak membuat klaim perubahan. Jika data "
            "kurang, berikan insights kosong dan limitations umum tanpa insight. "
            "Jika menafsirkan berita dari /news/, cantumkan empat citation untuk artikel "
            "yang sama: title, body, timestamp, dan source (URL), semuanya leaf scalar. "
            "Contoh: [{\"endpoint\":\"/news/\",\"field_path\":\"/results/0/title\"}, "
            "{\"endpoint\":\"/news/\",\"field_path\":\"/results/0/body\"}, "
            "{\"endpoint\":\"/news/\",\"field_path\":\"/results/0/timestamp\"}, "
            "{\"endpoint\":\"/news/\",\"field_path\":\"/results/0/source\"}]. "
            "Setiap insight juga membawa bahasa Inggrisnya dalam jawaban yang sama: title_en, "
            "observation_en, implication_en, caveat_en, masing-masing terjemahan setia dari field "
            "Indonesia yang sama. Terjemahan Inggris mengikuti semua aturan narasi di atas (tanpa "
            "digit, tanpa bahasa tindakan investasi, tanpa klaim perubahan waktu yang tidak didukung "
            "citation), ditulis sepenuhnya dalam bahasa Inggris, dan tidak punya citation sendiri; "
            "citation insight berlaku untuk kedua bahasa. "
            "Kembalikan JSON saja."
        )},
        {"role": "user", "content": (
            f"Ticker: {ticker}. Pilih endpoint relevan dari allowlist berikut; baca data "
            "sebelum menyimpulkan. Utamakan berita ticker-spesifik, operasional, "
            "keuangan, aksi korporasi, dan ringkasan perusahaan bila ada. "
            "Jangan meminta lebih dari yang diperlukan. Allowlist: " +
            json.dumps(endpoints, ensure_ascii=False))},
    ]
    seen = set()
    report_endpoint = f"/company/report/{ticker}/"
    if report_endpoint in allowlist:
        emit("research", f"Membaca {report_endpoint}", "baseline dibaca host sebelum agent memilih",
             status="run", tool="cache_get", agent="riset")
        report_payload = cache_tools.cache_get(ticker, report_endpoint)
        _emit_read(report_endpoint, report_payload)
        if report_payload is not None:
            evidence.append({"endpoint": report_endpoint, "payload": report_payload})
            seen.add(report_endpoint)
            close_date = _as_of(evidence)
            messages[1]["content"] += (
                f"\nHost sudah membaca {report_endpoint}; as_of yang benar adalah "
                f"{close_date!r}. Payload disediakan sebagai baseline cache: " +
                json.dumps(report_payload, ensure_ascii=False))
    max_calls = max(0, min(int(max_tool_calls), MAX_TOOL_CALLS,
                           len(allowlist) - len(seen)))
    final = None
    final_raw = None
    prior_valid_news_document = None
    failure = "agent did not return a valid final document"
    format_repair_used = False
    empty_final_nudged = False
    news_quarterly_nudged = False
    quarter_news_checked = False
    empty_final_needs_insight = False
    quarter_news_required_context = ""
    quarter_news_compact_messages = []
    tool_calls_made = 0
    for _ in range(max_calls + 3):
        raw, finish_reason = _response_text(_chat(messages))
        try:
            action = _parse_json(raw)
        except (ValueError, json.JSONDecodeError):
            if format_repair_used:
                failure = f"invalid JSON after bounded format repair (finish_reason={finish_reason})"
                break
            format_repair_used = True
            repair_messages = messages + [
                {"role": "assistant", "content": raw[:8000]},
                {"role": "user", "content": (
                    "Format responsmu menjadi satu object JSON valid {\"final\":{...}} "
                    "menggunakan hanya bukti cache yang sudah tersedia pada percakapan. "
                    "Jangan meminta atau menjalankan tool lagi. Citation hanya endpoint dan "
                    "field_path. Buat narasi kualitatif tanpa digit, disclaimer, bahasa "
                    "penilaian investasi, atau klaim perubahan waktu. Summary boleh kosong. "
                    "Pertahankan title_en, observation_en, implication_en, caveat_en tiap insight. "
                    "Jangan sertakan markdown, komentar, atau teks di luar JSON.")},
            ]
            repair_finish = "unknown"
            try:
                repair_raw, repair_finish = _response_text(_chat(repair_messages))
                action = _parse_json(repair_raw)
            except (ValueError, json.JSONDecodeError):
                failure = f"invalid JSON after bounded format repair (finish_reason={repair_finish})"
                break
            if not isinstance(action, dict) or not isinstance(action.get("final"), dict):
                failure = "format repair did not return a final document"
                break
            if action.get("tool"):
                failure = "format repair attempted a tool call; repaired tool calls are not executed"
                break
            raw, finish_reason = repair_raw, repair_finish
        if isinstance(action, dict) and action.get("tool"):
            args = action.get("args")
            if action.get("tool") != "cache_get" or not isinstance(args, list) or len(args) != 2:
                failure = "agent requested an unsupported tool call"
                break
            requested_ticker, endpoint = args
            if (str(requested_ticker).upper() != ticker or endpoint not in allowlist or
                    endpoint in seen):
                failure = "agent requested an out-of-scope or repeated cache endpoint"
                break
            if tool_calls_made >= max_calls:
                failure = "agent exceeded the bounded cache-read budget"
                break
            tool_calls_made += 1
            seen.add(endpoint)
            emit("research", f"Membaca {endpoint}", status="run", tool="cache_get", agent="riset")
            payload = cache_tools.cache_get(ticker, endpoint)
            _emit_read(endpoint, payload)
            if payload is None:
                messages.extend([
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": json.dumps(
                        {"tool_result": None, "endpoint": endpoint}, ensure_ascii=False)},
                ])
                continue
            evidence.append({"endpoint": endpoint, "payload": payload})
            messages.extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": json.dumps(
                    {"tool_result": payload, "endpoint": endpoint}, ensure_ascii=False)},
            ])
            continue
        if isinstance(action, dict) and isinstance(action.get("final"), dict):
            candidate_final = action["final"]
            candidate_insights = candidate_final.get("insights")
            quarterly_endpoint = f"/financials/quarterly/{ticker}/"
            quarter_payload = next((item["payload"] for item in evidence
                                    if item["endpoint"] == quarterly_endpoint), None)
            news_payload = next((item["payload"] for item in evidence
                                 if item["endpoint"] == "/news/"), None)
            if (not quarter_news_checked and quarter_payload is not None and
                    _contains_quarterly_metric(quarter_payload) and
                    "/news/" in allowlist and "/news/" not in seen):
                quarter_news_checked = True
                if tool_calls_made >= max_calls:
                    failure = "cannot verify relevant cached news within the bounded cache-read budget"
                    break
                seen.add("/news/")
                tool_calls_made += 1
                emit("research", "Membaca /news/", "host memeriksa berita untuk kuartal yang dibaca",
                     status="run", tool="cache_get", agent="riset")
                news_payload = cache_tools.cache_get(ticker, "/news/")
                _emit_read("/news/", news_payload)
                if news_payload is not None:
                    evidence.append({"endpoint": "/news/", "payload": news_payload})
                    if _has_relevant_ticker_news(ticker, news_payload, _as_of(evidence)):
                        quarter_news_required_context, quarter_news_compact_messages = _quarter_news_context(
                            ticker, quarterly_endpoint, news_payload, quarter_payload, _as_of(evidence))
                    if quarter_news_required_context:
                        messages.extend([
                            {"role": "assistant", "content": raw[:8000]},
                            {"role": "user", "content": (
                                "Host membaca /news/ karena ditemukan artikel relevan. Jangan gunakan "
                                "angka dari payload dalam prose; angka hanya boleh ada pada citation values "
                                "yang akan host isi. " + quarter_news_required_context +
                                " Payload berita: " + json.dumps(news_payload, ensure_ascii=False) +
                                " Payload kuartalan: " + json.dumps(quarter_payload, ensure_ascii=False))},
                        ])
                        continue
            if (not quarter_news_compact_messages and quarter_payload is not None and
                    news_payload is not None and _contains_quarterly_metric(quarter_payload) and
                    _has_relevant_ticker_news(ticker, news_payload, _as_of(evidence))):
                quarter_news_required_context, quarter_news_compact_messages = _quarter_news_context(
                    ticker, quarterly_endpoint, news_payload, quarter_payload, _as_of(evidence))
            cites_news = any(isinstance(row, dict) and
                             any(isinstance(c, dict) and c.get("endpoint") == "/news/"
                                 for c in (row.get("citations") or []))
                             for row in (candidate_insights or [])
                             if isinstance(candidate_insights, list))
            if (cites_news and not news_quarterly_nudged and
                    quarterly_endpoint in allowlist and quarterly_endpoint not in seen and
                    tool_calls_made < max_calls):
                prior_candidate, prior_problems = _candidate_document(
                    ticker, candidate_final, evidence)
                if not prior_problems:
                    prior_valid_news_document = prior_candidate
                news_quarterly_nudged = True
                messages.extend([
                    {"role": "assistant", "content": raw[:8000]},
                    {"role": "user", "content": (
                        f"Satu langkah evidence tambahan sebelum final: host belum membaca "
                        f"{quarterly_endpoint}. Minta cache_get untuk endpoint ini. Setelah "
                        "hasil tersedia, jika ada metrik operasional atau finansial yang "
                        "relevan, hubungkan konteks berita ke metrik tersebut secara "
                        "deskriptif dan cite nilai yang tepat. Jangan menyatakan hubungan "
                        "sebab-akibat; bila metrik tidak mendukung kaitan, jelaskan bahwa "
                        "berita tidak mengukur dampak terhadap kinerja emiten.")},
                ])
                continue
            if not candidate_insights and not empty_final_nudged:
                useful_unread = _useful_unread_endpoints(ticker, allowlist, seen)
                if useful_unread and tool_calls_made < max_calls:
                    empty_final_nudged = True
                    messages.extend([
                        {"role": "assistant", "content": raw[:8000]},
                        {"role": "user", "content": (
                            "Sebelum final, periksa setidaknya satu endpoint cache relevan yang "
                            "belum dibaca dari pilihan ini, bila datanya tersedia: " +
                            json.dumps(useful_unread, ensure_ascii=False) +
                            ". Utamakan financials quarterly dan news. Setelah membaca, "
                            "buat satu insight kualitatif dengan citation leaf yang tepat jika "
                            "bukti mendukung; jangan memaksakan kesimpulan. Gunakan pola aman: "
                            "catatan cache menyebut suatu metrik; jelaskan konteks bisnisnya; "
                            "caveat hanya tentang cakupan bukti. Hindari angka, klaim tren, "
                            "disclaimer, dan penilaian investasi.")},
                    ])
                    continue
            final = candidate_final
            final_raw = raw
            empty_final_needs_insight = bool(empty_final_nudged and not candidate_insights and
                any(item["endpoint"] != report_endpoint for item in evidence))
            break
        if format_repair_used:
            failure = "schema repair returned a response without a final document"
            break
        format_repair_used = True
        schema_messages = messages + [
            {"role": "assistant", "content": raw[:8000]},
            {"role": "user", "content": (
                "Your previous response was valid JSON but had the wrong schema. Return only "
                "one object shaped {\"final\":{\"ticker\":\"" + ticker +
                "\",\"as_of\":null,\"status\":\"research_brief\",\"summary\":\"\","
                "\"insights\":[],\"limitations\":[]}}. This is a final-only schema repair: "
                "do not request, include, or attempt a tool call. Use only evidence already present. "
                "Keep narrative qualitative and without digits or investment-action language; citations "
                "must contain endpoint and field_path only. Each insight keeps its English twins "
                "title_en, observation_en, implication_en and caveat_en. Return JSON only.")},
        ]
        try:
            repair_raw, repair_finish = _response_text(_chat(schema_messages))
            repaired_action = _parse_json(repair_raw)
        except (ValueError, json.JSONDecodeError):
            failure = "invalid JSON after bounded schema repair"
            break
        if isinstance(repaired_action, dict) and repaired_action.get("tool"):
            failure = "schema repair attempted a tool call; repaired tool calls are not executed"
            break
        if not isinstance(repaired_action, dict) or not isinstance(repaired_action.get("final"), dict):
            failure = "schema repair did not return a final document"
            break
        action = repaired_action
        raw, finish_reason = repair_raw, repair_finish
        candidate_final = action["final"]
        candidate_insights = candidate_final.get("insights")
        final = candidate_final
        final_raw = raw
        break

    if final is None:
        document = _fallback_document(ticker, evidence, failure)
    else:
        document, issues = _candidate_document(ticker, final, evidence)
        quarterly_endpoint = f"/financials/quarterly/{ticker}/"
        quarter_payload = next((item["payload"] for item in evidence
                                if item["endpoint"] == quarterly_endpoint), None)
        if (news_quarterly_nudged and quarter_payload is not None and
                _contains_quarterly_metric(quarter_payload) and
                not _has_news_and_quarterly_citation(document.get("insights"),
                                                     quarterly_endpoint)):
            issues.append("supplemental quarterly data supports a metric, so one insight must cite both the news article and that quarterly metric")
        if empty_final_needs_insight:
            issues.append("relevant cache endpoints were checked; provide one qualitative cited insight if a specific cache fact supports it, otherwise state the evidence gap without inventing facts")
        repair_attempts = 0
        all_issues = list(issues)
        repair_raw = final_raw or json.dumps(final, ensure_ascii=False)
        payload_by_endpoint = {item["endpoint"]: item["payload"] for item in evidence}
        english = _document_english_problems(ticker, document, payload_by_endpoint)
        # The latest candidate whose Indonesian passed: a repair asked for its
        # English alone must not cost the brief when it breaks the Indonesian.
        best = document if not issues else None
        while (issues or english) and repair_attempts < 2:
            repair_attempts += 1
            if quarter_news_compact_messages:
                repair_messages = quarter_news_compact_messages + [{
                    "role": "user", "content": (
                        "Previous output failed host validation: " +
                        json.dumps(issues + english, ensure_ascii=False) +
                        ". Start over from the exact one-insight JSON skeleton and pointers above. "
                        "Preserve one insight and include all required citations; do not copy previous invalid prose.") }]
            else:
                repair_messages = messages + [
                {"role": "assistant", "content": repair_raw},
                {"role": "user", "content": (
                    f"Perbaiki final JSON, percobaan koreksi {repair_attempts}, berdasarkan "
                    "masalah validasi host berikut: " +
                    json.dumps(issues + english, ensure_ascii=False) +
                    ". Gunakan hanya payload yang sudah diberikan; jangan meminta tool lagi. "
                    "Buat narasi tanpa digit, disclaimer, atau bahasa penilaian investasi. "
                    "Jangan buat klaim temporal; tulis satu snapshot kualitatif dengan caveat "
                    "yang hanya menjelaskan keterbatasan bukti. Gunakan pola aman: observation "
                    "'Cache mencatat pendapatan perusahaan pada catatan terbaru.'; implication "
                    "'Catatan ini memberi konteks untuk memahami aktivitas usaha.'; caveat "
                    "'Satu catatan belum menjelaskan dampak terhadap laba atau arus kas.' "
                    "Jangan buat klaim tentang cakupan pencarian atau kelengkapan halaman; "
                    "gunakan caveat berbasis isi seperti berita tidak mengukur dampak pada "
                    "pendapatan, laba, atau arus kas emiten. "
                    "Untuk berita, kaitkan isi laporan media ke konteks pasokan atau operasi, "
                    "tanpa menyimpulkan dampak finansial. Citation hanya endpoint dan "
                    "field_path; host mengisi value. Summary boleh kosong karena host "
                    "menyediakan summary tetap. Kembalikan satu object "
                    "{\"final\":{...}} lengkap sebagai JSON. " + _ENGLISH_REPAIR +
                    quarter_news_required_context)},
                ]
            try:
                repair_raw, repair_reason = _response_text(_chat(repair_messages))
                repaired = _parse_json(repair_raw)
            except (ValueError, json.JSONDecodeError):
                repaired, repair_reason = None, "invalid repair JSON"
            if not isinstance(repaired, dict) or not isinstance(repaired.get("final"), dict):
                issues = [f"repair response invalid: {repair_reason}"]
                all_issues.extend(issues)
                continue
            final_raw = repair_raw
            document, issues = _candidate_document(
                ticker, repaired["final"], evidence, rejected=all_issues,
                repair_attempts=repair_attempts)
            all_issues.extend(issues)
            english = _document_english_problems(ticker, document, payload_by_endpoint)
            if not issues:
                best = document
        if issues and best is not None:
            best["agent_trace"]["validation"]["rejected_claims"] = all_issues[:20]
            best["agent_trace"]["validation"]["repair_attempted"] = repair_attempts > 0
            best["agent_trace"]["validation"]["repair_attempts"] = repair_attempts
            document, issues = best, []
        if issues:
            if prior_valid_news_document is not None:
                prior_valid_news_document["limitations"].append(_WITHHELD_QUARTERLY_LIMITATION)
                prior_valid_news_document["agent_trace"]["selected_cache_endpoints"] = [
                    item["endpoint"] for item in evidence]
                prior_valid_news_document["agent_trace"]["tool_calls"] = [
                    {"endpoint": item["endpoint"], "cache_hit": True} for item in evidence]
                prior_valid_news_document["agent_trace"]["validation"]["cross_reference"] = {
                    "status": "withheld", "endpoint": f"/financials/quarterly/{ticker}/",
                    "reason": "follow-up citation failed host validation"}
                prior_issues = _validate_document(ticker, prior_valid_news_document, evidence)
            else:
                prior_issues = ["no earlier candidate passed host validation"]
            if prior_valid_news_document is not None and not prior_issues:
                prior_valid_news_document["agent_trace"]["validation"]["rejected_claims"] = all_issues[:20]
                prior_valid_news_document["agent_trace"]["validation"]["repair_attempted"] = repair_attempts > 0
                prior_valid_news_document["agent_trace"]["validation"]["repair_attempts"] = repair_attempts
                document = prior_valid_news_document
            else:
                document = _fallback_document(
                    ticker, evidence,
                    f"bounded repair attempts exhausted: {json.dumps(issues, ensure_ascii=False)}",
                    repair_attempts=repair_attempts, rejected=all_issues + prior_issues)
        if document.get("insights"):
            notes = _drop_bad_english(ticker, document, payload_by_endpoint)
            if notes:
                document["agent_trace"]["validation"]["english_problems"] = notes[:20]

    output_path = None
    if persist:
        from app import research_context, store
        store.put(research_context.COLLECTION, ticker, document, db)
        output_path = f"{research_context.COLLECTION}/{ticker}"
    return {"ok": document["status"] == "research_brief",
            "ticker": ticker, "document": document,
            "path": output_path,
            "agent_trace": document["agent_trace"]}

"""Evidence-first estimator: cache/public evidence -> gate -> driver file."""
from __future__ import annotations

import json
import math
import os
import re
import shlex
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.estimator import prompt as P
from agents.estimator import tools as T
from agents.estimator.schema import REQUIRED_SERIES
from agents.estimator.validate import gate

_LLM_ENV_KEYS = frozenset({
    "SEKTORAL_LLM_BASE_URL", "SEKTORAL_LLM_API_KEY", "SEKTORAL_LLM_MODEL",
    "MINIMAX_API_KEY",
})


def _load_dotenv(path=None):
    """Load only LLM settings from .env, without overriding process environment."""
    env_path = Path(path) if path else Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in _LLM_ENV_KEYS or key in os.environ:
            continue
        try:
            parts = shlex.split(value, comments=True, posix=True)
        except ValueError:
            continue
        os.environ[key] = " ".join(parts)


def _chat(messages, max_tokens=4000):
    """Call the configured OpenAI-compatible chat endpoint."""
    _load_dotenv()
    base = os.environ.get("SEKTORAL_LLM_BASE_URL", "https://api.minimax.io/v1").rstrip("/")
    key = os.environ.get("SEKTORAL_LLM_API_KEY", "") or os.environ.get("MINIMAX_API_KEY", "")
    model = os.environ.get("SEKTORAL_LLM_MODEL", "MiniMax-M3")
    if not key:
        raise RuntimeError("LLM key tidak ditemukan. Set SEKTORAL_LLM_API_KEY "
                           "atau MINIMAX_API_KEY di environment atau .env.")
    if "api.minimax.io" in base and not model.startswith("MiniMax-"):
        raise ValueError("model untuk api.minimax.io harus MiniMax-*; override base URL "
                         "untuk provider lain.")
    if not (base and model):
        raise RuntimeError("LLM belum dikonfigurasi (SEKTORAL_LLM_BASE_URL/MODEL)")

    token_limit = max(max_tokens, 131072) if model == "MiniMax-M3" else max_tokens
    request_body = {"model": model, "messages": messages,
                    "max_completion_tokens": token_limit, "temperature": 0.2}
    if model == "MiniMax-M3":
        request_body["thinking"] = {"type": "disabled"}
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(request_body).encode(),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as response:
        output = json.loads(response.read().decode())
    choice = output["choices"][0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content
                          if isinstance(part, dict))
    return {"content": content, "finish_reason": choice.get("finish_reason"),
            "usage": output.get("usage")}


def _response_text(response):
    """Accept structured provider metadata and simple string test adapters."""
    if isinstance(response, str):
        return response, None
    if not isinstance(response, dict):
        return "", None
    return str(response.get("content") or ""), response.get("finish_reason")


def _repair_message(raw, finish_reason, problems=None):
    """Give the model the exact failed candidate and actionable gate errors."""
    raw = raw[:8000]
    reason = f"finish_reason={finish_reason!r}. " if finish_reason else ""
    if problems:
        return ("Perbaiki kandidat drivers berikut supaya lolos gate. " + reason +
                "Pelanggaran: " + json.dumps(problems, ensure_ascii=False) +
                "\nKandidat sebelumnya: " + raw +
                "\nKembalikan seluruh object drivers lengkap sebagai JSON valid, "
                "jangan mengarang sumber atau angka.")
    return ("Respons awal bukan JSON valid dan/atau terpotong. " + reason +
            "Kandidat sebelumnya: " + raw +
            "\nKembalikan ulang satu object drivers lengkap sebagai JSON valid, "
            "tanpa markdown atau reasoning.")


def _unwrap_candidate(candidate):
    return candidate.get("final", candidate) if isinstance(candidate, dict) else candidate


def _missing_evidence_result(candidate):
    final = _unwrap_candidate(candidate)
    if isinstance(final, dict) and final.get("missing_evidence"):
        return {"error": "bukti belum cukup untuk membuat drivers",
                "missing_evidence": final.get("missing_evidence"),
                "available_facts": final.get("available_facts", [])}
    return None


def _generate_final(messages, years):
    """Generate once, then allow one evidence-preserving repair attempt."""
    raw, finish_reason = _response_text(_chat(messages))
    try:
        candidate = _parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        messages.extend([
            {"role": "assistant", "content": raw[:8000]},
            {"role": "user", "content": _repair_message(raw, finish_reason)},
        ])
        raw, finish_reason = _response_text(_chat(messages))
        try:
            candidate = _parse_json(raw)
        except (ValueError, json.JSONDecodeError):
            return None, {"error": "respons LLM bukan JSON valid setelah satu repair",
                          "finish_reason": finish_reason}

    missing = _missing_evidence_result(candidate)
    if missing:
        return None, missing
    final = _unwrap_candidate(candidate)
    problems = gate(final, len(years))
    if problems:
        messages.extend([
            {"role": "assistant", "content": raw[:8000]},
            {"role": "user", "content": _repair_message(raw, finish_reason, problems)},
        ])
        repaired, repair_reason = _response_text(_chat(messages))
        try:
            candidate = _parse_json(repaired)
        except (ValueError, json.JSONDecodeError):
            return None, {"error": "repair gate menghasilkan JSON tidak valid",
                          "finish_reason": repair_reason, "problems": problems}
        missing = _missing_evidence_result(candidate)
        if missing:
            return None, missing
        final = _unwrap_candidate(candidate)
        problems = gate(final, len(years))
        if problems:
            return None, {"error": "gate menolak setelah satu repair",
                          "finish_reason": repair_reason, "problems": problems}
    return final, None


def _parse_json(text):
    """Parse JSON after stripping MiniMax <think>...</think> or fences."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object")
    return json.loads(cleaned[start:end + 1])


def plan(ticker, years):
    """Inventory cached evidence without calling the LLM."""
    endpoints = T.cache_endpoints(ticker)
    return {"ticker": ticker.upper(), "years": years,
            "cache_endpoints": endpoints, "n_endpoints": len(endpoints),
            "tools": sorted(T.TOOLS)}


def run_live(ticker, years, agentic=False):
    """Read evidence, optionally let the LLM select cache reads, then gate."""
    normalized_ticker = ticker.upper()
    endpoints = T.cache_endpoints(normalized_ticker)
    evidence_log = [f"cache_endpoints({normalized_ticker}) -> {endpoints}"]
    calls = build_cache_calls(normalized_ticker, endpoints)
    public_evidence = public_forecast_evidence(normalized_ticker)
    if agentic:
        return _run_agentic_with_evidence(
            normalized_ticker, years, endpoints, evidence_log, calls, public_evidence)
    return _run_with_evidence(
        normalized_ticker, years, endpoints, evidence_log, calls, public_evidence)


def _run_agentic_with_evidence(ticker, years, endpoints, evidence_log, calls,
                               public_evidence, max_tool_calls=4):
    """Bounded JSON tool-use loop; the model chooses cache reads, host executes them."""
    allowed_endpoints = {call["args"][1] for call in calls}
    if not allowed_endpoints:
        return {"ok": False, "error": "tidak ada endpoint cache untuk diperiksa",
                "evidence": evidence_log}

    messages = [
        {"role": "system", "content": (
            "Kamu research agent. Kamu boleh meminta host membaca cache lokal Sectors "
            "dengan JSON {\"tool\":\"cache_get\",\"args\":[TICKER,ENDPOINT]}. "
            "Endpoint harus persis dari allowlist. Host yang menjalankan tool; kamu tidak "
            "punya akses langsung ke database/network. Setelah membaca minimal satu hasil, "
            "kembalikan JSON final: {\"final\":{\"decision\":\"ready\","
            "\"selected_cache_endpoints\":[...],\"reason\":\"...\"}} jika bukti cukup, "
            "atau {\"final\":{\"missing_evidence\":[...],"
            "\"available_facts\":[...]}} jika tidak. Jangan keluarkan prosa/markdown."
        )},
        {"role": "user", "content": (
            f"Ticker {ticker}; tahun {', '.join(years)}.\n"
            "Pilih endpoint relevan satu per giliran dan tunggu hasil tool sebelum memilih "
            "lagi atau memberi keputusan final. Minimal satu cache_get wajib sebelum final.\n"
            "Allowlist endpoint: " + json.dumps(sorted(allowed_endpoints)) +
            "\nForecast evidence terstruktur (sumber publik): " +
            json.dumps(public_evidence, ensure_ascii=False)
        )},
    ]
    seen = set()
    cache_evidence = []
    max_calls = min(max_tool_calls, len(allowed_endpoints))

    for _ in range(max_calls + 1):
        raw, finish_reason = _response_text(_chat(messages))
        try:
            action = _parse_json(raw)
        except (ValueError, json.JSONDecodeError):
            return {"ok": False, "error": "agent tidak mengembalikan JSON valid",
                    "finish_reason": finish_reason, "evidence": evidence_log}

        if isinstance(action, dict) and action.get("tool"):
            tool = action.get("tool")
            args = action.get("args")
            if tool != "cache_get" or not isinstance(args, list) or len(args) != 2:
                return {"ok": False, "error": "agent meminta tool/argumen yang tidak diizinkan",
                        "evidence": evidence_log}
            requested_ticker, endpoint = args
            if (str(requested_ticker).upper() != ticker or endpoint not in allowed_endpoints or
                    endpoint in seen):
                return {"ok": False, "error": "agent meminta endpoint di luar allowlist atau duplikat",
                        "requested_endpoint": endpoint, "evidence": evidence_log}
            try:
                result = T.cache_get(ticker, endpoint)
            except Exception as error:  # noqa: BLE001 — keep tool failures in the trace
                result = {"tool_error": type(error).__name__, "message": str(error)[:200]}
            if isinstance(result, dict) and isinstance(result.get("data"), list):
                result = {**result, "data": result["data"][:6]}
            seen.add(endpoint)
            cache_evidence.append({"endpoint": endpoint, "result": result})
            evidence_log.append(f"agent cache_get({ticker}, {endpoint}) -> {str(result)[:300]}")
            messages.extend([
                {"role": "assistant", "content": raw[:8000]},
                {"role": "user", "content": (
                    "Tool result (read-only JSON): " +
                    json.dumps(cache_evidence[-1], ensure_ascii=False)[:12000] +
                    "\nPilih endpoint lain dari allowlist yang belum dibaca, atau beri "
                    "keputusan final sesuai schema. Jangan mengarang data."
                )},
            ])
            continue

        final = _unwrap_candidate(action) if isinstance(action, dict) else None
        missing = _missing_evidence_result(action)
        if missing:
            return {"ok": False, **missing, "evidence": evidence_log}
        if not isinstance(final, dict) or not seen:
            return {"ok": False, "error": "agent final tanpa cache tool evidence",
                    "evidence": evidence_log}

        candidate = _forecast_candidate(ticker, years, public_evidence)
        structured_source = candidate is not None
        if structured_source:
            if (final.get("decision") != "ready" or
                    not isinstance(final.get("selected_cache_endpoints"), list) or
                    not set(final["selected_cache_endpoints"]).issubset(seen) or
                    not final["selected_cache_endpoints"]):
                return {"ok": False, "error": "keputusan agent tidak mereferensikan cache yang dibaca",
                        "agent_final": final, "evidence": evidence_log}
            problems = gate(candidate, len(years))
            if problems:
                return {"ok": False, "error": "gate menolak evidence terstruktur",
                        "problems": problems, "evidence": evidence_log}
        else:
            candidate = final.get("drivers", final)
            problems = gate(candidate, len(years))
            if problems:
                return {"ok": False, "error": "gate menolak agent final",
                        "problems": problems, "evidence": evidence_log}

        path = T.write_drivers(ticker, candidate)
        method = "agentic-structured-source" if structured_source else "agentic-llm"
        decision = "ready" if structured_source else "drivers_submitted"
        return {"ok": True, "path": str(path), "method": method,
                "agent_tool_calls": len(seen),
                "agent_decision": {"decision": decision,
                                   "selected_cache_endpoints": sorted(seen)},
                "evidence": evidence_log}

    return {"ok": False, "error": f"agent mencapai batas {max_calls} cache tool calls",
            "evidence": evidence_log}


def _forecast_candidate(ticker, years, evidence_rows):
    """Build driver paths directly from source values; never ask the LLM to copy them."""
    selections = {}
    for series in REQUIRED_SERIES:
        for evidence in evidence_rows:
            source_years = evidence.get("years")
            values = evidence.get(series)
            if (not isinstance(source_years, list) or not isinstance(values, list) or
                    len(source_years) != len(values) or not evidence.get("source") or
                    not evidence.get("url")):
                continue
            indexed = dict(zip(source_years, values))
            if not all(year in indexed for year in years):
                continue
            path = [indexed[year] for year in years]
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                       and math.isfinite(value) for value in path):
                continue
            selections[series] = (evidence, path)
            break

    if len(selections) != len(REQUIRED_SERIES):
        return None
    currencies = {evidence.get("currency") for evidence, _ in selections.values()}
    if len(currencies) != 1 or not next(iter(currencies)):
        return None

    drivers = {}
    for series, (evidence, path) in selections.items():
        source = f"{evidence['source']} — {evidence['url']}"
        note = (f"Direct published forecast from {evidence['source']}; "
                "single-source estimate, not consensus.")
        if series == "capex" and evidence.get("capex_basis"):
            note += f" Basis: {evidence['capex_basis']}"
        drivers[series] = {"path": path, "source": source, "note": note}

    return {"ticker": ticker, "basis": "agent-estimate",
            "as_of": date.today().isoformat(), "currency": currencies.pop(),
            "years": list(years), "drivers": drivers}


def _run_with_evidence(ticker, years, endpoints, evidence_log, calls, public_evidence):
    evidence_log.append(f"planned_cache_reads={len(calls)}")
    cache_evidence = []
    for call in calls:
        args = call["args"]
        try:
            result = T.cache_get(*args)
        except Exception as error:  # noqa: BLE001 — preserve source failure
            result = {"tool_error": type(error).__name__, "message": str(error)[:200]}
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            result = {**result, "data": result["data"][:6]}
        cache_evidence.append({"endpoint": args[1], "result": result})
        evidence_log.append(f"cache_get({args!r}) -> {str(result)[:300]}")

    # Exact source-provided forecasts are already verified structured facts. Map
    # them directly so the model cannot drop, alter, or detach numeric paths.
    candidate = _forecast_candidate(ticker, years, public_evidence)
    if candidate is not None:
        problems = gate(candidate, len(years))
        if problems:
            return {"ok": False, "error": "gate menolak evidence terstruktur",
                    "problems": problems, "evidence": evidence_log}
        path = T.write_drivers(ticker, candidate)
        return {"ok": True, "path": str(path), "method": "structured-source",
                "evidence": evidence_log}

    messages = [
        {"role": "system", "content": P.SYSTEM},
        {"role": "user", "content": P.user_task(ticker, years) +
         "\nCache actuals (read-only): " + json.dumps(cache_evidence, ensure_ascii=False) +
         "\nPublic forecast evidence: " + json.dumps(public_evidence, ensure_ascii=False) +
         "\nUse only supported values, preserve units, and cite the exact source URL per series. "
         "Do not extrapolate beyond reported years. If a required series/year is unsupported, "
         "return missing_evidence instead of guessing."},
    ]
    final, failure = _generate_final(messages, years)
    if failure:
        return {"ok": False, **failure, "evidence": evidence_log}
    problems = gate(final, len(years))
    if problems:
        return {"ok": False, "error": "gate menolak", "problems": problems,
                "evidence": evidence_log}
    path = T.write_drivers(ticker, final)
    return {"ok": True, "path": str(path), "method": "llm-assisted",
            "evidence": evidence_log}


def public_forecast_evidence(ticker):
    """Structured forecast sources registered for tickers with verified evidence."""
    if ticker.upper() != "AMMN":
        return []
    return [
        {
            "source": "KB Valbury Securities initiation report, 9 June 2026",
            "url": "https://www.kbvalbury.com/cfind/source/files/ammn-initiation-report---09062026.pdf",
            "currency": "USD million",
            "years": ["2026F", "2027F", "2028F"],
            "revenue": [3789, 4179, 4475],
            "ebitda": [1937, 2139, 2558],
            "net_profit": [806, 899, 1170],
            "capex": [1137, 1045, 1119],
            "capex_basis": "fixed-asset investment outflow proxy from the report's projected cash flow; excludes stockpile/mining-property rows",
            "limits": "one analyst report, not consensus; source covers estimates through FY2028 only",
        },
        {
            "source": "AMMAN H1 2026 Earnings Presentation, published 21 Sep 2026",
            "url": "https://www.amman.co.id/earnings-presentation",
            "direct_pdf": "https://www.amman.co.id/rails/active_storage/blobs/proxy/eyJfcmFpbHMiOnsiZGF0YSI6Njc4NiwicHVyIjoiYmxvYl9pZCJ9fQ==--b709bb5b1cfcd4e10d811aac0d9407656a084723/H1%202026%20EARNINGS%20PRESENTATION.pdf?disposition=inline",
            "as_of": "2026-09-21",
            "facts": [
                "H1 2026 audited: net sales USD 2,052mn; EBITDA USD 1,128mn; net income USD 504mn; capex USD 130mn.",
                "2026 guidance: concentrate 900 kdmt; copper in concentrate 485 Mlbs; gold in concentrate revised to 775 koz; copper cathode 130 kt; refined gold 350 koz.",
                "Capex is tapering as major projects near completion; no numeric FY26-28 capex path disclosed.",
            ],
        },
    ]


def build_cache_calls(ticker, endpoints):
    """Pick relevant cache reads in stable, compact priority order."""
    normalized_ticker = ticker.upper()
    priorities = ("/financials/quarterly/", "/company/report/",
                  "/company/get-segments/")
    calls = [{"tool": "cache_get", "args": [normalized_ticker, endpoint]}
             for endpoint in endpoints if any(key in endpoint for key in priorities)]
    for endpoint in (f"/financials/quarterly/{normalized_ticker}/",
                     f"/company/report/{normalized_ticker}/"):
        if endpoint not in [call["args"][1] for call in calls]:
            calls.append({"tool": "cache_get", "args": [normalized_ticker, endpoint]})
    calls.sort(key=lambda call: priorities.index(
        next(key for key in priorities if key in call["args"][1])))
    return calls


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--agentic", action="store_true",
                        help="jalankan loop agent JSON tool-use atas cache Sectors")
    parser.add_argument("--years", default="2026F,2027F,2028F")
    args = parser.parse_args(argv)
    years = [year.strip() for year in args.years.split(",")]
    result = run_live(args.ticker, years, agentic=args.agentic) if args.live else plan(args.ticker, years)
    print(json.dumps(result, indent=1, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()

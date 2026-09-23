"""Evidence-first estimator: sectors_cache only -> gate -> driver file."""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
import urllib.request
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
LLM_GENERATION_BUDGET = 8192


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


def _chat(messages, max_tokens=4000, reasoning_effort="high"):
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

    # MiniMax's Chat API has no separate thinking-token budget. Bound the
    # combined thinking + answer generation to 8k tokens, the closest supported
    # control, while enabling its adaptive thinking mode below.
    token_limit = max(max_tokens, LLM_GENERATION_BUDGET)
    request_body = {"model": model, "messages": messages,
                    "max_completion_tokens": token_limit, "temperature": 0.2}
    if model == "MiniMax-M3":
        # MiniMax exposes adaptive thinking, not an OpenAI-style high level.
        # Its documented adaptive mode is the reasoning-capable setting.
        request_body["thinking"] = {"type": "adaptive"}
    elif reasoning_effort:
        request_body["reasoning_effort"] = reasoning_effort
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(request_body).encode(),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as response:
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
        result = {"error": "bukti belum cukup untuk membuat drivers",
                  "missing_evidence": final.get("missing_evidence"),
                  "available_facts": final.get("available_facts", [])}
        if isinstance(final.get("news_analysis"), list):
            result["news_analysis"] = final["news_analysis"]
        return result
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
    """Use only cached evidence, optionally letting the LLM select cache reads."""
    normalized_ticker = ticker.upper()
    endpoints = T.cache_endpoints(normalized_ticker)
    evidence_log = [f"cache_endpoints({normalized_ticker}) -> {endpoints}"]
    calls = build_cache_calls(normalized_ticker, endpoints)
    if agentic:
        return _run_agentic_with_evidence(
            normalized_ticker, years, endpoints, evidence_log, calls)
    return _run_with_evidence(normalized_ticker, years, evidence_log, calls)


def _run_agentic_with_evidence(ticker, years, endpoints, evidence_log, calls,
                               max_tool_calls=8):
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
            "punya akses ke web atau sumber lain. Setelah membaca hasil, kembalikan "
            "drivers lengkap yang mencantumkan endpoint cache pada tiap source, atau "
            "missing_evidence jika cache tidak cukup. Jika berita cache tersedia, tetap "
            "parafrase dan hubungkan berita meski driver forecast belum cukup. Jangan "
            "keluarkan prosa/markdown."
        )},
        {"role": "user", "content": (
            f"Ticker {ticker}; tahun {', '.join(years)}.\n"
            "Pilih endpoint relevan satu per giliran dan tunggu hasil tool sebelum memilih "
            "lagi atau memberi keputusan final. Minimal satu cache_get wajib. Gunakan hanya "
            "data di payload cache yang dibaca host; jangan gunakan pengetahuan atau sumber "
            "di luar cache. Jika `/news/` ada di allowlist, baca juga dan rangkum berita "
            "relevan dengan parafrasa serta kaitan ke driver/tesis.\nAllowlist endpoint: " +
            json.dumps(sorted(allowed_endpoints))
        )},
    ]
    seen = set()
    available_endpoints = set()
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
            if result is not None and not (isinstance(result, dict) and
                                           result.get("tool_error")):
                available_endpoints.add(endpoint)
            seen.add(endpoint)
            cache_evidence.append({"endpoint": endpoint, "result": result})
            evidence_log.append(f"agent cache_get({ticker}, {endpoint}) -> {str(result)[:300]}")
            messages.extend([
                {"role": "assistant", "content": raw[:8000]},
                {"role": "user", "content": (
                    "Tool result (read-only JSON): " +
                    json.dumps(cache_evidence[-1], ensure_ascii=False)[:12000] +
                    "\nPilih endpoint lain dari allowlist yang belum dibaca, atau kembalikan "
                    "drivers lengkap yang bersumber dari payload yang dibaca / "
                    "missing_evidence. Jangan mengarang data."
                )},
            ])
            continue

        final = _unwrap_candidate(action) if isinstance(action, dict) else None
        missing = _missing_evidence_result(action)
        if missing:
            news_problems = _news_analysis_problems(
                _unwrap_candidate(action), _news_rows(cache_evidence))
            if news_problems:
                return {"ok": False, "error": "news analysis gagal validasi cache",
                        "problems": news_problems, "evidence": evidence_log}
            news_path = (T.write_news_analysis(ticker, _unwrap_candidate(action))
                         if missing.get("news_analysis") else None)
            result = {"ok": False, **missing, "evidence": evidence_log}
            if news_path:
                result["news_analysis_path"] = str(news_path)
            return result
        if not isinstance(final, dict) or not seen:
            return {"ok": False, "error": "agent final tanpa cache tool evidence",
                    "evidence": evidence_log}
        if "/news/" in allowed_endpoints and "/news/" not in seen:
            return {"ok": False, "error": "agent belum membaca news yang tersedia di sectors_cache",
                    "evidence": evidence_log}

        candidate = final
        problems = gate(candidate, len(years))
        cached_news = _news_rows(cache_evidence)
        problems.extend(_cache_source_problems(candidate, available_endpoints, cached_news))
        if problems:
            return {"ok": False, "error": "gate menolak agent final",
                    "problems": problems, "evidence": evidence_log}

        path = T.write_drivers(ticker, candidate)
        news_path = (T.write_news_analysis(ticker, candidate)
                     if candidate.get("news_analysis") else None)
        result = {"ok": True, "path": str(path), "method": "agentic-cache-only",
                "agent_tool_calls": len(seen),
                "agent_decision": {"decision": "drivers_submitted",
                                   "selected_cache_endpoints": sorted(seen)},
                "evidence": evidence_log}
        if news_path:
            result["news_analysis_path"] = str(news_path)
        return result

    return {"ok": False, "error": f"agent mencapai batas {max_calls} cache tool calls",
            "evidence": evidence_log}


def _news_rows(cache_evidence):
    for row in cache_evidence:
        if row.get("endpoint") != "/news/":
            continue
        result = row.get("result")
        if isinstance(result, dict) and isinstance(result.get("results"), list):
            return [item for item in result["results"] if isinstance(item, dict)]
    return []


def _cache_source_problems(candidate, available_endpoints, cached_news=(),
                           require_drivers=True):
    """Require every generated value to cite an endpoint actually read from cache."""
    problems = []
    drivers = candidate.get("drivers") if isinstance(candidate, dict) else None
    if not isinstance(drivers, dict):
        if require_drivers:
            problems.append("drivers tidak ditemukan untuk validasi sumber cache")
    else:
        for series in REQUIRED_SERIES:
            item = drivers.get(series)
            source = item.get("source") if isinstance(item, dict) else None
            if not isinstance(source, str) or not any(
                    endpoint in source for endpoint in available_endpoints):
                problems.append(f"{series}: source harus menyebut endpoint cache yang dibaca")
            if isinstance(source, str) and re.search(r"https?://", source, flags=re.I):
                problems.append(f"{series}: URL eksternal dilarang; gunakan hanya sectors_cache")
    facts = candidate.get("facts") if isinstance(candidate, dict) else None
    if isinstance(facts, list):
        for index, fact in enumerate(facts):
            source = fact.get("source") if isinstance(fact, dict) else None
            if not isinstance(source, str) or not any(
                    endpoint in source for endpoint in available_endpoints):
                problems.append(f"facts[{index}]: source harus menyebut endpoint cache yang dibaca")
            if (isinstance(source, str) and re.search(r"https?://", source, flags=re.I)
                    and not _source_matches_cached_news(source, cached_news)):
                problems.append(f"facts[{index}]: URL eksternal dilarang; gunakan hanya sectors_cache")

    problems.extend(_news_analysis_problems(candidate, cached_news))
    return problems


def _news_analysis_problems(candidate, cached_news):
    problems = []
    news_analysis = candidate.get("news_analysis") if isinstance(candidate, dict) else None
    if cached_news and not news_analysis:
        problems.append("news_analysis wajib merangkum dan menghubungkan berita relevan dari cache")
    if news_analysis is not None:
        if not isinstance(news_analysis, list):
            problems.append("news_analysis harus list")
        else:
            for index, item in enumerate(news_analysis):
                source = item.get("source") if isinstance(item, dict) else None
                if not isinstance(source, str) or "/news/" not in source:
                    problems.append(f"news_analysis[{index}]: source harus menunjuk /news/ di cache")
                    continue
                timestamp = item.get("timestamp") if isinstance(item, dict) else None
                matched_rows = [row for row in cached_news
                                if row.get("title") and row["title"] in source and
                                (not row.get("source") or row["source"] in source) and
                                str(row.get("timestamp") or "") == str(timestamp or "")]
                if not matched_rows:
                    problems.append(f"news_analysis[{index}]: judul, URL, dan timestamp harus cocok persis dengan news cache")
                summary = str(item.get("summary") or "") if isinstance(item, dict) else ""
                matched = matched_rows[0] if matched_rows else None
                if matched and (summary.strip() == str(matched.get("title") or "").strip()
                                or (summary and summary in str(matched.get("body") or ""))):
                    problems.append(f"news_analysis[{index}]: summary harus diparafrase, bukan salinan")
                if isinstance(source, str):
                    cited_urls = re.findall(r"https?://\S+", source, flags=re.I)
                    allowed_urls = {str(row.get("source")) for row in cached_news
                                    if row.get("source")}
                    if any(url.rstrip(".,;)") not in allowed_urls for url in cited_urls):
                        problems.append(f"news_analysis[{index}]: URL harus berasal persis dari cache")
                connection = str(item.get("connection") or "").strip() \
                    if isinstance(item, dict) else ""
                if len(connection) < 20:
                    problems.append(f"news_analysis[{index}]: connection harus menjelaskan implikasi")
            if len(news_analysis) > 3:
                problems.append("news_analysis: maksimal 3 artikel cache")
    return problems


def _source_matches_cached_news(source, cached_news):
    return isinstance(source, str) and any(
        (row.get("title") and row["title"] in source) or
        (row.get("source") and row["source"] in source)
        for row in cached_news
    )


def _run_with_evidence(ticker, years, evidence_log, calls):
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

    available_endpoints = {
        row["endpoint"] for row in cache_evidence
        if row.get("result") is not None and not (
            isinstance(row.get("result"), dict) and row["result"].get("tool_error"))
    }
    messages = [
        {"role": "system", "content": P.SYSTEM},
        {"role": "user", "content": P.user_task(ticker, years) +
         "\nBukti sectors_cache (read-only): " + json.dumps(cache_evidence, ensure_ascii=False) +
         "\nGunakan hanya bukti tersebut, pertahankan unit, dan cantumkan endpoint cache "
         "yang benar-benar dibaca pada source tiap series. Semua forecast harus berupa "
         "hitungan transparan dari cache dengan asumsi dijelaskan di note. Jika bukti "
         "tidak cukup, return missing_evidence alih-alih menebak."},
    ]
    final, failure = _generate_final(messages, years)
    if failure:
        if failure.get("news_analysis") is not None or (
                failure.get("missing_evidence") and _news_rows(cache_evidence)):
            news_problems = _news_analysis_problems(
                failure, _news_rows(cache_evidence))
            if news_problems:
                return {"ok": False, "error": "news analysis gagal validasi cache",
                        "problems": news_problems, "evidence": evidence_log}
        news_path = (T.write_news_analysis(ticker, failure)
                     if failure.get("news_analysis") else None)
        result = {"ok": False, **failure, "evidence": evidence_log}
        if news_path:
            result["news_analysis_path"] = str(news_path)
        return result
    problems = gate(final, len(years))
    problems.extend(_cache_source_problems(final, available_endpoints,
                                           _news_rows(cache_evidence)))
    if problems:
        return {"ok": False, "error": "gate menolak", "problems": problems,
                "evidence": evidence_log}
    path = T.write_drivers(ticker, final)
    news_path = (T.write_news_analysis(ticker, final)
                 if final.get("news_analysis") else None)
    result = {"ok": True, "path": str(path), "method": "llm-cache-only",
              "evidence": evidence_log}
    if news_path:
        result["news_analysis_path"] = str(news_path)
    return result


def build_cache_calls(ticker, endpoints):
    """Pick relevant cache reads in stable, compact priority order."""
    normalized_ticker = ticker.upper()
    priorities = ("/financials/quarterly/", "/company/report/",
                  "/company/get-segments/", "/news/")
    calls = [{"tool": "cache_get", "args": [normalized_ticker, endpoint]}
             for endpoint in endpoints if any(key in endpoint for key in priorities)]
    for endpoint in (f"/financials/quarterly/{normalized_ticker}/",
                     f"/company/report/{normalized_ticker}/"):
        if endpoint not in [call["args"][1] for call in calls]:
            calls.append({"tool": "cache_get", "args": [normalized_ticker, endpoint]})
    if "/news/" in endpoints and "/news/" not in [
            call["args"][1] for call in calls]:
        calls.append({"tool": "cache_get", "args": [normalized_ticker, "/news/"]})
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

"""Loop agen estimator: rencana -> tools -> draf -> gate -> tulis.

Provider LLM: endpoint chat-completions kompatibel OpenAI via env
  SEKTORAL_LLM_BASE_URL, SEKTORAL_LLM_API_KEY, SEKTORAL_LLM_MODEL.
Tanpa key = mode --dry-run (rencana + bukti cache, tanpa panggilan LLM).
Agen tidak pernah pegang SECTORS_API_KEY dan tidak memanggil upstream.

CLI: python3 -m agents.estimator.run TICKER [--live] [--years 2026F,2027F,2028F]
"""
from __future__ import annotations

import json
import os
import sys
import re
import urllib.request

sys.path.insert(0, str(__file__.rsplit("/agents/", 1)[0]))

from agents.estimator import prompt as P
from agents.estimator import tools as T
from agents.estimator.validate import gate


def _chat(messages, max_tokens=4000):
    """Provider default MiniMax direct; env SEKTORAL_LLM_* bisa override.

    Key dibaca runtime dari env, tidak pernah dicetak, ditulis, atau
    disalin ke repo. Fallback legacy disabled sengaja: tak ada silent
    route ke provider lain.
    """
    base = os.environ.get("SEKTORAL_LLM_BASE_URL", "https://api.minimax.io/v1").rstrip("/")
    key = os.environ.get("SEKTORAL_LLM_API_KEY", "") or os.environ.get("MINIMAX_API_KEY", "")
    model = os.environ.get("SEKTORAL_LLM_MODEL", "MiniMax-M3")
    if not key:
        raise RuntimeError("LLM key tidak ditemukan. Set SEKTORAL_LLM_API_KEY "
                           "atau MINIMAX_API_KEY di environment; tidak ada fallback diam-diam.")
    if "api.minimax.io" in base and not model.startswith("MiniMax-"):
        raise ValueError("model untuk api.minimax.io harus MiniMax-*; override base URL "
                         "untuk provider lain.")
    if not (base and model):
        raise RuntimeError("LLM belum dikonfigurasi "
                           "(SEKTORAL_LLM_BASE_URL/MODEL)")
    if model == "MiniMax-M3":
        max_tokens = max(max_tokens, 8192) # output M3 perlu budget memadai.
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens,
                       "temperature": 0.2}).encode()
    req = urllib.request.Request(
        base + "/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read().decode())
    return out["choices"][0]["message"]["content"]


def _parse_json(text):
    """Parse JSON after stripping MiniMax <think>...</think> or fences."""
    s = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I).strip()
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object")
    return json.loads(s[start:end + 1])


def plan(ticker, years):
    """Fase 1 (tanpa LLM): inventaris bukti cache. Untuk --dry-run."""
    eps = T.cache_endpoints(ticker)
    return {"ticker": ticker.upper(), "years": years,
            "cache_endpoints": eps, "n_endpoints": len(eps),
            "tools": sorted(T.TOOLS)}


def run_live(ticker, years):
    """Fase penuh: LLM + tools (function-calling sederhana via JSON)."""
    t = ticker.upper()
    eps = T.cache_endpoints(t)
    ev = [f"cache_endpoints({t}) -> {eps}"]
    # LLM sees bounded read-only evidence: key report + quarterly financials
    # + segments + actions/shareholders. No upstream Sectors fetch exists.
    evidence = {}
    calls = [{"tool": "cache_get", "args": [t, ep]}
             for ep in eps if any(k in ep for k in
             ("/company/report/", "/financials/quarterly/", "/company/get-segments/",
              "/company/corporate-actions/", "/company/shareholders-composition/"))]
    if not any("/company/report/" in c["args"][1] for c in calls):
        calls.append({"tool": "cache_get", "args": [t, f"/company/report/{t}/"]})
    pending = {"ticker": t, "years": years, "evidence": [], "calls": calls,
               "next": "Panggil 1 cache_get dari daftar calls. Kembalikan "
                       "JSON {tool,args,result,remaining}. Ulangi tiap sisa. "
                       "Setelah semua cache dibaca, balas {final: drivers JSON}. "
                       "Jangan keluarkan final sebelum semua bukti tersedia."}
    ev.append(f"planned_cache_reads={len(calls)}")
    # Bounded tool loop: tool calls are explicit JSON, executed by host.
    # Every loop includes only returned evidence, then asks for next call/final.
    messages = [{"role": "system", "content": P.SYSTEM},
                {"role": "user", "content": P.user_task(t, years) +
                 "\nCache endpoints: " + json.dumps(eps) +
                 "\nPlanned reads: " + json.dumps(calls) +
                 "\nReturn JSON only: {\"tool\": \"cache_get\", \"args\": [ticker, endpoint]} "
                 "OR {\"final\": drivers_object}. Read one cache item per turn. "
                 "After a tool result, choose next read; after all relevant sources "
                 "have been reviewed, return final. NEVER fabricate missing evidence."}]
    final = None
    max_steps = min(len(calls) + 3, 12)
    for _ in range(max_steps):
        raw = _chat(messages)
        try:
            ans = _parse_json(raw)
        except (ValueError, json.JSONDecodeError):
            # One schema-repair turn: don't expose chain-of-thought or raw output.
            if messages[-1]["role"] != "user" or "Perbaiki" not in messages[-1]["content"]:
                messages.append({"role": "user", "content":
                                 "Perbaiki format: balas satu JSON valid saja, tanpa <think>, "
                                 "markdown, atau teks lain. Object harus berupa {tool,args} "
                                 "atau {final: drivers_object}. Ini bukan output akhir lain."})
                continue
            return {"ok": False, "error": "respons LLM bukan JSON", "evidence": ev}
        if isinstance(ans, dict) and ("final" in ans or "drivers" in ans):
            final = ans.get("final") or ans
            break
        tool = ans.get("tool")
        args = ans.get("args") or []
        if tool not in ("cache_get", "fetch_public"):
            return {"ok": False, "error": "tool tidak diizinkan", "evidence": ev}
        try:
            result = getattr(T, tool)(*args)
        except Exception as e:  # noqa: BLE001 — failure provenance retained
            result = {"tool_error": type(e).__name__, "message": str(e)[:200]}
        item = {"tool": tool, "args": args, "result": result}
        ev.append(f"{tool}({args!r}) -> {str(result)[:300]}")
        messages.append({"role": "assistant", "content": json.dumps(ans, ensure_ascii=False)})
        messages.append({"role": "user", "content": "Tool result (JSON): " +
                         json.dumps(item, ensure_ascii=False)[:10000] +
                         "\nSekarang pilih satu tool lagi atau kembalikan {\"final\": drivers_object}."})
    if final is None:
        return {"ok": False, "error": "batas tool loop tercapai tanpa final", "evidence": ev}
    if not final:
        return {"ok": False, "error": "tanpa final JSON", "evidence": ev}
    problems = gate(final, len(years))
    if problems:
        return {"ok": False, "error": "gate menolak", "problems": problems,
                "evidence": ev}
    p = T.write_drivers(t, final)
    return {"ok": True, "path": str(p), "evidence": ev}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--years", default="2026F,2027F,2028F")
    a = ap.parse_args(argv)
    years = [y.strip() for y in a.years.split(",")]
    if a.live:
        print(json.dumps(run_live(a.ticker, years), indent=1,
                         ensure_ascii=False)[:3000])
    else:
        print(json.dumps(plan(a.ticker, years), indent=1,
                         ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()

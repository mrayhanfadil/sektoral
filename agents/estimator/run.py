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
import urllib.request

sys.path.insert(0, str(__file__.rsplit("/agents/", 1)[0]))

from agents.estimator import prompt as P
from agents.estimator import tools as T
from agents.estimator.validate import gate


def _chat(messages, max_tokens=4000):
    base = os.environ.get("SEKTORAL_LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("SEKTORAL_LLM_API_KEY", "")
    model = os.environ.get("SEKTORAL_LLM_MODEL", "")
    if not (base and key and model):
        raise RuntimeError("LLM belum dikonfigurasi "
                           "(SEKTORAL_LLM_BASE_URL/API_KEY/MODEL)")
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


def plan(ticker, years):
    """Fase 1 (tanpa LLM): inventaris bukti cache. Untuk --dry-run."""
    eps = T.cache_endpoints(ticker)
    return {"ticker": ticker.upper(), "years": years,
            "cache_endpoints": eps, "n_endpoints": len(eps),
            "tools": sorted(T.TOOLS)}


def run_live(ticker, years):
    """Fase penuh: LLM + tools (function-calling sederhana via JSON)."""
    t = ticker.upper()
    ev = [f"cache_endpoints({t}) -> {T.cache_endpoints(t)}"]
    msgs = [{"role": "system", "content": P.SYSTEM},
            {"role": "user", "content": P.user_task(t, years) + "\nBukti: " +
             ev[0] + "\nBalas JSON: {\"calls\": [{\"tool\": ..., \"args\": ...}], "
             "\"final\": {...drivers...} atau null}"}]
    raw = _chat(msgs)
    try:
        ans = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, IndexError):
        return {"ok": False, "error": "respons LLM bukan JSON", "raw": raw[:500]}
    for c in ans.get("calls") or []:
        fn = getattr(T, c.get("tool", ""), None)
        if fn is None or c.get("tool") == "write_drivers":
            continue
        try:
            res = fn(*c.get("args", []))
            ev.append(f"{c['tool']} -> {str(res)[:400]}")
        except Exception as e:  # noqa: BLE001 — bukti kegagalan dicatat
            ev.append(f"{c['tool']} GAGAL: {e}")
    final = ans.get("final")
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

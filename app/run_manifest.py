"""Immutable run manifest: compare a new PDF with an archived one.

One manifest per ticker run records code revision, as_of, latest market
close, cache snapshot IDs, official filings + publication dates, Tavily
query + retrieval status, selected news URLs, assumption-plan hash,
English source-text hash, profile, release status, and blockers. Changed
data/methods never look like a gate regression.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import house_assumptions, release_policy

ROOT = Path(__file__).resolve().parent.parent
# Rendered files of a publication bundle. Every bundle has the Indonesian
# report, its PDF and the trace view. The English edition joins the bundle
# when its files exist at finalize time (ADR 0015); a manifest without it, as
# every manifest before #34, verifies exactly as before.
REQUIRED_ARTIFACTS = {"html": "{ticker}.html", "pdf": "{ticker}.pdf",
                      "trace_html": "{ticker}-trace.html"}
OPTIONAL_ARTIFACTS = {"html_en": "{ticker}.en.html", "pdf_en": "{ticker}.en.pdf"}
ARTIFACT_FILES = {**REQUIRED_ARTIFACTS, **OPTIONAL_ARTIFACTS}


def bundle_kinds(manifest) -> tuple[str, ...]:
    """Artifact kinds a manifest's bundle holds: the required ones, plus each
    optional kind it lists."""
    listed = manifest.get("artifacts") if isinstance(manifest, dict) else None
    listed = listed if isinstance(listed, dict) else {}
    return (*REQUIRED_ARTIFACTS, *(kind for kind in OPTIONAL_ARTIFACTS if kind in listed))


def git_revision():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT), stderr=subprocess.DEVNULL,
            timeout=5).decode().strip()
    except Exception:
        return "unknown"


def assumption_plan_hash(plan):
    try:
        blob = json.dumps(plan or {}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]
    except Exception:
        return "unhashable"


def content_hash(value):
    """Full SHA-256 of a JSON-compatible evidence or market-input object."""
    try:
        blob = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                          separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()
    except Exception:
        return "unhashable"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_hash(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def file_sha256(path) -> str | None:
    """SHA-256 of one file's bytes, or None when it cannot be read."""
    return _file_hash(Path(path))


def working_tree_identity():
    """Identify uncommitted tracked and untracked source that built a run."""
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all", "-z"],
            cwd=str(ROOT), stderr=subprocess.DEVNULL, timeout=10)
        paths = subprocess.check_output(
            ["git", "ls-files", "--modified", "--deleted", "--others",
             "--exclude-standard", "-z"],
            cwd=str(ROOT), stderr=subprocess.DEVNULL, timeout=10)
        files = []
        for raw_path in paths.split(b"\0"):
            if not raw_path:
                continue
            relative = raw_path.decode("utf-8", errors="replace")
            path = (ROOT / relative).resolve()
            try:
                path.relative_to(ROOT.resolve())
            except ValueError:
                files.append({"path": relative, "sha256": None, "state": "outside_root"})
                continue
            digest = _file_hash(path) if path.is_file() else None
            files.append({"path": relative, "sha256": digest,
                          "state": "present" if digest else "deleted_or_unreadable"})
        state = {"status": status.decode("utf-8", errors="replace"),
                 "files": sorted(files, key=lambda row: row["path"])}
        return {"dirty": bool(status), "sha256": _sha256_bytes(json.dumps(
            state, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()),
            "changed_files": state["files"]}
    except Exception as error:
        return {"dirty": None, "sha256": None,
                "error": f"working tree identity unavailable: {error}"}


def issuer_source_hashes(ticker):
    """Content identity of curated per-issuer inputs and shared rate policy."""
    symbol = str(ticker or "").upper()
    names = ("issuer_evidence", "market_quotes", "peer_groups", "analyst_scenarios",
             "drivers", "bank_drivers", "operating_drivers", "market_history", "idx_history",
             "rating_history", "method_overrides")
    paths = [ROOT / "data" / group / f"{symbol}.json" for group in names]
    paths.append(ROOT / "data" / "rate_benchmarks.json")
    return {path.relative_to(ROOT).as_posix(): digest
            for path in paths if (digest := _file_hash(path)) is not None}


def source_tree_hash():
    """Stable identity for engine, agent, report-policy, and rendering source."""
    roots = (ROOT / "app", ROOT / "agents", ROOT / "spec", ROOT / "docs" / "adr",
             ROOT / "web" / "src")
    files = [path for root in roots if root.exists() for path in root.rglob("*")
             if path.is_file() and not any(part in {"__pycache__", "node_modules", ".git"}
                                           for part in path.parts)]
    files.extend(path for path in (ROOT / "Dockerfile", ROOT / "requirements.txt",
                                   ROOT / "requirements-dev.txt", ROOT / "web" / "package.json",
                                   ROOT / "web" / "package-lock.json") if path.is_file())
    entries = []
    for path in sorted(set(files)):
        relative = path.relative_to(ROOT).as_posix()
        entries.append({"path": relative, "sha256": _file_hash(path)})
    for name in ("CONTEXT.md", "PRODUCT.md"):
        path = ROOT / name
        if path.is_file():
            entries.append({"path": name, "sha256": _file_hash(path)})
    entries.sort(key=lambda row: row["path"])
    return _sha256_bytes(json.dumps(entries, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode())


def source_text_en_hash():
    """Identity of the English source-text translations the build quotes."""
    try:
        from . import prose_lang  # lazy: keeps this module free of report imports
        return prose_lang.source_text_sha256()
    except Exception:
        return None


def cache_snapshot_ids(ticker):
    """Cache identity for one ticker: newest cache_key per endpoint naming it.

    Scoped to the ticker so refreshing another issuer does not change this
    run's snapshot, and reads only keys (no payload JSON).
    """
    try:
        from . import cache as cache_mod
        con = cache_mod.connect()
        try:
            rows = con.execute(
                "SELECT endpoint, cache_key FROM sectors_cache"
                " WHERE endpoint LIKE ? ORDER BY fetched_at",
                (f"%/{str(ticker).upper()}/%",)).fetchall()
        finally:
            con.close()
        return {endpoint: key for endpoint, key in rows}
    except Exception:
        return {}


def cache_snapshot_hashes(ticker):
    """SHA-256 of each latest ticker-scoped cached endpoint payload."""
    try:
        from . import cache as cache_mod
        con = cache_mod.connect()
        try:
            rows = con.execute(
                "SELECT endpoint, cache_key, payload_json FROM sectors_cache"
                " WHERE endpoint LIKE ? ORDER BY fetched_at",
                (f"%/{str(ticker).upper()}/%",)).fetchall()
        finally:
            con.close()
        latest = {}
        for endpoint, cache_key, payload_json in rows:
            latest[endpoint] = {"cache_key": cache_key,
                                "content_sha256": _sha256_bytes(str(payload_json).encode())}
        return latest
    except Exception:
        return {}


def finalize_manifest(manifest, folder, ticker):
    """Return a detached publication manifest after the artifacts are rendered.

    This sidecar hashes the final bytes without creating a hash cycle inside
    the HTML/PDF that embeds the source manifest.
    """
    result = dict(manifest or {})
    # All current report builders supply this before rendering. The fallback
    # keeps offline test/rebuild callers on the same recorded policy version.
    if not isinstance(result.get("release_policy"), dict):
        result["release_policy"] = release_policy.versioned_snapshot()
    if not isinstance(result.get("house_assumptions"), dict):
        result["house_assumptions"] = house_assumptions.versioned_snapshot()
    symbol = str(ticker or "").upper()
    root = Path(folder)
    patterns = {kind: name.format(ticker=symbol) for kind, name in ARTIFACT_FILES.items()}
    hashes = {kind: _file_hash(root / name) for kind, name in patterns.items()}
    result["artifacts"] = {kind: {"file": patterns[kind], "sha256": digest}
                           for kind, digest in hashes.items() if digest is not None}
    # An absent English edition is not missing: that bundle is Indonesian only.
    result["missing_artifacts"] = [kind for kind in REQUIRED_ARTIFACTS if hashes[kind] is None]
    if result.get("market_inputs") is not None:
        result["market_inputs_sha256"] = content_hash(result["market_inputs"])
    identity = {key: value for key, value in result.items()
                if key not in {"publication_id", "artifacts", "missing_artifacts"}}
    identity["artifacts"] = result["artifacts"]
    result["publication_id"] = _sha256_bytes(json.dumps(
        identity, sort_keys=True, ensure_ascii=False, default=str,
        separators=(",", ":")).encode())
    return result


def re_full_sha(value):
    return (isinstance(value, str) and len(value) == 64 and
            all(ch in "0123456789abcdef" for ch in value.lower()))


def publication_manifest_errors(manifest, ticker, as_of, artifact_hashes):
    """Validate a stored source manifest against the final artifact bytes."""
    if not isinstance(manifest, dict):
        return ["publication manifest is missing or invalid"]
    errors = []
    if str(manifest.get("ticker") or "").upper() != str(ticker or "").upper():
        errors.append("publication manifest ticker does not match report")
    if str(manifest.get("as_of") or "")[:10] != str(as_of or "")[:10]:
        errors.append("publication manifest Report Date does not match report")
    if not re_full_sha(manifest.get("source_tree_sha256")):
        errors.append("publication manifest source tree hash is missing or invalid")
    if not re_full_sha(manifest.get("spec_sha256")):
        errors.append("publication manifest report spec hash is missing or invalid")
    if not re_full_sha(manifest.get("evidence_register_sha256")):
        errors.append("publication manifest Evidence Register hash is missing or invalid")
    policy_snapshot = manifest.get("release_policy")
    if not isinstance(policy_snapshot, dict):
        errors.append("publication manifest release policy is missing or invalid")
    else:
        policy_body = policy_snapshot.get("policy")
        policy_hash = policy_snapshot.get("sha256")
        current_policy = release_policy.versioned_snapshot()
        try:
            recorded_hash = release_policy.policy_sha256(policy_body) if isinstance(policy_body, dict) else None
        except (TypeError, ValueError):
            recorded_hash = None
        if not isinstance(policy_hash, str) or policy_hash != recorded_hash:
            errors.append("publication manifest release policy hash does not match its contents")
        elif policy_snapshot != current_policy:
            errors.append("publication manifest release policy is stale")
    house_snapshot = manifest.get("house_assumptions")
    if not isinstance(house_snapshot, dict):
        errors.append("publication manifest house assumptions are missing or invalid")
    else:
        house_body = house_snapshot.get("policy")
        house_hash = house_snapshot.get("sha256")
        current_house = house_assumptions.versioned_snapshot()
        try:
            recorded_house_hash = (house_assumptions.policy_sha256(house_body)
                                   if isinstance(house_body, dict) else None)
        except (TypeError, ValueError):
            recorded_house_hash = None
        if not isinstance(house_hash, str) or house_hash != recorded_house_hash:
            errors.append("publication manifest house-assumption hash does not match its contents")
        elif house_snapshot != current_house:
            errors.append("publication manifest house assumptions are stale")
    if manifest.get("missing_artifacts"):
        errors.append("publication manifest records missing artifacts")
    expected_artifacts = manifest.get("artifacts")
    if not isinstance(expected_artifacts, dict):
        errors.append("publication manifest artifact hashes are missing")
        expected_artifacts = {}
    # English kinds are checked only where the manifest lists them.
    for kind in bundle_kinds(manifest):
        entry = expected_artifacts.get(kind)
        current = (artifact_hashes or {}).get(kind)
        if not isinstance(entry, dict) or not re_full_sha(entry.get("sha256")):
            errors.append(f"publication manifest {kind} hash is missing or invalid")
        elif current != entry["sha256"]:
            errors.append(f"publication manifest {kind} hash does not match current artifact")
    publication_id = manifest.get("publication_id")
    if not re_full_sha(publication_id):
        errors.append("publication manifest ID is missing or invalid")
    else:
        identity = {key: value for key, value in manifest.items()
                    if key not in {"publication_id", "artifacts", "missing_artifacts", "review"}}
        identity["artifacts"] = expected_artifacts
        expected_id = _sha256_bytes(json.dumps(
            identity, sort_keys=True, ensure_ascii=False, default=str,
            separators=(",", ":")).encode())
        if publication_id != expected_id:
            errors.append("publication manifest ID does not match its contents")
    return list(dict.fromkeys(errors))


def build_manifest(*, ticker, as_of, intake=None, forecast=None,
                   valuation=None, news_evidence=None, assumption_plan=None,
                   release=None, spec_sha=None, evidence_register=None):
    intake = intake or {}
    forecast = forecast or {}
    valuation = valuation or {}
    news_evidence = news_evidence or {}
    search = news_evidence.get("search") or {}
    rows = news_evidence.get("rows") or []
    official = (intake.get("official_evidence") or {}).get("latest_actual") or {}
    market_quote = intake.get("market_quote") or {}
    release = release or (valuation.get("release") or {})

    queries = search.get("queries")
    if not queries and search.get("query"):
        queries = [{"query": search.get("query")}]
    if not spec_sha:
        spec_sha = _file_hash(ROOT / "spec" / "Instruksi-Report-v3.md")
    return {
        "ticker": str(ticker or "").upper(),
        "code_revision": git_revision(),
        "source_tree_sha256": source_tree_hash(),
        "working_tree": working_tree_identity(),
        "as_of": str(as_of or intake.get("as_of") or "")[:10],
        # When the document was built; the report says so when it differs
        # from the Report Date (app.render.build_note).
        "built_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "profile": intake.get("model_profile"),
        "model": {"forecast_agent": os.getenv("SEKTORAL_LLM_MODEL", "MiniMax-M3"),
                  "agent_effort": "high", "schema_version": 1},
        "source_pack_sha256": issuer_source_hashes(ticker),
        "source_text_en_sha256": source_text_en_hash(),
        "market_close": {
            "price": intake.get("price"),
            "price_date": intake.get("price_date"),
            "source_title": market_quote.get("source_title"),
            "source_url": market_quote.get("source_url"),
        },
        "official_filing": {
            "period": official.get("period"),
            "period_end": official.get("period_end"),
            "published_at": official.get("published_at"),
            "source_title": official.get("source_title"),
            "source_url": official.get("source_url"),
        },
        "tavily": {
            "status": search.get("status"),
            "queries": queries or [],
            "window": search.get("window"),
            "fetched_at": search.get("fetched_at"),
            "error": search.get("error"),
            "partial_failures": list(search.get("partial_failures") or []),
        },
        "selected_news_urls": [str(r.get("source") or "") for r in rows
                               if isinstance(r, dict) and r.get("source")],
        "assumption_plan_hash": assumption_plan_hash(assumption_plan),
        "evidence_register_sha256": content_hash(evidence_register),
        "forecast_basis": forecast.get("forecast_basis"),
        "production_ready": forecast.get("production_ready"),
        "target_method": valuation.get("method"),
        "target_price": valuation.get("tp"),
        "release_status": release.get("status"),
        "engine_release_status": release.get("engine_status"),
        "blockers": list(release.get("blockers") or []),
        "spec_sha256": spec_sha,
        "release_policy": release_policy.versioned_snapshot(),
        "house_assumptions": house_assumptions.versioned_snapshot(),
        "cache_snapshot": cache_snapshot_ids(ticker),
        "cache_snapshot_sha256": cache_snapshot_hashes(ticker),
    }

"""Immutable snapshots of analyst-approved Company Update bundles.

An archive is stored below ``<run folder>/archives/<TICKER>/<publication_id>``.
Rendered files are copied byte-for-byte. Structured documents are serialized
as stable JSON snapshots from ``app.outputs`` (and its selected database).
Every copied file is hashed in ``archive.json``; readers verify confinement
and the recorded content hash before returning an artifact path.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from . import assumption_review, outputs, reviewer_auth, store

_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,19}$")
_PUBLICATION_ID = re.compile(r"^[a-f0-9]{64}$")
_FINAL_KINDS = ("html", "pdf", "trace_html")
_FILE_NAMES = {
    "html": "{ticker}.html",
    "pdf": "{ticker}.pdf",
    "trace_html": "{ticker}-trace.html",
    "report": "{ticker}-report.json",
    "trace": "{ticker}-trace.json",
    "manifest": "{ticker}-manifest.json",
    "events": "{ticker}-events.json",
}
_OUTPUT_COLLECTIONS = {
    "report": outputs.REPORT,
    "trace": outputs.TRACE,
    "manifest": outputs.MANIFEST,
    "events": outputs.EVENTS,
}
_ARCHIVE_MANIFEST = "archive.json"
EVENT_COLLECTION = "publication_lineage_events"
_EVENT_KINDS = {"published", "superseded", "withdrawn"}


class PublicationHistoryError(RuntimeError):
    """Publication history is inconsistent or has been modified."""


class PublicationMutationDenied(PermissionError):
    """Only a configured reviewer or compliance identity may mutate history."""


class UnknownPublicationError(LookupError):
    """No verified publication with this ID exists for the requested ticker."""


class SupersessionReasonRequired(ValueError):
    """A successor needs an explicit reason when a prior publication exists."""


def _symbol(ticker) -> str | None:
    value = str(ticker or "").upper()
    return value if _TICKER.fullmatch(value) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _json_bytes(document) -> bytes:
    return (json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2,
                        separators=(",", ": ")) + "\n").encode("utf-8")


def _archive_dir(root: Path, ticker: str, publication_id: str) -> Path:
    return root / "archives" / ticker / publication_id


def _archive_result(manifest: dict, folder: Path, ticker: str) -> dict:
    result = dict(manifest)
    result["archive_dir"] = str(_archive_dir(folder, ticker, manifest["publication_id"]))
    return result


def _load_archive(directory: Path, root: Path, ticker: str,
                  publication_id: str) -> dict | None:
    """Read and verify a complete archive; malformed or modified bundles fail closed."""
    if directory.is_symlink() or not _inside(directory, root) or not directory.is_dir():
        return None
    manifest_path = directory / _ARCHIVE_MANIFEST
    if not _inside(manifest_path, directory):
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (not isinstance(manifest, dict)
            or manifest.get("ticker") != ticker
            or manifest.get("publication_id") != publication_id
            or not isinstance(manifest.get("review_sha"), str)
            or not isinstance(manifest.get("archived_at"), str)):
        return None
    files = manifest.get("files")
    hashes = manifest.get("artifact_hashes")
    if not isinstance(files, dict) or not isinstance(hashes, dict) or set(files) != set(hashes):
        return None
    if not set(_FINAL_KINDS).issubset(files):
        return None
    for kind, name in files.items():
        if kind not in _FILE_NAMES or name != _FILE_NAMES[kind].format(ticker=ticker):
            return None
        path = directory / name
        if not _inside(path, directory) or not path.is_file():
            return None
        try:
            if _sha256(path) != hashes.get(kind):
                return None
        except OSError:
            return None
    return manifest


def archive_approved_bundle(folder, ticker, db=None) -> dict | None:
    """Archive a currently approved report bundle once, without replacing it.

    The three rendered-file hashes must agree across the live files, the
    approved review record, and the run manifest. Report, trace and manifest
    database documents are required. Recorded events are included when they
    exist; older runs without recorded events remain archivable.

    Returns the archive manifest plus its local ``archive_dir``, or ``None``
    when the bundle is not approved, incomplete, unsafe, or conflicts with an
    existing archive at the same publication ID.
    """
    symbol = _symbol(ticker)
    root = Path(folder).resolve()
    if symbol is None or not root.is_dir():
        return None

    # Evaluate review against the same database used for the documents below.
    state = assumption_review.status(root, symbol, db)
    if state.get("state") != "approved":
        return None
    review = state.get("record")
    if not isinstance(review, dict) or not isinstance(review.get("review_sha"), str):
        return None

    manifest = outputs.load(outputs.MANIFEST, root, symbol, db)
    if not isinstance(manifest, dict):
        return None
    publication_id = manifest.get("publication_id")
    if not isinstance(publication_id, str) or not _PUBLICATION_ID.fullmatch(publication_id):
        return None
    review_hashes = review.get("artifact_hashes")
    current_hashes = state.get("artifact_hashes")
    manifest_artifacts = manifest.get("artifacts")
    if not all(isinstance(value, dict) for value in
               (review_hashes, current_hashes, manifest_artifacts)):
        return None

    rendered_sources: dict[str, Path] = {}
    expected_hashes: dict[str, str] = {}
    for kind in _FINAL_KINDS:
        expected = review_hashes.get(kind)
        current = current_hashes.get(kind)
        manifest_item = manifest_artifacts.get(kind)
        if (not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)
                or current != expected or not isinstance(manifest_item, dict)
                or manifest_item.get("sha256") != expected
                or manifest_item.get("file") != _FILE_NAMES[kind].format(ticker=symbol)):
            return None
        source = root / _FILE_NAMES[kind].format(ticker=symbol)
        if not _inside(source, root) or not source.is_file():
            return None
        try:
            if _sha256(source) != expected:
                return None
        except OSError:
            return None
        rendered_sources[kind] = source
        expected_hashes[kind] = expected

    documents = {
        kind: outputs.load(collection, root, symbol, db)
        for kind, collection in _OUTPUT_COLLECTIONS.items()
    }
    if any(documents[kind] is None for kind in ("report", "trace", "manifest")):
        return None
    trace_review = (documents["trace"].get("assumption_review")
                    if isinstance(documents["trace"], dict) else None)
    if (not isinstance(trace_review, dict)
            or trace_review.get("review_sha") != review.get("review_sha")):
        return None

    # The output manifest must be the same publication identity that names it.
    if documents["manifest"].get("publication_id") != publication_id:
        return None

    files = {kind: _FILE_NAMES[kind].format(ticker=symbol) for kind in _FINAL_KINDS}
    for kind in _OUTPUT_COLLECTIONS:
        if documents[kind] is not None:
            files[kind] = _FILE_NAMES[kind].format(ticker=symbol)

    archive_parent = root / "archives" / symbol
    if not _inside(archive_parent, root):
        return None
    try:
        archive_parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    if not _inside(archive_parent, root):
        return None
    destination = archive_parent / publication_id
    candidate_hashes = _archive_hashes_for_existing_inputs(
        rendered_sources, documents, files, expected_hashes)
    if not candidate_hashes:
        return None
    if destination.exists() or destination.is_symlink():
        prior = _load_archive(destination, root, symbol, publication_id)
        if (prior is not None and prior.get("review_sha") == review["review_sha"]
                and prior.get("artifact_hashes") == candidate_hashes):
            return _archive_result(prior, root, symbol)
        return None

    try:
        staging = Path(tempfile.mkdtemp(prefix=f".{publication_id}.", dir=archive_parent))
    except OSError:
        return None
    try:
        archive_hashes: dict[str, str] = {}
        for kind, name in files.items():
            target = staging / name
            if kind in rendered_sources:
                shutil.copyfile(rendered_sources[kind], target)
            else:
                target.write_bytes(_json_bytes(documents[kind]))
            archive_hashes[kind] = _sha256(target)

        archive_manifest = {
            "schema_version": 1,
            "ticker": symbol,
            "publication_id": publication_id,
            "review_sha": review["review_sha"],
            "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": files,
            "artifact_hashes": archive_hashes,
        }
        (staging / _ARCHIVE_MANIFEST).write_bytes(_json_bytes(archive_manifest))
        # The staging directory is a sibling of the destination, so rename is
        # atomic on the same filesystem and readers never see a partial bundle.
        staging.rename(destination)
        return _archive_result(archive_manifest, root, symbol)
    except OSError:
        prior = _load_archive(destination, root, symbol, publication_id)
        if (prior is not None and prior.get("review_sha") == review["review_sha"]
                and prior.get("artifact_hashes") == candidate_hashes):
            return _archive_result(prior, root, symbol)
        return None
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _archive_hashes_for_existing_inputs(rendered_sources, documents, files,
                                        final_hashes) -> dict[str, str]:
    """Compute the candidate snapshot hashes for idempotent archive calls."""
    hashes = dict(final_hashes)
    for kind in files:
        if kind in rendered_sources:
            continue
        try:
            hashes[kind] = hashlib.sha256(_json_bytes(documents[kind])).hexdigest()
        except (TypeError, ValueError):
            return {}
    return hashes


def list_archives(folder, ticker) -> list[dict]:
    """Return verified archive manifests for a ticker, newest first."""
    symbol = _symbol(ticker)
    root = Path(folder).resolve()
    if symbol is None or not root.is_dir():
        return []
    archive_root = root / "archives" / symbol
    if not _inside(archive_root, root) or not archive_root.is_dir():
        return []
    found = []
    try:
        children = list(archive_root.iterdir())
    except OSError:
        return []
    for child in children:
        publication_id = child.name
        if not _PUBLICATION_ID.fullmatch(publication_id):
            continue
        manifest = _load_archive(child, root, symbol, publication_id)
        if manifest is not None:
            found.append(manifest)
    return sorted(found, key=lambda row: (row.get("archived_at", ""),
                                          row.get("publication_id", "")), reverse=True)


def artifact(folder, ticker, publication_id, kind) -> Path | None:
    """Return a verified archived file path for a known bundle kind, else None.

    Supported kinds are ``html``, ``pdf``, ``trace_html``, ``report``,
    ``trace``, ``manifest``, and ``events``. The returned path is inside the
    archive and its bytes match the archive manifest's SHA-256 digest.
    """
    symbol = _symbol(ticker)
    if (symbol is None or not isinstance(publication_id, str)
            or not _PUBLICATION_ID.fullmatch(publication_id)
            or not isinstance(kind, str) or kind not in _FILE_NAMES):
        return None
    root = Path(folder).resolve()
    if not root.is_dir():
        return None
    directory = _archive_dir(root, symbol, publication_id)
    manifest = _load_archive(directory, root, symbol, publication_id)
    if manifest is None:
        return None
    history = publication_history(root, symbol, publication_id)
    if history["state"] in {"withdrawn", "history_invalid"}:
        return None
    name = manifest["files"].get(kind)
    if name != _FILE_NAMES[kind].format(ticker=symbol):
        return None
    path = directory / name
    return path if _inside(path, directory) and path.is_file() else None


def _event_prefix(folder, ticker: str, publication_id: str) -> str:
    return f"{outputs.key(folder, ticker)}::{publication_id}::"


def _event_digest(event: dict) -> str:
    body = {key: value for key, value in event.items() if key != "event_sha256"}
    return hashlib.sha256(_json_bytes(body)).hexdigest()


def _read_events(folder, ticker: str, publication_id: str, db=None) -> list[dict] | None:
    """Read one append-only event stream, rejecting gaps or altered records."""
    prefix = _event_prefix(folder, ticker, publication_id)
    try:
        keys = store.keys(EVENT_COLLECTION, prefix, db)
        events = []
        previous_hash = None
        for sequence, key in enumerate(keys, 1):
            if key != f"{prefix}{sequence:08d}":
                return None
            event = store.get(EVENT_COLLECTION, key, db)
            if not isinstance(event, dict):
                return None
            if (event.get("schema_version") != 1 or event.get("ticker") != ticker
                    or event.get("publication_id") != publication_id
                    or event.get("sequence") != sequence
                    or event.get("event_type") not in _EVENT_KINDS
                    or event.get("previous_event_sha256") != previous_hash
                    or event.get("event_sha256") != _event_digest(event)):
                return None
            if not isinstance(event.get("recorded_at"), str) or not isinstance(event.get("actor"), dict):
                return None
            for link in ("predecessor_publication_id", "successor_publication_id"):
                value = event.get(link)
                if value is not None and (not isinstance(value, str)
                                          or not _PUBLICATION_ID.fullmatch(value)):
                    return None
            if event.get("event_type") in {"superseded", "withdrawn"} and len(
                    str(event.get("reason") or "").strip()) < 12:
                return None
            previous_hash = event["event_sha256"]
            events.append(event)
        return events
    except (OSError, ValueError, TypeError):
        return None


def _verified_actor(token: str | None) -> dict:
    identity = reviewer_auth.authenticate(token)
    if identity is None or identity.get("role") not in {"reviewer", "compliance"}:
        raise PublicationMutationDenied(
            "publication history requires an authenticated reviewer or compliance identity")
    return {"id": identity["id"], "name": identity["name"],
            "role": identity["role"], "source": "authenticated_registry"}


def _append_event(folder, ticker: str, publication_id: str, event_type: str, *,
                  actor: dict, reason: str = "", predecessor_publication_id=None,
                  successor_publication_id=None, db=None) -> dict:
    """Append an immutable, hash-chained event. Existing events are never rewritten."""
    existing = _read_events(folder, ticker, publication_id, db)
    if existing is None:
        raise PublicationHistoryError("publication event history is missing or tampered")
    for event in existing:
        if (event.get("event_type") == event_type
                and event.get("predecessor_publication_id") == predecessor_publication_id
                and event.get("successor_publication_id") == successor_publication_id):
            if (event.get("reason") != reason or event.get("actor") != actor):
                raise PublicationHistoryError("an existing publication event conflicts with this action")
            return event
    if event_type in {"superseded", "withdrawn"} and len(reason.strip()) < 12:
        raise ValueError("an explicit reason of at least 12 characters is required")
    sequence = len(existing) + 1
    event = {
        "schema_version": 1, "ticker": ticker, "publication_id": publication_id,
        "sequence": sequence, "event_type": event_type,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actor": dict(actor), "reason": reason.strip(),
        "predecessor_publication_id": predecessor_publication_id,
        "successor_publication_id": successor_publication_id,
        "previous_event_sha256": existing[-1]["event_sha256"] if existing else None,
    }
    event["event_sha256"] = _event_digest(event)
    key = f"{_event_prefix(folder, ticker, publication_id)}{sequence:08d}"
    if not store.insert_if_absent(EVENT_COLLECTION, key, event, db):
        raise PublicationHistoryError("concurrent publication event changed the event sequence")
    return event


def _has_archive(folder, ticker: str, publication_id: str) -> bool:
    root = Path(folder).resolve()
    return _load_archive(_archive_dir(root, ticker, publication_id), root,
                         ticker, publication_id) is not None


def _current_publication(folder, ticker: str, publication_id: str, db=None) -> bool:
    manifest = outputs.load(outputs.MANIFEST, folder, ticker, db)
    report = outputs.load(outputs.REPORT, folder, ticker, db)
    return (isinstance(manifest, dict) and manifest.get("publication_id") == publication_id
            and isinstance(report, dict)
            and str((report.get("meta") or {}).get("ticker") or "").upper() == ticker)


def publication_history(folder, ticker, publication_id, db=None) -> dict:
    """Verified state and lineage links for one known current or archived publication."""
    symbol = _symbol(ticker)
    if (symbol is None or not isinstance(publication_id, str)
            or not _PUBLICATION_ID.fullmatch(publication_id)):
        return {"state": "unknown", "events": []}
    known = _has_archive(folder, symbol, publication_id) or _current_publication(
        folder, symbol, publication_id, db)
    if not known:
        return {"state": "unknown", "events": []}
    events = _read_events(folder, symbol, publication_id, db)
    if events is None:
        return {"state": "history_invalid", "events": []}

    published = next((event for event in events if event["event_type"] == "published"), None)
    superseded = next((event for event in events if event["event_type"] == "superseded"), None)
    withdrawn = next((event for event in events if event["event_type"] == "withdrawn"), None)

    # Verify both sides of every link. A valid local hash chain cannot silently
    # point at a made-up predecessor or successor.
    if published and published.get("predecessor_publication_id"):
        predecessor_id = published["predecessor_publication_id"]
        parent_events = _read_events(folder, symbol, predecessor_id, db)
        if (not (_has_archive(folder, symbol, predecessor_id)
                 or _current_publication(folder, symbol, predecessor_id, db))
                or parent_events is None or not any(
                    e.get("event_type") == "superseded"
                    and e.get("successor_publication_id") == publication_id
                    and e.get("reason") == published.get("reason") for e in parent_events)):
            return {"state": "history_invalid", "events": events}
    if superseded and superseded.get("successor_publication_id"):
        successor_id = superseded["successor_publication_id"]
        child_events = _read_events(folder, symbol, successor_id, db)
        if (not (_has_archive(folder, symbol, successor_id)
                 or _current_publication(folder, symbol, successor_id, db))
                or child_events is None or not any(
                    e.get("event_type") == "published"
                    and e.get("predecessor_publication_id") == publication_id
                    and e.get("reason") == superseded.get("reason") for e in child_events)):
            return {"state": "history_invalid", "events": events}

    state = ("withdrawn" if withdrawn else "superseded" if superseded else
             "published" if published else "archived" if _has_archive(
                 folder, symbol, publication_id) else "unrecorded")
    return {
        "state": state,
        "predecessor_publication_id": published.get("predecessor_publication_id") if published else None,
        "successor_publication_id": superseded.get("successor_publication_id") if superseded else None,
        "supersession_reason": superseded.get("reason") if superseded else None,
        "withdrawal_reason": withdrawn.get("reason") if withdrawn else None,
        "withdrawn_at": withdrawn.get("recorded_at") if withdrawn else None,
        "events": events,
    }


def publication_state(folder, ticker, publication_id, db=None) -> str:
    return publication_history(folder, ticker, publication_id, db).get("state", "unknown")


def predecessor_candidate(folder, ticker, publication_id, db=None) -> str | None:
    """Newest verified prior archive, if a new approved bundle would supersede one."""
    symbol = _symbol(ticker)
    if symbol is None or not isinstance(publication_id, str):
        return None
    for manifest in list_archives(folder, symbol):
        predecessor_id = manifest.get("publication_id")
        if predecessor_id == publication_id:
            continue
        history = publication_history(folder, symbol, predecessor_id, db)
        if history["state"] == "history_invalid":
            raise PublicationHistoryError("prior publication history is missing or tampered")
        if history["state"] != "superseded":
            return predecessor_id
    return None


def record_approved_publication(folder, ticker, *, reviewer_token: str | None,
                                supersession_reason: str = "", db=None) -> dict:
    """Record an authenticated approval and, when applicable, link its predecessor."""
    symbol = _symbol(ticker)
    actor = _verified_actor(reviewer_token)
    if symbol is None:
        raise UnknownPublicationError("invalid ticker")
    status = assumption_review.status(folder, symbol, db)
    record = status.get("record")
    manifest = outputs.load(outputs.MANIFEST, folder, symbol, db)
    publication_id = manifest.get("publication_id") if isinstance(manifest, dict) else None
    if (status.get("state") != "approved" or not isinstance(record, dict)
            or record.get("identity_source") != "authenticated_registry"
            or record.get("reviewer_id") != actor["id"]
            or not isinstance(publication_id, str)
            or not _PUBLICATION_ID.fullmatch(publication_id)):
        raise PublicationMutationDenied("the authenticated reviewer must approve this frozen bundle")
    predecessor_id = predecessor_candidate(folder, symbol, publication_id, db)
    reason = str(supersession_reason or "").strip()
    if predecessor_id and len(reason) < 12:
        raise SupersessionReasonRequired(
            "a supersession reason of at least 12 characters is required")
    if predecessor_id and not _has_archive(folder, symbol, predecessor_id):
        raise UnknownPublicationError("predecessor archive is not verified")
    published_event = _append_event(
        folder, symbol, publication_id, "published", actor=actor, reason=reason,
        predecessor_publication_id=predecessor_id, db=db)
    if predecessor_id:
        _append_event(folder, symbol, predecessor_id, "superseded", actor=actor,
                      reason=reason, successor_publication_id=publication_id, db=db)
    history = publication_history(folder, symbol, publication_id, db)
    if history["state"] == "history_invalid":
        raise PublicationHistoryError("publication links did not verify after append")
    return {"event": published_event, **history}


def withdraw_publication(folder, ticker, publication_id, *, reason: str,
                         reviewer_token: str | None, db=None) -> dict:
    """Withdraw a verified current or archived publication without deleting it."""
    symbol = _symbol(ticker)
    actor = _verified_actor(reviewer_token)
    if (symbol is None or not isinstance(publication_id, str)
            or not _PUBLICATION_ID.fullmatch(publication_id)):
        raise UnknownPublicationError("invalid publication ID")
    why = str(reason or "").strip()
    if len(why) < 12:
        raise ValueError("a withdrawal reason of at least 12 characters is required")
    if not _has_archive(folder, symbol, publication_id):
        if not _current_publication(folder, symbol, publication_id, db):
            raise UnknownPublicationError("publication ID is not verified for this ticker")
        review = assumption_review.status(folder, symbol, db)
        if review.get("state") != "approved":
            raise UnknownPublicationError("only an approved publication can be withdrawn")
        archived = archive_approved_bundle(folder, symbol, db=db)
        if not isinstance(archived, dict) or archived.get("publication_id") != publication_id:
            raise PublicationHistoryError("approved publication could not be preserved before withdrawal")
    current = publication_history(folder, symbol, publication_id, db)
    if current["state"] == "history_invalid":
        raise PublicationHistoryError("publication history is missing or tampered")
    if current["state"] == "unknown":
        raise UnknownPublicationError("publication ID is unknown")
    if current["state"] == "withdrawn":
        return current
    event = _append_event(
        folder, symbol, publication_id, "withdrawn", actor=actor, reason=why,
        predecessor_publication_id=current.get("predecessor_publication_id"),
        successor_publication_id=current.get("successor_publication_id"), db=db)
    result = publication_history(folder, symbol, publication_id, db)
    if result["state"] != "withdrawn":
        raise PublicationHistoryError("withdrawal event did not verify after append")
    return {"event": event, **result}

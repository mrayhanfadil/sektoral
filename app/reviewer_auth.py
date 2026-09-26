"""Authenticated reviewer identities for local and hosted review workflows.

The server stores only reviewer identity metadata. Each configured credential
is represented by a SHA-256 token digest in ``SECTORAL_REVIEWERS``; raw review
tokens are supplied by the reviewer and are never written to report records.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re

from .release_policy import ROLE_PERMISSIONS, role_may

_TOKEN_SHA = re.compile(r"^[0-9a-f]{64}$")
_ROLES = set(ROLE_PERMISSIONS)
_MIN_TOKEN_LENGTH = 32


def registry() -> list[dict]:
    """Parse the reviewer registry, returning an empty list on any bad config."""
    raw = os.environ.get("SECTORAL_REVIEWERS") or ""
    try:
        entries = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(entries, list) or not entries:
        return []
    parsed = []
    seen_ids, seen_tokens = set(), set()
    for entry in entries:
        if not isinstance(entry, dict):
            return []
        reviewer_id = entry.get("id")
        name = entry.get("name")
        role = entry.get("role")
        digest = entry.get("token_sha256")
        if (not isinstance(reviewer_id, str) or not reviewer_id.strip() or len(reviewer_id) > 120
                or not isinstance(name, str) or len(name.strip()) < 2 or len(name) > 120
                or role not in _ROLES or not isinstance(digest, str)
                or not _TOKEN_SHA.fullmatch(digest)):
            return []
        reviewer_id = reviewer_id.strip()
        digest = digest.lower()
        if reviewer_id in seen_ids or digest in seen_tokens:
            return []
        seen_ids.add(reviewer_id)
        seen_tokens.add(digest)
        parsed.append({"id": reviewer_id, "name": name.strip(), "role": role,
                       "token_sha256": digest})
    return parsed


def configured() -> bool:
    """True only when the full reviewer registry parses successfully."""
    return bool(registry())


def approvals_enabled() -> bool:
    """Whether at least one configured identity may approve a publication."""
    return any(role_may(entry["role"], "approve") for entry in registry())


def authenticate(given: str | None) -> dict | None:
    """Resolve a supplied token to configured identity; never accept a name."""
    if not isinstance(given, str) or len(given) < _MIN_TOKEN_LENGTH:
        return None
    candidate = hashlib.sha256(given.encode("utf-8")).hexdigest()
    match = next((entry for entry in registry()
                 if hmac.compare_digest(candidate, entry["token_sha256"])), None)
    if match is None:
        return None
    return {"id": match["id"], "name": match["name"], "role": match["role"]}

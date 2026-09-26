"""Reviewer tokens resolve to configured identities and fail closed."""
from __future__ import annotations

import hashlib
import json

from app import reviewer_auth


TOKEN = "reviewer-secret-is-long-and-random-0001"


def _registry(token=TOKEN):
    return json.dumps([{"id": "reviewer-1", "name": "A. Reviewer", "role": "reviewer",
                        "token_sha256": hashlib.sha256(token.encode()).hexdigest()}])


def test_review_token_resolves_a_configured_identity_without_client_name(monkeypatch):
    monkeypatch.setenv("SECTORAL_REVIEWERS", _registry())
    assert reviewer_auth.configured()
    assert reviewer_auth.authenticate(TOKEN) == {
        "id": "reviewer-1", "name": "A. Reviewer", "role": "reviewer"}
    assert reviewer_auth.authenticate("wrong") is None
    assert reviewer_auth.authenticate(None) is None
    assert reviewer_auth.approvals_enabled()


def test_invalid_or_ambiguous_registry_fails_closed(monkeypatch):
    monkeypatch.delenv("SECTORAL_REVIEWERS", raising=False)
    assert not reviewer_auth.configured()
    assert reviewer_auth.authenticate("anything") is None

    monkeypatch.setenv("SECTORAL_REVIEWERS", "not-json")
    assert not reviewer_auth.configured()
    assert not reviewer_auth.approvals_enabled()
    monkeypatch.setenv("SECTORAL_REVIEWERS", json.dumps([
        {"id": "same", "name": "First Reviewer", "role": "reviewer",
         "token_sha256": "a" * 64},
        {"id": "same", "name": "Second Reviewer", "role": "reviewer",
         "token_sha256": "b" * 64},
    ]))
    assert not reviewer_auth.configured()

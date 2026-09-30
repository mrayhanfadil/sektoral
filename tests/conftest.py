"""Shared test isolation for the analyst agent.

Tests must never call the real LLM or Tavily, or write to the app database in ``data/``.
Tests that exercise the agent pass their own scripted ``chat`` callable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.analyst import run as analyst_run  # noqa: E402
from agents.forecast_assumptions import run as forecast_run  # noqa: E402
from app import store, tavily  # noqa: E402


def _no_llm(_messages, **_kwargs):
    raise RuntimeError("LLM is disabled in tests")


@pytest.fixture(autouse=True)
def isolate_analyst(monkeypatch, tmp_path):
    monkeypatch.setattr(analyst_run, "_chat", _no_llm)
    # The forecast agent's subagents and its plan translation alike.
    monkeypatch.setattr(forecast_run, "_chat", _no_llm)
    # Agent memory, forecast plans, news and peer caches all live in the app
    # database; each test gets its own under tmp_path.
    monkeypatch.setattr(store, "DEFAULT_DB", tmp_path / "sectoral.db")
    # No real web search in tests; tests that need it inject their own ring.
    monkeypatch.setattr(tavily, "_RING", tavily.KeyRing([]))

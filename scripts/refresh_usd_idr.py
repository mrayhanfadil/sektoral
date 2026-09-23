#!/usr/bin/env python3
"""Explicitly refresh and print the cached Yahoo Finance USD/IDR close."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.fx import DEFAULT_CACHE_PATH, refresh_usd_idr  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH,
                        help=f"cache JSON path (default: {DEFAULT_CACHE_PATH})")
    args = parser.parse_args()
    try:
        result = refresh_usd_idr(cache_path=args.cache)
    except Exception as exc:
        print(f"USD/IDR refresh failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

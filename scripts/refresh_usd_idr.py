#!/usr/bin/env python3
"""Explicitly refresh and print the stored Yahoo Finance USD/IDR close."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.fx import refresh_usd_idr  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None,
                        help="app database (default: SECTORAL_DB or data/sectoral.db)")
    args = parser.parse_args()
    try:
        result = refresh_usd_idr(db=args.db)
    except Exception as exc:
        print(f"USD/IDR refresh failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

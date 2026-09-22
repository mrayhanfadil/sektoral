#!/usr/bin/env bash
# Toggle Sectors discipline modes in /home/fadil/.config/sectors-be/env and
# bounce the api container. Modes (any one can be set, or none):
#
#   SECTORS_OFFLINE=1      - refuse all UPSTREAM calls. Disk still serves: the
#                            SQLite sectors_cache hit and the freeze files in
#                            output/cache/ticker_fill/ (legacy ammn_fill/) are
#                            read normally. Only a genuinely cold endpoint
#                            raises sectors_offline_mode. Never bills.
#
#   SECTORS_CACHE_ONLY=1   - same as above, worded for "cache first" runs: on a
#                            miss, refuse upstream (599) at server/sectors._get()
#                            and label the ADK tool result
#                            {source: sectors_cache_only}. Use when the key is
#                            set but you want zero burn unless warmed.
#
#   SECTORS_STALE_OK=0     - strict TTL expiry. Off by default (1) because the
#                            cache is FOREVER LIVING: rows are stamped with the
#                            NEVER_EXPIRES_AT sentinel and never miss.
#
#   SECTORS_CACHE_TTL_DAYS - lifetime of a freshly written row. Unset/0 = forever
#                            (default). N = N days. tiers = legacy tier table.
#
#   FREEZE_TTL_DAYS        - recency gate on freeze files. Unset/0 = forever
#                            (default). N = refuse freezes older than N days.
#
# Usage:
#   bash scripts/toggle_sectors_offline.sh lock      # SECTORS_OFFLINE=1
#   bash scripts/toggle_sectors_offline.sh cache     # SECTORS_CACHE_ONLY=1
#   bash scripts/toggle_sectors_offline.sh forever   # no gates, cache lifetime forever
#   bash scripts/toggle_sectors_offline.sh unlock    # all off, key still in env
#
# After any change, bounce the api container so the new env is in effect:
#
#   bash /tmp/restart-api.sh

set -e

ENV_FILE="$HOME/.config/sectors-be/env"
# Every line this script owns; kept in one place so the clear paths can't drift.
_MANAGED='/^# SECTORS credit-discipline toggle/d; /^SECTORS_OFFLINE=/d; /^SECTORS_CACHE_ONLY=/d; /^SECTORS_STALE_OK=/d; /^SECTORS_CACHE_TTL_DAYS=/d; /^FREEZE_TTL_DAYS=/d'

case "${1:-}" in
    lock)
        MODE="SECTORS_OFFLINE"
        VAL="1"
        ;;
    cache)
        MODE="SECTORS_CACHE_ONLY"
        VAL="1"
        ;;
    forever)
        MODE="SECTORS_CACHE_TTL_DAYS"
        VAL="0"
        ;;
    unlock)
        MODE="__CLEAR__"
        VAL=""
        ;;
    *)
        echo "Usage: $0 {lock|cache|forever|unlock}" >&2
        exit 2
        ;;
esac

if [[ "$MODE" == "__CLEAR__" ]]; then
    # Strip every flag (and the comment line we add) from env, leave key intact
    if [[ -f "$ENV_FILE" ]]; then
        sed -i "$_MANAGED" "$ENV_FILE"
    fi
    echo "[toggle] cleared credit-discipline flags (key preserved)"
else
    if [[ ! -f "$ENV_FILE" ]]; then
        echo "[toggle] env file not found: $ENV_FILE" >&2
        exit 1
    fi
    # Idempotent: drop any prior lines, then append fresh ones
    sed -i "$_MANAGED" "$ENV_FILE"
    {
        echo "# SECTORS credit-discipline toggle (managed by scripts/toggle_sectors_offline.sh)"
        echo "SECTORS_STALE_OK=1"
        echo "SECTORS_CACHE_TTL_DAYS=0"
        echo "FREEZE_TTL_DAYS=0"
        echo "${MODE}=${VAL}"
    } >> "$ENV_FILE"
    echo "[toggle] set $MODE=$VAL (cache lifetime forever) in $ENV_FILE"
fi

# Always restart the api container so the new env is read by the running process
if [[ -f /tmp/restart-api.sh ]]; then
    bash /tmp/restart-api.sh
else
    echo "[toggle] /tmp/restart-api.sh missing - bounce api container manually:" >&2
    echo "         cd ~/projects/sectors-hackathon && make up" >&2
    exit 1
fi

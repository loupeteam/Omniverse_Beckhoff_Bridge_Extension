#!/usr/bin/env bash
# Headless Kit check for the Beckhoff bridge (see README.md).
#
# Usage:
#   tools/kit_check/run.sh --kit <kit build root> [--exts DIR] [--stage FILE] [--mode inject|live] [--log FILE]
#
# Every option can come from the environment instead:
#   FIXCHECK_KIT_ROOT  folder holding kit/kit.exe (a kit-app-template _build/<platform>/release)
#   FIXCHECK_EXTS      extension folder to load (default: this repo's exts/)
#   FIXCHECK_STAGE     stage to open (default: stages/mirror_test.usda next to this script)
#   FIXCHECK_MODE      "inject" = synthetic data, no PLC; "live" or empty = the PLC in the stage
#   FIXCHECK_LOG       where to keep Kit's output (default: kit_check.log in the current folder)
#
# The .kit is generated from fixcheck.kit.template with ${FIXCHECK_EXTS} and
# ${FIXCHECK_KIT_ROOT} substituted. Kit exits with code 7 by design: the script
# quits the app itself and os._exit(7)s if a dirty stage keeps it alive.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

KIT_ROOT="${FIXCHECK_KIT_ROOT:-}"
EXTS="${FIXCHECK_EXTS:-$REPO/exts}"
STAGE="${FIXCHECK_STAGE:-$HERE/stages/mirror_test.usda}"
MODE="${FIXCHECK_MODE:-}"
LOG="${FIXCHECK_LOG:-kit_check.log}"

while [ $# -gt 0 ]; do
    case "$1" in
        --kit)   KIT_ROOT="$2"; shift 2 ;;
        --exts)  EXTS="$2"; shift 2 ;;
        --stage) STAGE="$2"; shift 2 ;;
        --mode)  MODE="$2"; shift 2 ;;
        --log)   LOG="$2"; shift 2 ;;
        -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ "$MODE" = "live" ] && MODE=""
[ -n "$KIT_ROOT" ] || { echo "need --kit <kit build root> or FIXCHECK_KIT_ROOT" >&2; exit 2; }

# Kit wants forward slashes, and TOML strings would read backslashes as escapes.
native() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else echo "$1"; fi
}
KIT_ROOT="$(native "$(cd "$KIT_ROOT" && pwd)")"
EXTS="$(native "$(cd "$EXTS" && pwd)")"
STAGE="$(native "$(cd "$(dirname "$STAGE")" && pwd)/$(basename "$STAGE")")"

case "$LOG" in /*|[A-Za-z]:*) ;; *) LOG="$PWD/$LOG" ;; esac
KIT_EXE="$KIT_ROOT/kit/kit.exe"
[ -f "$KIT_EXE" ] || KIT_EXE="$KIT_ROOT/kit/kit"
[ -f "$KIT_EXE" ] || { echo "no kit/kit.exe under $KIT_ROOT" >&2; exit 2; }
[ -f "$STAGE" ] || { echo "no stage at $STAGE" >&2; exit 2; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
KIT_FILE="$WORK/fixcheck.kit"
sed -e "s|\${FIXCHECK_EXTS}|$EXTS|g" -e "s|\${FIXCHECK_KIT_ROOT}|$KIT_ROOT|g" \
    "$HERE/fixcheck.kit.template" > "$KIT_FILE"

echo "kit    $KIT_EXE"
echo "exts   $EXTS"
echo "stage  $STAGE"
echo "mode   ${MODE:-live}"
echo "log    $LOG"

# Kit puts its working directory on sys.path. Run it from the temp folder so a
# repo checkout's bare package folders (beckhoff_bridge/ at the root) cannot be
# picked up as empty namespace packages ahead of the installed ones.
cd "$WORK"
set +e
FIXCHECK_STAGE="$STAGE" FIXCHECK_MODE="$MODE" \
"$KIT_EXE" "$KIT_FILE" \
    --ext-folder "$KIT_ROOT/exts" \
    --ext-folder "$KIT_ROOT/extscache" \
    --ext-folder "$KIT_ROOT/apps" \
    --ext-folder "$EXTS" \
    --no-window --exec "$(native "$HERE/kit_check.py")" > "$LOG" 2>&1
CODE=$?
set -e

# Kit's own timestamped lines ("2026-...") are left in the log; show the check itself.
awk '/^fix check -- /{p=1} p && !/^20[0-9][0-9]-/' "$LOG"
echo "kit exit code $CODE (7 = quit forced after the check, expected)"
grep -q '^OK -- all fix checks passed' "$LOG"

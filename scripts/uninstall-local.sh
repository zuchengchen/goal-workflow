#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

usage() {
  printf '%s\n' \
    "Usage: scripts/uninstall-local.sh [--dest PATH] [--dry-run]" \
    "" \
    "Remove a validated goal-workflow installation." \
    "" \
    "Options:" \
    "  --dest PATH  Destination (default: \${CODEX_HOME:-\$HOME/.codex}/skills/goal-workflow)" \
    "  --dry-run    Validate and print the target without deleting it" \
    "  -h, --help   Show this help"
}

DEST=""
DRY_RUN=0
while (($#)); do
  case "$1" in
    --dest)
      if (($# < 2)); then
        printf 'ERROR: --dest requires a path\n' >&2
        exit 2
      fi
      DEST=$2
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$DEST" ]]; then
  if [[ -n "${CODEX_HOME:-}" ]]; then
    DEST="$CODEX_HOME/skills/goal-workflow"
  elif [[ -n "${HOME:-}" ]]; then
    DEST="$HOME/.codex/skills/goal-workflow"
  else
    printf 'ERROR: neither CODEX_HOME nor HOME is set; use --dest\n' >&2
    exit 2
  fi
fi

# Share the updater's lock for validation, quarantine, and removal.
UNINSTALL_ARGS=(--dest "$DEST")
if [[ $DRY_RUN -eq 1 ]]; then
  UNINSTALL_ARGS+=(--dry-run)
fi
exec python3 "$SCRIPT_DIR/uninstall-installed-skill.py" "${UNINSTALL_ARGS[@]}"

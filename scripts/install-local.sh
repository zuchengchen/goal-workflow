#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
SOURCE_DIR="$REPO_ROOT/skills/goal-workflow"
VALIDATOR="$SCRIPT_DIR/validate.py"

usage() {
  printf '%s\n' \
    "Usage: scripts/install-local.sh [--dest PATH] [--replace]" \
    "" \
    "Install the canonical goal-workflow skill from this checkout." \
    "" \
    "Options:" \
    "  --dest PATH  Destination (default: \${CODEX_HOME:-\$HOME/.codex}/skills/goal-workflow)" \
    "  --replace    Replace an existing installation without retaining a backup" \
    "  -h, --help   Show this help"
}

DEST=""
REPLACE=0
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
    --replace)
      REPLACE=1
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

python3 "$VALIDATOR" --skill-dir "$SOURCE_DIR" --installed-only >/dev/null

# Use the same locked transaction and recovery protocol as the updater.
INSTALL_ARGS=(--source-dir "$REPO_ROOT" --dest "$DEST" --keep-duplicates)
if [[ $REPLACE -eq 0 ]]; then
  INSTALL_ARGS+=(--no-replace)
fi
exec python3 "$SCRIPT_DIR/update-installed-skill.py" "${INSTALL_ARGS[@]}"

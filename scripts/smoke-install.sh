#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
INSTALLER="$SCRIPT_DIR/install-local.sh"
UNINSTALLER="$SCRIPT_DIR/uninstall-local.sh"
VALIDATOR="$SCRIPT_DIR/validate.py"
UPDATER="$SCRIPT_DIR/update-installed-skill.py"
CANONICAL="$REPO_ROOT/skills/goal-workflow"

TMP_ROOT="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM

TEST_USER_DIR="$TMP_ROOT/user"
TEST_CODEX_DIR="$TMP_ROOT/codex-home"
TEST_PROJECT_DIR="$TMP_ROOT/project"
mkdir -p "$TEST_USER_DIR" "$TEST_PROJECT_DIR"
cd "$TEST_PROJECT_DIR"

run_isolated() {
  env HOME="$TEST_USER_DIR" USERPROFILE="$TEST_USER_DIR" CODEX_HOME="$TEST_CODEX_DIR" "$@"
}

DEST="$TEST_CODEX_DIR/skills/goal-workflow"

run_isolated "$INSTALLER" >/dev/null
test -f "$DEST/SKILL.md"
cmp "$CANONICAL/SKILL.md" "$DEST/SKILL.md"
cmp "$CANONICAL/agents/openai.yaml" "$DEST/agents/openai.yaml"
python3 "$VALIDATOR" --skill-dir "$DEST" --installed-only >/dev/null

# Even a temporary cwd can have real installations in its ancestors. Keep
# duplicates here; updater_safety.py tests pruning with explicit fixture paths.
run_isolated "$UPDATER" --source-dir "$REPO_ROOT" --keep-duplicates >/dev/null
cmp "$CANONICAL/SKILL.md" "$DEST/SKILL.md"
cmp "$CANONICAL/agents/openai.yaml" "$DEST/agents/openai.yaml"
python3 "$VALIDATOR" --skill-dir "$DEST" --installed-only >/dev/null

DUPLICATE="$TEST_USER_DIR/.agents/skills/goal-workflow"
mkdir -p "$(dirname "$DUPLICATE")"
cp -R "$DEST" "$DUPLICATE"
run_isolated "$UPDATER" --source-dir "$REPO_ROOT" --keep-duplicates >/dev/null
test -e "$DUPLICATE"

if run_isolated "$INSTALLER" >/dev/null 2>&1; then
  printf 'ERROR: installer overwrote an existing destination without --replace\n' >&2
  exit 1
fi

UNSAFE_DEST="$TMP_ROOT/not-a-skills-directory/goal-workflow"
if run_isolated "$INSTALLER" --dest "$UNSAFE_DEST" >/dev/null 2>&1; then
  printf 'ERROR: installer accepted a destination outside a skills directory\n' >&2
  exit 1
fi
test ! -e "$UNSAFE_DEST"
test ! -e "$(dirname "$UNSAFE_DEST")"

WRONG_SKILL_DEST="$TMP_ROOT/wrong-skill/skills/goal-workflow"
mkdir -p "$WRONG_SKILL_DEST"
printf '%s\n' '---' 'name: another-skill' 'description: invalid identity' '---' >"$WRONG_SKILL_DEST/SKILL.md"
if run_isolated "$INSTALLER" --dest "$WRONG_SKILL_DEST" --replace >/dev/null 2>&1; then
  printf 'ERROR: installer replaced a same-named directory with the wrong skill identity\n' >&2
  exit 1
fi
test -f "$WRONG_SKILL_DEST/SKILL.md"
grep -q '^name: another-skill$' "$WRONG_SKILL_DEST/SKILL.md"

touch "$DEST/local-update-marker"
run_isolated "$INSTALLER" --replace >/dev/null
test ! -e "$DEST/local-update-marker"
python3 "$VALIDATOR" --skill-dir "$DEST" --installed-only >/dev/null

shopt -s nullglob
backups=("$TEST_CODEX_DIR/skills"/goal-workflow.backup.*)
replacements=("$TEST_CODEX_DIR/skills"/.goal-workflow.replace.*)
shopt -u nullglob
if [[ ${#backups[@]} -ne 0 || ${#replacements[@]} -ne 0 ]]; then
  printf 'ERROR: --replace left a backup or replacement directory behind\n' >&2
  exit 1
fi
test ! -e "$TEST_CODEX_DIR/skills/.goal-workflow.update.lock"
entries=("$TEST_CODEX_DIR/skills"/*)
if [[ ${#entries[@]} -ne 1 || "${entries[0]}" != "$DEST" ]]; then
  printf 'ERROR: update left more than the single goal-workflow skill directory\n' >&2
  exit 1
fi

run_isolated "$UNINSTALLER" --dry-run >/dev/null
test -d "$DEST"
run_isolated "$UNINSTALLER" >/dev/null
test ! -e "$DEST"

EXPLICIT_DEST="$TMP_ROOT/explicit/skills/goal-workflow"
run_isolated "$INSTALLER" --dest "$EXPLICIT_DEST" >/dev/null
run_isolated "$UNINSTALLER" --dest "$EXPLICIT_DEST" --dry-run >/dev/null
test -d "$EXPLICIT_DEST"
run_isolated "$UNINSTALLER" --dest "$EXPLICIT_DEST" >/dev/null
test ! -e "$EXPLICIT_DEST"

SYMLINK_DEST="$TMP_ROOT/symlink/skills/goal-workflow"
mkdir -p "$(dirname "$SYMLINK_DEST")"
ln -s "$CANONICAL" "$SYMLINK_DEST"
if run_isolated "$UNINSTALLER" --dest "$SYMLINK_DEST" >/dev/null 2>&1; then
  printf 'ERROR: uninstaller accepted a symbolic-link target\n' >&2
  exit 1
fi
test -f "$CANONICAL/SKILL.md"

INVALID_DEST="$TMP_ROOT/invalid/skills/goal-workflow"
mkdir -p "$INVALID_DEST"
printf '%s\n' '---' 'name: another-skill' 'description: invalid identity' '---' >"$INVALID_DEST/SKILL.md"
if run_isolated "$UNINSTALLER" --dest "$INVALID_DEST" >/dev/null 2>&1; then
  printf 'ERROR: uninstaller accepted a directory with the wrong skill identity\n' >&2
  exit 1
fi
test -d "$INVALID_DEST"

printf 'Install/update/uninstall smoke test passed in isolated CODEX_HOME.\n'

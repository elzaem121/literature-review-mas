#!/usr/bin/env bash
# Fail when a commit changes src/ or eval/ but not docs/STATUS.md, unless its message contains [no-status].
#
#   check_status_updated.sh <commit-msg-file>        commit-msg hook: checks the staged changes (`make hooks`)
#   check_status_updated.sh --commits <rev-list args> CI: checks every non-merge commit, e.g. --commits A..B
set -euo pipefail

STATUS_FILE="docs/STATUS.md"
SKIP_TAG="[no-status]"
WATCHED='^(src|eval)/'

# check <label> <changed paths, one per line> <commit message>
check() {
  if grep -qE "$WATCHED" <<<"$2" && ! grep -qxF "$STATUS_FILE" <<<"$2" && ! grep -qF "$SKIP_TAG" <<<"$3"; then
    echo "$1 changes src/ or eval/ but not $STATUS_FILE." >&2
    echo "Update $STATUS_FILE in the same commit, or put $SKIP_TAG in the commit message." >&2
    return 1
  fi
}

if [[ $# -eq 0 ]]; then
  echo "usage: $0 <commit-msg-file> | --commits <rev-list args>" >&2
  exit 2
fi

if [[ "$1" == "--commits" ]]; then
  shift
  failed=0
  for sha in $(git rev-list --no-merges --reverse "$@"); do
    files=$(git diff-tree --no-commit-id --name-only -r --root "$sha")
    message=$(git log -1 --format=%B "$sha")
    check "Commit ${sha:0:7}" "$files" "$message" || failed=1
  done
  exit "$failed"
fi

message=$(grep -v '^#' "$1" || true)
check "This commit" "$(git diff --cached --name-only)" "$message"

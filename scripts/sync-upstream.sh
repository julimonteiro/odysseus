#!/bin/sh
# Explicit fetch/merge. Never resets the fork or overwrites custom commits.
set -eu
mode=${1:---check}
branch=${2:-main}
case "$mode" in --check|--merge) ;; *) echo 'Usage: sync-upstream.sh [--check|--merge] [main|dev]' >&2; exit 2;; esac
case "$branch" in main|dev) ;; *) echo 'Choose upstream main or dev' >&2; exit 2;; esac
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo"
if ! git remote get-url upstream >/dev/null 2>&1; then
  git remote add upstream https://github.com/odysseus-dev/odysseus.git
fi
if [ -n "$(git status --porcelain)" ]; then
  echo 'Commit or stash local changes before syncing upstream.' >&2
  exit 1
fi
if [ -z "$(git branch --show-current)" ]; then
  echo 'Check out a branch before syncing upstream.' >&2
  exit 1
fi
git fetch upstream "$branch"
if [ "$mode" = --check ]; then
  git log --oneline "HEAD..upstream/$branch"
  echo 'Review the commits above, then rerun with --merge to merge them into the current branch.'
else
  git merge --no-ff --no-edit "upstream/$branch"
  echo 'Run project and upstream regression tests before pushing this merge.'
fi

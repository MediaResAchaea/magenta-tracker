#!/usr/bin/env bash
#
# Unattended sync for magenta-tracker — this is what the hourly scheduled task runs.
# Self-healing: ensures the repo/remote/Pages exist, pulls ONLY the new messages
# (incremental via fetch.py), and pushes the updated registry. Safe to re-run.
#
set -uo pipefail
cd "$(dirname "$0")"

GH_USER="MediaResAchaea"
REPO_NAME="${REPO_NAME:-magenta-tracker}"
SLUG="$GH_USER/$REPO_NAME"
log(){ echo "[$(date -u +%FT%TZ)] $*"; }

# 1. trust this working dir even under mixed ownership/elevation (added once)
SAFE="$(pwd -W 2>/dev/null || pwd)"
git config --global --get-all safe.directory 2>/dev/null | grep -qxF "$SAFE" \
  || git config --global --add safe.directory "$SAFE"

# 2. right GitHub identity + HTTPS credential helper for an unattended push
gh auth switch --hostname github.com --user "$GH_USER" >/dev/null 2>&1 || true
gh auth setup-git >/dev/null 2>&1 || true

# 3. ensure the local repo + identity
[ -d .git ] || git init -b main >/dev/null
git config user.name  "$GH_USER"
git config user.email "${GH_USER,,}@users.noreply.github.com"

# 4. ensure the remote repo exists
if ! gh repo view "$SLUG" >/dev/null 2>&1; then
  log "creating $SLUG"; gh repo create "$SLUG" --public >/dev/null
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$SLUG.git"

# 5. pull only the delta
log "fetching delta"
python fetch.py 2>&1 || python3 fetch.py 2>&1

git add -A

# 6. token safety — never commit the token, fail closed
if [ -f token.txt ]; then
  TOK="$(tr -d ' \t\r\n' < token.txt)"
  if [ -n "$TOK" ] && git grep -I --cached -qF "$TOK"; then
    log "ABORT: token appears in a staged file"; exit 1
  fi
fi

# 7. commit + push only if something changed
if git diff --cached --quiet; then
  log "no changes"
else
  git commit -m "data: refresh $(date -u +%FT%TZ)" >/dev/null
  git push -u origin main 2>&1 && log "pushed"
fi

# 8. make sure Pages is enabled (first run); cheap no-op afterward
gh api "repos/$SLUG/pages" >/dev/null 2>&1 \
  || { echo '{"source":{"branch":"main","path":"/docs"}}' | gh api -X POST "repos/$SLUG/pages" --input - >/dev/null 2>&1 && log "enabled Pages"; }

log "done"

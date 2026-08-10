#!/usr/bin/env bash
#
# Refresh the data and push. Run this whenever you want the site to catch up
# (or from cron / Task Scheduler). Assumes deploy.sh has already run once.
#
#   bash update.sh
#
set -euo pipefail
cd "$(dirname "$0")"

echo "==> fetching live data"
python fetch.py || python3 fetch.py

git add -A

# same fail-closed token check as deploy.sh
if [ -f token.txt ]; then
  TOK="$(tr -d ' \t\r\n' < token.txt)"
  if [ -n "$TOK" ] && git grep -I --cached -qF "$TOK"; then
    echo "   ABORT: your token string appears in a staged file."; exit 1
  fi
fi

if git diff --cached --quiet; then
  echo "==> no changes since last run"
  exit 0
fi

git commit -m "data: refresh $(date -u +%FT%TZ)"
git push
echo "==> pushed."

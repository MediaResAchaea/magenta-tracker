#!/usr/bin/env bash
#
# One-shot deploy: publish the magenta-tracker site to GitHub Pages under the
# MediaResAchaea account. Safe to re-run (idempotent).
#
#   bash deploy.sh              # deploy with whatever data.json is present
#   bash deploy.sh --with-data  # run fetch.py first, then deploy the live pull
#
# Override the repo name (e.g. for a bare user-site URL):
#   REPO_NAME=mediaresachaea.github.io bash deploy.sh --with-data
#
set -euo pipefail
cd "$(dirname "$0")"

GH_USER="MediaResAchaea"
REPO_NAME="${REPO_NAME:-magenta-tracker}"
SLUG="$GH_USER/$REPO_NAME"

# ---------------------------------------------------------------------------
# 0. optional: pull fresh data first
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--with-data" ]; then
  echo "==> fetching live data"
  python fetch.py || python3 fetch.py
fi

# ---------------------------------------------------------------------------
# 1. point gh + git at the right account, over HTTPS (token auth, no SSH keys)
# ---------------------------------------------------------------------------
echo "==> using GitHub account: $GH_USER"
gh auth switch --hostname github.com --user "$GH_USER"
gh auth setup-git

# ---------------------------------------------------------------------------
# 2. init repo + identity
# ---------------------------------------------------------------------------
[ -d .git ] || git init -b main
git config user.name  "$GH_USER"
git config user.email "${GH_USER,,}@users.noreply.github.com"

# make absolutely sure the token file is ignored
grep -qxF 'token.txt' .gitignore 2>/dev/null || echo 'token.txt' >> .gitignore

git add -A

# ---------------------------------------------------------------------------
# 3. SAFETY: never commit the token. Fail closed.
# ---------------------------------------------------------------------------
echo "==> token safety checks"
if git ls-files --error-unmatch token.txt >/dev/null 2>&1; then
  echo "   ABORT: token.txt is tracked by git."; exit 1
fi
if [ -f token.txt ]; then
  TOK="$(tr -d ' \t\r\n' < token.txt)"
  if [ -n "$TOK" ] && git grep -I --cached -qF "$TOK"; then
    echo "   ABORT: your token string appears in a staged file:"
    git grep -I --cached -nF "$TOK" || true
    exit 1
  fi
fi
echo "   ok: token.txt untracked, token not present in any staged file"

# ---------------------------------------------------------------------------
# 4. commit
# ---------------------------------------------------------------------------
if git diff --cached --quiet; then
  echo "==> nothing new to commit"
else
  git commit -m "magenta-tracker: update site"
fi

# ---------------------------------------------------------------------------
# 5. create remote repo (if needed) + push
# ---------------------------------------------------------------------------
if ! gh repo view "$SLUG" >/dev/null 2>&1; then
  echo "==> creating https://github.com/$SLUG (public)"
  gh repo create "$SLUG" --public
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$SLUG.git"
echo "==> pushing"
git push -u origin main

# ---------------------------------------------------------------------------
# 6. enable GitHub Pages on /docs (idempotent)
# ---------------------------------------------------------------------------
if gh api "repos/$SLUG/pages" >/dev/null 2>&1; then
  echo "==> Pages already enabled"
else
  echo "==> enabling Pages (branch main, folder /docs)"
  echo '{"source":{"branch":"main","path":"/docs"}}' | gh api -X POST "repos/$SLUG/pages" --input - >/dev/null
fi

# ---------------------------------------------------------------------------
# 7. report the URL
# ---------------------------------------------------------------------------
echo "==> done."
sleep 3
URL="$(gh api "repos/$SLUG/pages" --jq .html_url 2>/dev/null || true)"
echo "   Live at: ${URL:-https://${GH_USER,,}.github.io/$REPO_NAME/}"
echo "   (first build can take a minute or two.)"

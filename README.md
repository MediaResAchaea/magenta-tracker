# Magenta Tracker

An unofficial, Blizzard-blue-tracker-style feed of every post by the tracked
authors (currently **Ictinus** and **Edra**) in the Achaea Discord, rendered as
a static site you can host on GitHub Pages.

`fetch.py` pulls the messages via Discord's user-token message-search API and
writes `docs/data.json`; `docs/index.html` is a dependency-free page that renders
that JSON with search, per-author and per-channel filters, and links back to
each message.

```
magenta-tracker/
├─ config.json        guild, authors, channel list, window (days)
├─ fetch.py           pulls messages -> docs/data.json
├─ token.txt          your Discord token (gitignored — never committed)
├─ docs/
│  ├─ index.html      the static site (GitHub Pages serves this)
│  └─ data.json       the data the site reads (starts as a sample)
└─ .gitignore
```

## Heads-up before you run anything

- **This uses a user account token (self-botting).** That's against Discord's
  ToS and *can* get the account actioned. Use the alt you're fine risking, keep
  the rate low (the script already throttles), and don't automate sending.
- **GitHub Pages is public.** Publishing means Ictinus's posts — including
  anything pulled from the semi-gated `#feedback` forum threads — go on the open
  web. Decide what belongs there before you make the repo public. If you want it
  private, host the `docs/` folder behind auth on the michaelguer box instead.
- `token.txt` is in `.gitignore`. Keep it that way. If it ever lands in a commit,
  reset the token (change the account password) immediately.

## 1. Fetch the data

Requires Python 3.8+. The token is read from `$DISCORD_TOKEN`, or from
`token.txt` beside the script (already created for you).

```bash
cd magenta-tracker
python fetch.py                # last 7 days (config.json default)
python fetch.py --days 30      # wider window
python fetch.py --all          # everything the search index still holds
```

This overwrites `docs/data.json` with the live pull and prints a per-channel count.

## 2. Preview locally

`index.html` reads `data.json` with `fetch()`, so open it through a server, not
as a `file://` path:

```bash
cd docs
python -m http.server
# open http://localhost:8000
```

## 3. Publish to GitHub Pages

Pages is configured to serve the `/docs` folder on the default branch.

```bash
cd magenta-tracker
git init && git add . && git commit -m "magenta-tracker: initial"
gh repo create magenta-tracker --public --source=. --push   # or --private
gh api -X POST repos/:owner/magenta-tracker/pages -f source.branch=main -f source.path=/docs
```

(Or in the GitHub UI: **Settings → Pages → Source: main / /docs**.)
Site lands at `https://<user>.github.io/magenta-tracker/`. To use a custom
subdomain like `magenta.michaelguer.in`, add a `docs/CNAME` file and a DNS record.

## 4. Keep it updated — hourly, incremental, hands-off

`fetch.py` is **incremental** ("tombstoned"): the committed `docs/data.json` is
the state. Each run reads the newest stored message id and only asks Discord for
what's newer, plus a rolling `refresh_hours` window (config, default 6h) so
recent edits get updated. It never re-pulls the whole history.

### Automated via GitHub Actions (default)

`.github/workflows/track.yml` runs every hour, fetches the delta, and pushes the
updated registry — which rebuilds the Pages site. Set it up once:

```bash
# store the token as an encrypted repo secret (NOT in any file)
gh secret set DISCORD_TOKEN --repo MediaResAchaea/magenta-tracker < token.txt

# make sure the workflow is on the remote (deploy.sh already committed it)
git push
```

Then check the **Actions** tab; trigger a manual run with "Run workflow" to test.
Note: scheduled Actions can be delayed a few minutes under load — normal.

### Or run it locally / on the box

`update.sh` does the same fetch-commit-push and is now incremental too:

```cron
0 * * * *  cd /path/magenta-tracker && bash update.sh   # hourly on the michaelguer box
```

On Windows, point Task Scheduler at `bash update.sh` (residential IP — the
lowest-detection option). Ask and I'll hand you a one-shot registration script.

## Adding people

Edit `config.json` → `authors` and append `{ "id": "...", "username": "...",
"display": "..." }`. The id is the Discord user id (Settings → Advanced →
Developer Mode, then right-click the user → Copy User ID). The next run sees
the registry has nothing for that person yet and backfills their last `days`
days; after that they are incremental like everyone else. The site shows an
author filter row and per-post author tags whenever more than one person is
tracked.

## Adding channels

Edit `config.json` → `channels` (`"name": "channel_id"`). Forum channels are
fine: pass the forum's id and the search sweeps its accessible sub-threads.

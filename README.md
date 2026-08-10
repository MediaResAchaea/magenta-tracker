# Magenta Tracker

An unofficial, Blizzard-blue-tracker-style feed of every post by **Ictinus** in
the Achaea Discord, rendered as a static site you can host on GitHub Pages.

`fetch.py` pulls the messages via Discord's user-token message-search API and
writes `docs/data.json`; `docs/index.html` is a dependency-free page that renders
that JSON with search, per-channel filters, and links back to each message.

```
magenta-tracker/
├─ config.json        guild, author, channel list, window (days)
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

## 4. Keep it updated

`fetch.py` is idempotent — re-run it and re-push to refresh. To automate on the
michaelguer box:

```cron
# every 30 min: refresh data and push
*/30 * * * * cd /path/magenta-tracker && python fetch.py && git commit -am "refresh" && git push
```

(On Windows, the same thing via Task Scheduler.) For a hands-off pipeline, a
GitHub Action can run `fetch.py` on a schedule with the token stored as a repo
secret — ask and I'll wire it up.

## Adding channels

Edit `config.json` → `channels` (`"name": "channel_id"`). Forum channels are
fine: pass the forum's id and the search sweeps its accessible sub-threads.

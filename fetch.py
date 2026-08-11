#!/usr/bin/env python3
"""Magenta Tracker -- fetch Ictinus's recent posts from the Achaea Discord.

Uses the user-token message-search API (a user-account-only endpoint; bots
cannot call it) to pull the author's messages across the configured channels,
then merges them into docs/data.json -- the persistent registry the static
site reads.

INCREMENTAL BY DEFAULT ("tombstoned"): the committed docs/data.json IS the
state. Each run reads the highest message id already stored and only asks
Discord for what's newer than that, plus a small rolling "refresh window"
(config: refresh_hours) so recent edits get updated. It never re-pulls the
whole history. The first run (no registry yet) does the `days` backfill.

Usage:
    DISCORD_TOKEN=... python fetch.py     # incremental (or first-run backfill)
    python fetch.py --days 14             # force a wider backfill window
    python fetch.py --full                # ignore the registry, re-backfill `days`
    python fetch.py --all                 # no date floor at all (full history)

The token is read from $DISCORD_TOKEN or a token.txt file beside this script.
token.txt is gitignored -- it never gets committed or published.

Heads-up: driving a user account with a script is against Discord's ToS
(self-botting) and can get the account actioned. Run it on an account you're
willing to risk, keep the request rate low, and don't point it at anything you
wouldn't be comfortable seeing on a public page.
"""
import os, sys, json, time, argparse, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://discord.com/api/v10"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DISCORD_EPOCH = 1420070400000


def load_token():
    tok = os.environ.get("DISCORD_TOKEN")
    if tok:
        return tok.strip()
    path = os.path.join(HERE, "token.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    sys.exit("No token found: set $DISCORD_TOKEN or create token.txt beside fetch.py")


def load_config():
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as fh:
        return json.load(fh)


def load_registry(path):
    """Return the existing message dict {id: record}, or {} if none/sample."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return {}
    if data.get("sample"):          # the shipped placeholder -> treat as empty
        return {}
    return {m["id"]: m for m in data.get("messages", [])}


def api(token, path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    for _ in range(8):
        req = urllib.request.Request(url, headers={"Authorization": token, "User-Agent": UA})
        try:
            with urllib.request.urlopen(req) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code == 429:
                body = json.load(err)
                time.sleep(float(body.get("retry_after", 1)) + 0.3)
                continue
            if err.code == 202:
                time.sleep(2)
                continue
            if err.code in (403, 404):
                return {"_error": err.code}
            raise
    return {"_error": "retries-exhausted"}


def snowflake(ms):
    return (ms - DISCORD_EPOCH) << 22


def resolve_name(token, cid, id2name, feedback_id, cache):
    if cid in id2name:
        return id2name[cid]
    if cid in cache:
        return cache[cid]
    meta = api(token, f"/channels/{cid}")
    name = meta.get("name") or cid
    label = ("feedback / " + name) if meta.get("parent_id") == feedback_id else name
    cache[cid] = label
    return label


def build_record(token, guild, m, id2name, feedback_id, cache):
    cid = m["channel_id"]
    ref = m.get("referenced_message") or {}
    return {
        "id": m["id"],
        "channel_id": cid,
        "channel": resolve_name(token, cid, id2name, feedback_id, cache),
        "ts": m["timestamp"],
        "edited": m.get("edited_timestamp"),
        "content": m.get("content", ""),
        "attachments": [{"url": a.get("url"), "name": a.get("filename"),
                         "ct": a.get("content_type")} for a in m.get("attachments", [])],
        "embeds": [{"title": e.get("title"), "desc": e.get("description"),
                    "url": e.get("url")} for e in m.get("embeds", [])],
        "reply_to": ref.get("id"),
        "reply_excerpt": (ref.get("content") or "")[:160],
        "url": f"https://discord.com/channels/{guild}/{cid}/{m['id']}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="backfill window in days")
    ap.add_argument("--full", action="store_true", help="ignore registry, re-backfill `days`")
    ap.add_argument("--all", action="store_true", help="no date floor (full history)")
    args = ap.parse_args()

    token = load_token()
    cfg = load_config()
    guild = cfg["guild_id"]
    author = cfg["author"]
    channels = cfg["channels"]
    id2name = {v: k for k, v in channels.items()}
    feedback_id = channels.get("feedback")
    refresh_hours = cfg.get("refresh_hours", 6)
    days = args.days if args.days is not None else cfg.get("days", 7)

    outpath = os.path.join(HERE, cfg.get("output", "docs/data.json"))
    registry = {} if (args.full or args.all) else load_registry(outpath)

    # ---- decide how far back to ask Discord ----------------------------------
    if args.all:
        min_id, mode = None, "full history (no floor)"
    elif registry:
        max_id = max(int(i) for i in registry)
        refresh_floor = snowflake(int((time.time() - refresh_hours * 3600) * 1000))
        min_id = min(max_id, refresh_floor)          # cover the gap AND recent edits
        mode = f"incremental: {len(registry)} in registry, refresh window {refresh_hours}h"
    else:
        min_id, mode = snowflake(int((time.time() - days * 86400) * 1000)), f"first-run backfill {days}d"
    print(f"mode: {mode}", file=sys.stderr)

    params = [("author_id", author["id"]), ("limit", "25"),
              ("sort_by", "timestamp"), ("sort_order", "desc")]
    for cid in channels.values():
        params.append(("channel_id", cid))
    if min_id is not None:
        params.append(("min_id", str(min_id)))

    # ---- pull the delta ------------------------------------------------------
    fetched, cache, offset, total = {}, {}, 0, None
    while True:
        page = api(token, f"/guilds/{guild}/messages/search", params + [("offset", str(offset))])
        if "messages" not in page:
            print("search stopped:", str(page)[:200], file=sys.stderr)
            break
        total = page["total_results"]
        hits = [m for group in page["messages"] for m in group if m.get("hit")]
        if not hits:
            break
        for m in hits:
            fetched[m["id"]] = m
        offset += 25
        print(f"  ... {len(fetched)}/{total}", file=sys.stderr)
        if offset >= total or offset >= 5000:
            break
        time.sleep(0.4)

    # ---- merge into the registry (new/edited overwrite; nothing is dropped) --
    before = len(registry)
    added = 0
    for mid, m in fetched.items():
        if mid not in registry:
            added += 1
        registry[mid] = build_record(token, guild, m, id2name, feedback_id, cache)
    records = sorted(registry.values(), key=lambda r: r["ts"])

    out = {
        "author": author,
        "guild": guild,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "refresh_hours": refresh_hours,
        "since_id": max(registry) if registry else None,
        "count": len(records),
        "channels": channels,
        "messages": records,
    }
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print(f"registry {before} -> {len(records)} (+{added} new, {len(fetched)} fetched this run) "
          f"=> {outpath}")


if __name__ == "__main__":
    main()

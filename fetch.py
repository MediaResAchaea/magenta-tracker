#!/usr/bin/env python3
"""Magenta Tracker -- fetch Ictinus's recent posts from the Achaea Discord.

Uses the user-token message-search API (a user-account-only endpoint; bots
cannot call it) to pull every message by the configured author across the
configured channels, then writes docs/data.json for the static site.

Usage:
    DISCORD_TOKEN=... python fetch.py           # last N days (from config.json)
    python fetch.py --days 14                    # override the window
    python fetch.py --all                        # no date floor (full history)

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
            if err.code == 429:            # rate limited
                body = json.load(err)
                time.sleep(float(body.get("retry_after", 1)) + 0.3)
                continue
            if err.code == 202:            # search index still warming
                time.sleep(2)
                continue
            if err.code in (403, 404):     # no access / gone -- skip quietly
                return {"_error": err.code}
            raise
    return {"_error": "retries-exhausted"}


def snowflake(ms):
    return (ms - DISCORD_EPOCH) << 22


def resolve_name(token, cid, id2name, feedback_id, cache):
    """Map a channel id to a friendly label, tagging forum threads as feedback/<thread>."""
    if cid in id2name:
        return id2name[cid]
    if cid in cache:
        return cache[cid]
    meta = api(token, f"/channels/{cid}")
    name = meta.get("name") or cid
    label = ("feedback / " + name) if meta.get("parent_id") == feedback_id else name
    cache[cid] = label
    return label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="window size in days")
    ap.add_argument("--all", action="store_true", help="ignore the date floor")
    args = ap.parse_args()

    token = load_token()
    cfg = load_config()
    guild = cfg["guild_id"]
    author = cfg["author"]
    channels = cfg["channels"]
    id2name = {v: k for k, v in channels.items()}
    feedback_id = channels.get("feedback")
    days = 0 if args.all else (args.days if args.days is not None else cfg.get("days", 7))

    params = [("author_id", author["id"]), ("limit", "25"),
              ("sort_by", "timestamp"), ("sort_order", "desc")]
    for cid in channels.values():
        params.append(("channel_id", cid))
    if days > 0:
        cutoff_ms = int((time.time() - days * 86400) * 1000)
        params.append(("min_id", str(snowflake(cutoff_ms))))

    collected, cache, offset, total = {}, {}, 0, None
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
            collected[m["id"]] = m
        offset += 25
        print(f"  ... {len(collected)}/{total}", file=sys.stderr)
        if offset >= total or offset >= 5000:   # search caps out around 5000
            break
        time.sleep(0.4)

    records = []
    for m in collected.values():
        cid = m["channel_id"]
        ref = m.get("referenced_message") or {}
        records.append({
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
        })
    records.sort(key=lambda r: r["ts"])

    out = {
        "author": author,
        "guild": guild,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "count": len(records),
        "channels": channels,
        "messages": records,
    }
    outpath = os.path.join(HERE, cfg.get("output", "docs/data.json"))
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"Wrote {len(records)} messages to {outpath}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Turns a Collector Hall issue (from .github/ISSUE_TEMPLATE/collection.yml) into files under collections/.

It checks the submission with the same card matching as breakaway.py, then writes collections/<handle>.csv
(normalised: card numbers, editions and public card details only) and collections/<handle>.json. The workflow
opens a pull request with them; nothing is published until a maintainer merges it.

    python scripts/hall_submit.py --body issue.md --user-id 12345 [--dry-run] [--result result.json]

The GitHub user id (a number, not the username) is kept in the .json file so that the same account can update or
rename its own entry later and nobody else can take it over.
"""
import argparse, datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hall  # noqa: E402

FIELDS = {"handle": "Handle", "cards": "Cards", "blurb": "Short blurb (optional)", "team": "Favourite team (optional)",
          "confirm": "Before you submit"}
NO_TEAM = "No favourite team"


def sections(body):
    """### Heading -> text, the way GitHub writes issue form answers."""
    out, key, buf = {}, None, []
    for ln in (body or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.+?)\s*$", ln)
        if m:
            if key is not None: out[key] = "\n".join(buf).strip()
            key, buf = m.group(1), []
        elif key is not None: buf.append(ln)
    if key is not None: out[key] = "\n".join(buf).strip()
    return out


def field(sec, k):
    v = sec.get(FIELDS[k], "")
    return "" if v == "_No response_" else v


def unfence(s):
    m = re.match(r"^```[a-zA-Z]*\n(.*?)\n?```\s*$", s.strip(), re.S)
    return m.group(1) if m else s


def submit(body, user_id, dry_run=False, today=None):
    """-> {"ok": bool, "errors": [...], "notes": [...], "handle", "replaces", "files": [written/removed paths]}"""
    today = today or datetime.date.today().isoformat()
    res = {"ok": False, "errors": [], "notes": [], "handle": "", "replaces": "", "files": [], "removed": []}
    E = res["errors"].append
    sec = sections(body)
    handle = field(sec, "handle").strip().lstrip("@").strip().lower()
    res["handle"] = handle if hall.HANDLE_RE.match(handle) else ""
    if not handle: E("Pick a handle.")
    elif not hall.HANDLE_RE.match(handle): E("The handle must be 3-30 characters: lowercase letters, numbers and single dashes (like `puck-hoarder-97`).")
    elif handle in hall.RESERVED: E(f"`{handle}` is reserved. Please pick another handle.")
    if not str(user_id).isdigit(): E("Missing GitHub user id.")
    confirm = field(sec, "confirm")
    ticks = re.findall(r"^- \[[xX]\] ", confirm, re.M)
    if len(ticks) < 2: E("Tick both boxes under \"Before you submit\".")
    blurb = hall.clean_blurb(field(sec, "blurb"))
    team = field(sec, "team").strip()
    if team == NO_TEAM: team = ""
    meta = {"handle": handle, "blurb": blurb, "team": team}
    cards = unfence(field(sec, "cards"))
    if not cards.strip(): E("Paste your my_cards.csv (or a list of card numbers or NHL Breakaway links) into the Cards box.")
    elif len(cards.splitlines()) > hall.MAX_LINES: E(f"That list has more than {hall.MAX_LINES:,} lines.")
    tl = hall.teams()
    if res["handle"]:
        for e in hall.check_meta(handle, meta, set(tl)):
            E(e.split(": ", 1)[-1][:1].upper() + e.split(": ", 1)[-1][1:] + ".")
    mine, unmatched = ({}, [])
    if cards.strip() and len(cards.splitlines()) <= hall.MAX_LINES:
        mine, unmatched = hall.read_cards(cards)
        if not mine: E("None of the cards matched an archive moment. Paste your my_cards.csv export (with its header row), card numbers, or NHL Breakaway links.")
        elif unmatched:
            res["notes"].append(f"{len(unmatched)} line(s) didn't match an archive moment and were left out (for example: "
                                + ", ".join("`" + u[:60].replace("`", "'") + "`" for u in unmatched[:3]) + ").")
    # who owns what: one entry per GitHub account, a handle belongs to the account that first took it
    owners = {}
    if os.path.isdir(hall.DIR):
        for fn in os.listdir(hall.DIR):
            if fn.endswith(".json"):
                m = hall.b.jload(os.path.join(hall.DIR, fn), {}) or {}
                owners[fn[:-5]] = m
    if res["handle"] and handle in owners and str(owners[handle].get("github_id")) != str(user_id):
        E(f"The handle `{handle}` is already taken. Please pick another one.")
    mine_old = next((h for h, m in owners.items() if str(m.get("github_id")) == str(user_id) and h not in hall.EXAMPLES), "")
    if res["errors"]: return res
    old = owners.get(handle) or (owners.get(mine_old) if mine_old else None) or {}
    meta.update({"github_id": int(user_id), "added": old.get("added") or today, "updated": today})
    if not meta["blurb"]: del meta["blurb"]
    if not meta["team"]: del meta["team"]
    if mine_old and mine_old != handle:
        res["replaces"] = mine_old
        res["notes"].append(f"This replaces your earlier entry `@{mine_old}` (renamed to `@{handle}`).")
    elif mine_old == handle:
        res["notes"].append(f"This updates your existing entry `@{handle}`.")
    res["moments"], res["editions"] = len(mine), sum(len(v) for v in mine.values())
    csv_text = hall.to_csv(mine)
    if hall.read_cards(csv_text, "x.csv")[0] != mine: E("Internal check failed: the normalised CSV doesn't read back the same."); return res
    paths = {os.path.join(hall.DIR, handle + ".csv"): csv_text,
             os.path.join(hall.DIR, handle + ".json"): json.dumps(meta, indent=2, ensure_ascii=False) + "\n"}
    if not dry_run:
        os.makedirs(hall.DIR, exist_ok=True)
        for p, t in paths.items():
            with open(p, "w", encoding="utf-8", newline="\n") as f: f.write(t)
        if res["replaces"]:
            for ext in (".csv", ".json"):
                p = os.path.join(hall.DIR, res["replaces"] + ext)
                if os.path.exists(p): os.remove(p); res["removed"].append(os.path.relpath(p, hall.ROOT))
    res["files"] = [os.path.relpath(p, hall.ROOT) for p in paths]
    res["ok"] = True
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, help="file with the issue body")
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--result", help="write the result as JSON here")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    with open(a.body, encoding="utf-8") as f: body = f.read()
    r = submit(body, a.user_id, a.dry_run)
    if a.result:
        with open(a.result, "w", encoding="utf-8") as f: json.dump(r, f, indent=2)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()

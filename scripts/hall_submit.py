#!/usr/bin/env python3
"""Turns a Collector Hall issue (from .github/ISSUE_TEMPLATE/collection.yml) into files under collections/.

The Cards field may be pasted CSV/text or a GitHub drag-and-drop attachment link
(github.com/user-attachments/... or githubusercontent). Attachments are downloaded over HTTPS from
those hosts only (2 MB cap), then checked with the same card matching as breakaway.py. Writes
collections/<handle>.csv (normalised) and collections/<handle>.json. The workflow opens a pull
request; nothing is published until a maintainer merges it.

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

# Attachment downloads (drag-and-drop into the issue form). Public-repo files are
# reachable without a token; we still refuse any host that isn't GitHub.
ATTACH_RE = re.compile(
    r"https://(?:github\.com/user-attachments/(?:files|assets)/\S+|"
    r"(?:raw\.|cdn\.)?githubusercontent\.com/\S+|"
    r"user-images\.githubusercontent\.com/\S+)",
    re.I,
)
ATTACH_HOSTS = (
    "github.com",
    "githubusercontent.com",
    "raw.githubusercontent.com",
    "cdn.githubusercontent.com",
    "user-images.githubusercontent.com",
)
ATTACH_MAX = 2 * 1024 * 1024  # 2 MB


def _host_ok(host):
    host = (host or "").lower().split(":")[0]
    if host in ATTACH_HOSTS:
        return True
    # allow foo.githubusercontent.com
    return host.endswith(".githubusercontent.com")


def attachment_url(text):
    """First GitHub attachment / githubusercontent URL in the cards field, or None."""
    if not text:
        return None
    # Prefer markdown links whose label looks like a file
    for m in re.finditer(r"\[([^\]]+)\]\((https://[^)]+)\)", text):
        label, url = m.group(1), m.group(2)
        if ATTACH_RE.match(url) and _host_ok(re.match(r"https://([^/]+)", url).group(1)):
            return url.rstrip(").,;")
    m = ATTACH_RE.search(text)
    if not m:
        return None
    url = m.group(0).rstrip(").,;\"'")
    host = re.match(r"https://([^/]+)", url).group(1)
    return url if _host_ok(host) else None


def fetch_attachment(url, token=None):
    """Download url. Returns (text, err). Only GitHub hosts; size-capped; no shell."""
    import urllib.error
    import urllib.request
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https" or not _host_ok(parsed.hostname):
        return None, "That file link is not a GitHub attachment we can open."
    # Path should look like an attachment or a .csv/.txt
    path = parsed.path or ""
    if "user-attachments" not in path and not path.lower().endswith((".csv", ".txt")):
        # still allow githubusercontent with csv/txt; reject odd paths later by content
        if "githubusercontent.com" not in (parsed.hostname or ""):
            return None, "That file link is not a GitHub attachment we can open."

    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "breakaway-archive-collector-hall")
    req.add_header("Accept", "text/csv,text/plain,*/*")
    # Public attachments usually need no token; a token can 404 on user-attachments.
    # Only send Authorization when explicitly asked (ATTACH_TOKEN), never the default GITHUB_TOKEN
    # unless ATTACH_USE_TOKEN=1 — keep default unauthenticated for public files.
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — host allowlisted above
            final = resp.geturl()
            fhost = urlparse(final).hostname
            if not _host_ok(fhost):
                return None, "The download redirected off GitHub; not opening it."
            # Cap size: read at most ATTACH_MAX + 1
            buf = resp.read(ATTACH_MAX + 1)
    except urllib.error.HTTPError as e:
        return None, f"Could not download the attached file (HTTP {e.code}). Try pasting the CSV instead."
    except Exception:
        return None, "Could not download the attached file. Try pasting the CSV instead."

    if len(buf) > ATTACH_MAX:
        return None, f"That attachment is larger than {ATTACH_MAX // (1024 * 1024)} MB."
    # Reject obvious binary
    if b"\x00" in buf[:1024]:
        return None, "That attachment does not look like a text CSV."
    try:
        text = buf.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = buf.decode("latin-1")
        except Exception:
            return None, "That attachment could not be read as text."
    return text, None


def resolve_cards(raw):
    """Cards field -> (csv_text, note_or_none, error_or_none). Handles paste or attachment link."""
    text = unfence(raw or "")
    url = attachment_url(text)
    if not url:
        return text, None, None
    # Prefer the file when a GitHub attachment link is present (drag-and-drop path).
    token = os.environ.get("ATTACH_TOKEN") or None
    body, err = fetch_attachment(url, token=token)
    if err:
        return None, None, err
    note = "Read the cards from the file you attached."
    return body, note, None



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
    cards_raw = field(sec, "cards")
    cards, attach_note, attach_err = resolve_cards(cards_raw)
    if attach_err: E(attach_err)
    if attach_note: res["notes"].append(attach_note)
    if cards is None: cards = ""
    if not attach_err and not cards.strip(): E("Drag your my_cards.csv into the Cards box, or paste the CSV (or a list of card numbers or NHL Breakaway links).")
    elif cards.strip() and len(cards.splitlines()) > hall.MAX_LINES: E(f"That list has more than {hall.MAX_LINES:,} lines.")
    tl = hall.teams()
    if res["handle"]:
        for e in hall.check_meta(handle, meta, set(tl)):
            E(e.split(": ", 1)[-1][:1].upper() + e.split(": ", 1)[-1][1:] + ".")
    mine, unmatched = ({}, [])
    if not attach_err and cards.strip() and len(cards.splitlines()) <= hall.MAX_LINES:
        mine, unmatched = hall.read_cards(cards)
        if not mine: E("None of the cards matched an archive moment. Drag your my_cards.csv into the Cards box, or paste the export (with its header row), card numbers, or NHL Breakaway links.")
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

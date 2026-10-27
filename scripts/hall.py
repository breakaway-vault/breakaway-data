#!/usr/bin/env python3
"""Collector Hall: public collections that fans submit, kept as static files in collections/.

    collections/<handle>.csv    the cards, in my_cards.csv format (read with breakaway.py's own matching)
    collections/<handle>.json   small metadata: handle, optional blurb and favourite team

Used by scripts/build_site.py (to compile site/data/hall.json) and by scripts/hall_submit.py (the issue form
workflow). Run it directly to check every entry:

    python scripts/hall.py check
"""
import csv, io, json, os, re, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import breakaway as b  # noqa: E402  (read-only use of the app's loaders)

DIR = os.path.join(ROOT, "collections")
HANDLE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?=[a-z0-9])){2,29}$")   # 3-30 chars, a-z 0-9 and single dashes
RESERVED = {"example", "example-collector", "admin", "administrator", "maintainer", "moderator", "official", "staff",
            "support", "team", "nhl", "nhlpa", "sweet", "breakaway", "breakaway-archive", "archive", "hall", "null",
            "undefined", "anonymous", "me", "you"}
EXAMPLES = {"example-collector"}          # seed entries made up for the page, never real people
BLURB_MAX = 140
MAX_LINES = 10000


def model():
    """{card id: (player, team, set, rarity, series id, token id)} for every moment in the archive."""
    links = b.jload(os.path.join(b.DATA, "links.json"), {}) or {}
    out = {}
    for r in b.sort_rows(b.load_model()):
        s, ln = r["_s"], links.get(str(r["id"])) or {}
        out[str(r["id"])] = (s["player"], s["team"], s["set"], s["rarity"], ln.get("series_id", ""), str(ln.get("token_id", "")))
    return out


def teams():
    return sorted({t for (_, t, _, _, _, _) in model().values() if t})


def read_cards(text, name="my_cards.txt"):
    """-> (mine, unmatched), matched exactly like breakaway.py "Show only my cards" (and the site's in-browser reader)."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8", newline="") as f: f.write(text)
        return b.load_mine(p, quiet=True)


def to_csv(mine, mdl=None):
    """The canonical my_cards.csv this project writes (the same columns as the site's Export my_cards.csv)."""
    mdl = mdl or model()
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n")
    w.writerow(["card_id", "edition", "player", "team", "set", "rarity", "url"])
    for cid in sorted(mine, key=int):
        player, team, set_, rarity, sid, tok = mdl.get(cid, ("", "", "", "", "", ""))
        for e in mine[cid] or [None]:
            url = f"https://nhlbreakaway.com/series/{sid}/{((int(tok) >> 48) << 48) + e - 1}" if e and sid and tok.isdigit() else ""
            w.writerow([cid, e or "", player, team, set_, rarity, url])
    return buf.getvalue()


def clean_blurb(s):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s


def check_meta(handle, meta, team_list):
    errs = []
    if not HANDLE_RE.match(handle or ""): errs.append(f"handle {handle!r}: use 3-30 lowercase letters, numbers and single dashes")
    if meta.get("handle") != handle: errs.append(f"{handle}.json: handle must be {handle!r}")
    blurb = meta.get("blurb") or ""
    if len(blurb) > BLURB_MAX: errs.append(f"{handle}: blurb is longer than {BLURB_MAX} characters")
    if re.search(r"https?://|www\.|<|>", blurb): errs.append(f"{handle}: no links or HTML in the blurb")
    if meta.get("team") and meta["team"] not in team_list: errs.append(f"{handle}: unknown team {meta['team']!r}")
    if meta.get("example") and handle not in EXAMPLES: errs.append(f"{handle}: only seed entries can be examples")
    return errs


def entries(strict=False):
    """-> ([hall entries for the site], [problems]). Each entry: h, blurb, team, example, added, updated, mine."""
    out, probs = [], []
    if not os.path.isdir(DIR): return out, probs
    tl = set(teams())
    for fn in sorted(os.listdir(DIR)):
        if not fn.endswith(".csv"): continue
        h = fn[:-4]; mp = os.path.join(DIR, h + ".json")
        meta = b.jload(mp, None) if os.path.exists(mp) else None
        if meta is None: probs.append(f"{h}: missing {h}.json"); continue
        errs = check_meta(h, meta, tl)
        mine, unmatched = b.load_mine(os.path.join(DIR, fn), quiet=True)
        if not mine: errs.append(f"{h}: no cards matched")
        if unmatched: errs.append(f"{h}: {len(unmatched)} line(s) don't match an archive moment")
        if errs: probs += errs; continue
        out.append({"h": h, "blurb": meta.get("blurb") or "", "team": meta.get("team") or "", "example": bool(meta.get("example")),
                    "added": meta.get("added", ""), "updated": meta.get("updated", ""), "mine": mine})
    for fn in os.listdir(DIR):
        if fn.endswith(".json") and not os.path.exists(os.path.join(DIR, fn[:-5] + ".csv")): probs.append(f"{fn}: no matching .csv")
    return out, probs


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]: sys.exit(__doc__)
    es, probs = entries()
    for pr in probs: print("problem:", pr)
    print(f"{len(es)} Collector Hall entr{'y' if len(es) == 1 else 'ies'}, {len(probs)} problem(s)")
    sys.exit(1 if probs else 0)

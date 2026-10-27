#!/usr/bin/env python3
"""Collector Hall: public collections that fans submit, kept as static files in collections/.

    collections/<handle>.csv    the cards, in my_cards.csv format (read with breakaway.py's own matching)
    collections/<handle>.json   small metadata: handle, display_name (the name as typed), optional blurb and team

<handle> is the slug made from the name people type ("Rink Rat 97" -> rink_rat_97); see clean_name().

Used by scripts/build_site.py (to compile site/data/hall.json) and by scripts/hall_submit.py (the issue form
workflow). Run it directly to check every entry:

    python scripts/hall.py check
    python scripts/hall.py find "Rink Rat 97"     which entry a name or slug points to (for removals)
"""
import csv, io, json, os, re, sys, tempfile, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import breakaway as b  # noqa: E402  (read-only use of the app's loaders)

DIR = os.path.join(ROOT, "collections")
HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,28}[a-z0-9]$")  # 3-30 chars, a-z 0-9 _ -, start/end alnum
RESERVED = {"example", "example-collector", "maple-leafs-complete", "admin", "administrator", "maintainer", "moderator", "official", "staff",
            "support", "team", "nhl", "nhlpa", "sweet", "breakaway", "breakaway-archive", "archive", "hall", "null",
            "undefined", "anonymous", "me", "you"}
EXAMPLES = {"example-collector", "maple-leafs-complete"}  # seed entries made up for the page, never real people
NAME_MIN, NAME_MAX = 3, 30
NAME_HELP = ("Use 3 to 30 characters: letters, numbers, spaces, underscores (_), dashes (-) and periods (.). "
             "Your NHL Breakaway name works, and capitals and spaces are fine (like `Rink Rat 97` or `puck_hoarder_97`).")
BLURB_MAX = 140


def slugify(name):
    """The file name / link part for a display name: "Rink Rat 97" -> "rink_rat_97", "J.R. Smith" -> "j_r_smith"."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[\s.]+", "_", s)
    s = re.sub(r"[^a-z0-9_-]", "", s)
    s = re.sub(r"[_-]{2,}", lambda m: "_" if "_" in m.group() else "-", s)
    return s.strip("_-")


def clean_name(raw):
    """What someone typed as a handle -> (display_name, slug, error). error is one friendly sentence or ""."""
    s = unicodedata.normalize("NFC", raw or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip("`'\"“”‘’").strip().lstrip("@").strip()
    s = re.sub(r"\s+", " ", s)
    if not s: return "", "", "Type a name for your Collector Hall page (your NHL Breakaway name is perfect)."
    if re.search(r"https?:|www\.|[<>\[\]()/\\]", s, re.I):
        return "", "", "The name can't be a link or contain code. " + NAME_HELP
    bad = sorted({c for c in s if not (c.isalnum() or c in " _-.")})
    if bad:
        shown = " ".join(c if c.isprintable() else "?" for c in bad[:5])
        return "", "", f"The name has characters that aren't allowed ({shown}). " + NAME_HELP
    if not NAME_MIN <= len(s) <= NAME_MAX:
        return "", "", f"The name is {len(s)} characters long. " + NAME_HELP
    slug = slugify(s)
    if not HANDLE_RE.match(slug):
        return "", "", "The name needs at least 3 plain letters or numbers (A-Z, 0-9). " + NAME_HELP
    return s, slug, ""
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
    if not HANDLE_RE.match(handle or ""): errs.append(f"handle {handle!r}: use 3-30 lowercase letters, numbers, underscores and dashes (start and end with a letter or number)")
    if meta.get("handle") != handle: errs.append(f"{handle}.json: handle must be {handle!r}")
    if "display_name" in meta:
        dn, sl, err = clean_name(meta.get("display_name"))
        if err or dn != meta["display_name"]: errs.append(f"{handle}: display_name {meta.get('display_name')!r} is not allowed")
        elif sl != handle: errs.append(f"{handle}: display_name {dn!r} makes the link {sl!r}, not {handle!r}")
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
        out.append({"h": h, "name": meta.get("display_name") or h, "blurb": meta.get("blurb") or "", "team": meta.get("team") or "", "example": bool(meta.get("example")),
                    "added": meta.get("added", ""), "updated": meta.get("updated", ""), "mine": mine})
    for fn in os.listdir(DIR):
        if fn.endswith(".json") and not os.path.exists(os.path.join(DIR, fn[:-5] + ".csv")): probs.append(f"{fn}: no matching .csv")
    return out, probs


if __name__ == "__main__":
    if sys.argv[1:2] == ["find"] and len(sys.argv) > 2:
        q = " ".join(sys.argv[2:]); m = re.search(r"#h=([^&\s]+)", q)
        if m: from urllib.parse import unquote; q = unquote(m.group(1))
        _, sl, _e = clean_name(q); sl = sl or slugify(q)
        hit = [fn[:-5] for fn in sorted(os.listdir(DIR)) if fn.endswith(".json")
               and (fn[:-5] in (q.strip().lstrip("@").lower(), sl) or (b.jload(os.path.join(DIR, fn), {}) or {}).get("display_name") == q.strip().lstrip("@"))]
        print("\n".join(f"collections/{h}.csv + collections/{h}.json" for h in hit) or f"no entry for {q!r} (its link would be #h={sl})")
        sys.exit(0 if hit else 1)
    if sys.argv[1:] != ["check"]: sys.exit(__doc__)
    es, probs = entries()
    for pr in probs: print("problem:", pr)
    print(f"{len(es)} Collector Hall entr{'y' if len(es) == 1 else 'ies'}, {len(probs)} problem(s)")
    sys.exit(1 if probs else 0)

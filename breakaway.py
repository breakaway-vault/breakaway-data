#!/usr/bin/env python3
"""
breakaway-data: a preservation archive of NHL Breakaway highlight metadata.

USAGE
  python breakaway.py all                 # fetch (only new/missing) -> covers -> build -> package
  python breakaway.py fetch [--refresh]   # master list, highlight->token links, raw nft. metadata
  python breakaway.py covers              # full-res cover art into output/covers_full/ (sha256-checked)
  python breakaway.py build               # OFFLINE: rebuild output/highlights.xlsx from data/ only
  python breakaway.py package             # output/covers/, covers.zip, Breakaway-Highlights.zip
  python breakaway.py videos [--out-dir DIR] [--limit N] [--series "Series 3"] [--ids 12,40] [--yes]
                                          # OPT-IN video download (asks y/n after a size estimate)
  Common flags: --concurrency N (default 6, max 8) for nft.nhlbreakaway.com / CDN requests.

SOURCES (all public, no login)
  card list     data/highlights.json
  links         NHL Breakaway set listings (apigw.sweet.io/catalog/search/moment/set/<set>), matched on
                set + player + series; leftovers from the card page lookup, one request
                at a time with a 1s pause (small community site).
  on-chain-ish  https://nft.nhlbreakaway.com/series/<series>/<token>  saved byte-for-byte to data/meta/<id>.json
  off-chain     raw set listings + set completion + quest data in data/offchain/
  covers/video  nft.nhlbreakaway.com image CDN and mediagateway.sweet.io (output/, gitignored)
"""
import argparse, base64, concurrent.futures as cf, csv, datetime as dt, hashlib, html, io, json, os, re
import sys, threading, time, unicodedata, urllib.error, urllib.request, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA, OUT, CACHE = (os.path.join(ROOT, d) for d in ("data", "output", "cache"))
SITE = ""  # card-list site removed from this archive
NFT = "https://nft.nhlbreakaway.com/series"
APIGW = "https://apigw.sweet.io"
UA = "Mozilla/5.0 (breakaway-data preservation export; polite, cached)"
HDR = {"User-Agent": UA, "Referer": "https://nhlbreakaway.com/", "Origin": "https://nhlbreakaway.com"}


def p(*a): print(*a, flush=True)
def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def jload(path, default=None):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default
def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"; json.dump(obj, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False); os.replace(tmp, path)
def wbytes(path, b):
    os.makedirs(os.path.dirname(path), exist_ok=True); tmp = path + ".part"
    open(tmp, "wb").write(b); os.replace(tmp, path)


# ------------------------------------------------------------------ polite HTTP
class Throttle:
    def __init__(self, n, base=0.15):
        self.sem = threading.Semaphore(n); self.base = base; self.delay = base; self.lock = threading.Lock()
    def ok(self):
        with self.lock: self.delay = max(self.base, self.delay * 0.9)
    def bad(self):
        with self.lock: self.delay = min(30.0, self.delay * 2 + 0.5)

THR = Throttle(6)


def http(url, method="GET", tries=6, timeout=60, thr=None, headers=None):
    """Returns (status, bytes, headers). 401/403/404 are final (never worked around)."""
    thr = thr or THR
    for i in range(tries):
        thr.sem.acquire(); time.sleep(thr.delay)
        try:
            req = urllib.request.Request(url, headers={**HDR, **(headers or {})}, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read() if method == "GET" else b""
                thr.ok(); return r.status, b, r.headers
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 410):
                return e.code, None, e.headers
            thr.bad(); ra = e.headers.get("Retry-After") if e.headers else None
            time.sleep(float(ra) if ra and ra.isdigit() else min(60, 2 ** (i + 1)))
        except Exception:
            thr.bad(); time.sleep(min(60, 2 ** (i + 1)))
        finally:
            thr.sem.release()
    return None, None, None


def norm(s):
    s = unicodedata.normalize("NFKD", html.unescape(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)
def strip(s): return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


# ------------------------------------------------------------------ master list
def fetch_master(refresh):
    raw = os.path.join(DATA, "master", "highlights.html")
    if refresh or not os.path.exists(raw):
        p("Fetching master list (one request) from", SITE + "/highlights")
        st, b, _ = http(SITE + "/highlights", timeout=150, thr=Throttle(1, 1.0))
        if not b: sys.exit("Could not load the card list page. Try again.")
        wbytes(raw, b)
    page = open(raw, encoding="utf-8", errors="replace").read()
    rows = []
    for tr in re.findall(r"<tr data-player=.*?</tr>", page, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        cid = int(re.search(r'href="/player/(\d+)', tr).group(1))
        rar = re.search(r"alt=['\"]([^'\"]+)['\"]", tds[2]); ed = strip(tds[3])
        rows.append({"id": cid, "player": strip(tds[0]), "set": strip(tds[1]),
                     "rarity": rar.group(1) if rar else strip(tds[2]),
                     "editions": None if ed == "--" else (int(ed) if ed.isdigit() else ed),
                     "team": strip(tds[4]), "lowest_ask": strip(tds[5]),
                     "fmv": strip(tds[7]) if len(tds) > 7 else "", "card_url": f"{SITE}/player/{cid}"})
    rows.sort(key=lambda r: r["id"])
    jdump(rows, os.path.join(DATA, "highlights.json"))
    return rows


# ------------------------------------------------------------------ off-chain set data + links
def fetch_offchain(refresh):
    od = os.path.join(DATA, "offchain")
    thr = Throttle(3, 0.3)
    def grab(rel, url):
        path = os.path.join(od, rel)
        if refresh or not os.path.exists(path):
            st, b, _ = http(url, thr=thr)
            if b: wbytes(path, b)
        return jload(path, [])
    sc = grab("setcompletion_826.json", f"{APIGW}/gameplay/setcompletion?campaign_id=826")
    cc = grab("collection_challenge_826.json", f"{APIGW}/gameplay/collection-challenge?campaign_id=826")
    sets = {x["set_uuid"] for x in sc if x.get("set_uuid")}
    for c in cc:
        for h in c.get("highlights") or []:
            if h.get("moment_uuid"): sets.add(h["moment_uuid"][:12] + "0" * 20)
    md = os.path.join(DATA, "meta")
    if os.path.isdir(md):
        for fn in os.listdir(md):
            try:
                a = {t["name"]: t["value"] for t in jload(os.path.join(md, fn)).get("attributes", [])}
                if a.get("Set UUID"): sets.add(a["Set UUID"])
            except Exception: pass
    with cf.ThreadPoolExecutor(3) as ex:
        list(ex.map(lambda u: grab(f"sets/{u}.json", f"{APIGW}/catalog/search/moment/set/{u}?campaign_id=826"), sorted(sets)))
    moments = []
    for fn in sorted(os.listdir(os.path.join(od, "sets"))):
        for m in jload(os.path.join(od, "sets", fn), []):
            sc_ = re.search(r"/series/([A-Za-z0-9]{8})/", json.dumps(m.get("assets")))
            moments.append({"uuid": m["uuid"], "player": m.get("name"), "set": (m.get("token_set") or {}).get("name"),
                            "series_name": (m.get("token_series") or {}).get("name"),
                            "rarity": (m.get("rarity") or {}).get("name"), "series_id": sc_.group(1) if sc_ else None,
                            "file": f"data/offchain/sets/{fn}", "raw": m})
    p(f"Off-chain: {len(sets)} sets, {len(moments)} moments listed by NHL Breakaway")
    return moments


SUF = re.compile(r"\s*\((S1|S2|S3|I|II|III)\)\s*$")
SUF_SERIES = {"S1": "Series 1", "I": "Series 1", "S2": "Series 2", "II": "Series 2", "S3": "Series 3", "III": "Series 3"}


def build_links(rows, moments, crawl=True):
    path = os.path.join(DATA, "links.json"); links = jload(path, {})
    idx = {}
    for m in moments: idx.setdefault((norm(m["set"]), norm(m["player"])), {})[m["uuid"]] = m
    todo = []
    for r in rows:
        k = str(r["id"])
        if k in links: continue
        sm = SUF.search(r["set"]); want = SUF_SERIES[sm.group(1)] if sm else None
        cands = list(idx.get((norm(SUF.sub("", r["set"])), norm(r["player"])), {}).values())
        if want: cands = [m for m in cands if m["series_name"] == want]
        elif len({m["series_name"] for m in cands}) > 1: cands = [m for m in cands if m["series_name"] == "Series 1"] or cands
        if len(cands) > 1: cands = [m for m in cands if norm(m["rarity"]) == norm(r["rarity"])] or cands
        if len(cands) == 1 and cands[0]["series_id"]:
            m = cands[0]
            links[k] = {"series_id": m["series_id"], "token_id": str(int(m["uuid"][16:20], 16) << 48),
                        "moment_uuid": m["uuid"], "via": "NHL Breakaway set listing match (set+player+series)"}
        else: todo.append(r["id"])
    if todo and crawl:
        p(f"{len(todo)} highlights need the card page lookup; fetching one at a time (1s gap)")
        pc = os.path.join(CACHE, "player"); thr = Throttle(1, 1.0)
        for n, cid in enumerate(todo, 1):
            fp = os.path.join(pc, f"{cid}.html")
            if not os.path.exists(fp):
                st, b, _ = http(f"{SITE}/player/{cid}", timeout=150, thr=thr)
                if b: wbytes(fp, b)
            if os.path.exists(fp):
                m = re.search(r"https://nhlbreakaway\.com/series/([A-Za-z0-9]+)/(\d+)", open(fp, encoding="utf-8", errors="replace").read())
                if m: links[str(cid)] = {"series_id": m.group(1), "token_id": str(int(m.group(2)) >> 48 << 48),
                                         "via": "card page lookup"}
            if n % 25 == 0: p(f"  player pages {n}/{len(todo)}")
    jdump(dict(sorted(links.items(), key=lambda x: int(x[0]))), path)
    return links


# ------------------------------------------------------------------ raw nft. metadata
def b64sha(b): return base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode()


def ipfs_entries(d):
    """Every (path, ipfs CID, sha256, url) found anywhere in a metadata doc."""
    out = []
    def walk(o, path):
        if isinstance(o, dict):
            if isinstance(o.get("altloc"), dict) and o["altloc"].get("ipfs"):
                out.append({"path": path, "ipfs": o["altloc"]["ipfs"], "sha256": o.get("sha256"), "url": o.get("url") or o.get("uri")})
            for k, v in o.items(): walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o): walk(v, f"{path}[{i}]")
    walk(d, ""); return out


def fetch_meta(links, refresh):
    mdir = os.path.join(DATA, "meta"); mpath = os.path.join(DATA, "manifest.json")
    man = jload(mpath, {}); lock = threading.Lock()
    def one(k):
        ln = links[k]; url = f"{NFT}/{ln['series_id']}/{ln['token_id']}"; fp = os.path.join(mdir, f"{k}.json")
        e = man.get(k, {})
        if not refresh and os.path.exists(fp) and e.get("status") == 200 and e.get("source_url") == url:
            return
        st, b, h = http(url)
        e = {"id": int(k), "source_url": url, "fetched_at": now(), "status": st, "link_via": ln.get("via")}
        if b:
            wbytes(fp, b)
            e.update({"meta_path": f"data/meta/{k}.json", "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                      "content_type": h.get("Content-Type") if h else None})
            try: e["ipfs"] = ipfs_entries(json.loads(b))
            except Exception: e["parse_error"] = True
        with lock: man[k] = e
    keys = sorted(links, key=int)
    with cf.ThreadPoolExecutor(THR.sem._value) as ex:
        for n, _ in enumerate(ex.map(one, keys), 1):
            if n % 250 == 0: p(f"  metadata {n}/{len(keys)}")
    for _ in range(2):  # retry failures, slower
        bad = [k for k in keys if man.get(k, {}).get("status") != 200]
        if not bad: break
        p(f"  retrying {len(bad)} failed metadata fetches"); time.sleep(10)
        for k in bad: one(k)
    jdump(dict(sorted(man.items(), key=lambda x: int(x[0]))), mpath)
    return man


def cmd_fetch(a):
    rows = fetch_master(a.refresh)
    moments = fetch_offchain(a.refresh)
    links = build_links(rows, moments, crawl=not a.no_crawl)
    man = fetch_meta(links, a.refresh)
    # edition #1 of a moment can be missing (never minted / burned): fall back to the real token on the
    # card page lookup (one request each, 1s gap) and keep that exact token
    miss = [k for k, e in man.items() if e.get("status") == 404 and not links[k].get("exact")]
    if miss and not a.no_crawl:
        thr = Throttle(1, 1.0)
        for k in miss:
            fp = os.path.join(CACHE, "player", f"{k}.html")
            if not os.path.exists(fp):
                st, b, _ = http(f"{SITE}/player/{k}", timeout=150, thr=thr)
                if b: wbytes(fp, b)
            if os.path.exists(fp):
                m = re.search(r"https://nhlbreakaway\.com/series/([A-Za-z0-9]+)/(\d+)", open(fp, encoding="utf-8", errors="replace").read())
                if m: links[k] = {"series_id": m.group(1), "token_id": m.group(2), "exact": True,
                                  "via": "card page lookup (edition #1 token missing)"}
        jdump(dict(sorted(links.items(), key=lambda x: int(x[0]))), os.path.join(DATA, "links.json"))
        man = fetch_meta(links, False)
    # attach off-chain moment pointer to manifest
    by_uuid = {m["uuid"]: m for m in moments}
    for k, e in man.items():
        try:
            u = {t["name"]: t["value"] for t in jload(os.path.join(DATA, "meta", f"{k}.json")).get("attributes", [])}.get("Moment UUID")
        except Exception: u = None
        if u: e["moment_uuid"] = u
        if u in by_uuid: e["offchain_path"] = by_uuid[u]["file"]
    jdump(dict(sorted(man.items(), key=lambda x: int(x[0]))), os.path.join(DATA, "manifest.json"))
    ok = sum(1 for e in man.values() if e.get("status") == 200)
    size = sum(os.path.getsize(os.path.join(DATA, "meta", f)) for f in os.listdir(os.path.join(DATA, "meta")))
    off = sum(1 for e in man.values() if e.get("offchain_path"))
    p(f"Fetch done: {len(rows)} highlights, {len(links)} linked, {ok} metadata OK, "
      f"{len(man) - ok} failed, {off} with off-chain data; data/meta = {size/1e6:.1f} MB")


# ------------------------------------------------------------------ offline model
def flat(o, pre="", out=None):
    out = {} if out is None else out
    if isinstance(o, dict):
        for k, v in o.items(): flat(v, f"{pre}.{k}" if pre else k, out)
    elif isinstance(o, list):
        if o and all(isinstance(x, dict) and "name" in x and "value" in x and len(x) <= 3 for x in o):
            for x in o: out[f"{pre}.{x['name']}"] = x["value"]
        elif o and all(isinstance(x, dict) and "purpose" in x for x in o):
            for x in o: flat({kk: vv for kk, vv in x.items() if kk != "purpose"}, f"{pre}.{x['purpose']}", out)
        elif all(not isinstance(x, (dict, list)) for x in o): out[pre] = ", ".join(map(str, o))
        else:
            for i, x in enumerate(o): flat(x, f"{pre}[{i}]", out)
    else: out[pre] = o
    return out


def load_model():
    rows = jload(os.path.join(DATA, "highlights.json"))
    if not rows: sys.exit("No data/highlights.json yet. Run: python breakaway.py fetch")
    man = jload(os.path.join(DATA, "manifest.json"), {})
    offc = {}
    sd = os.path.join(DATA, "offchain", "sets")
    if os.path.isdir(sd):
        for fn in os.listdir(sd):
            for m in jload(os.path.join(sd, fn), []): offc[m["uuid"]] = m
    for r in rows:
        k = str(r["id"]); e = man.get(k, {}); r["_man"] = e
        mp = os.path.join(DATA, "meta", f"{k}.json")
        r["_meta"] = jload(mp) if os.path.exists(mp) else None
        u = e.get("moment_uuid")
        if not u and r["_meta"]:
            u = {t["name"]: t["value"] for t in r["_meta"].get("attributes", [])}.get("Moment UUID")
        r["_off"] = offc.get(u)
    return rows


def summary(r):
    d = r["_meta"] or {}; a = {t["name"]: t["value"] for t in d.get("attributes", [])}
    off = r["_off"] or {}; oa = off.get("attributes") or {}; mo = oa.get("moment") or {}; g = oa.get("game") or {}
    pl = oa.get("primary_player") or {}; imgs = d.get("images") or {}; media = (d.get("assets") or {}).get("media") or []
    vid = next((m.get("uri") for m in media if m.get("purpose") == "primary-asset"), "") or next(
        (m.get("uri") for m in (off.get("assets") or {}).get("media") or [] if m.get("purpose") == "video"), "")
    front = imgs.get("front") or {}
    ln = r["_man"]
    return {
        "player": r["player"], "team": a.get("Team") or r["team"], "position": pl.get("position", ""),
        "jersey": pl.get("jersey", ""), "date": a.get("Date") or mo.get("date", ""), "play": a.get("Play") or mo.get("event", ""),
        "tagline": oa.get("collectible_tagline", ""), "period": mo.get("period", ""), "clock": mo.get("clock", ""),
        "final_score": g.get("final_score", ""), "venue": (g.get("venue") or {}).get("name", ""),
        "flags": ", ".join(k.replace("_", " ") for k, v in (mo.get("flags") or {}).items() if v),
        "set": a.get("Set") or r["set"], "list_set": r["set"], "series": a.get("Series") or (off.get("token_series") or {}).get("name", ""),
        "rarity": a.get("Rarity") or r["rarity"], "editions": int(a["Total Editions"]) if str(a.get("Total Editions", "")).isdigit() else (off.get("editions") or r["editions"] or ""),
        "description": re.sub(r"\n+Officially Licensed Product.*$", "", (d.get("description") or off.get("description") or "").strip(), flags=re.S),
        "issued": (d.get("issued") or off.get("issued") or "")[:10], "audio": a.get("Audio Type", ""),
        "lowest_ask": r["lowest_ask"], "fmv": r["fmv"],
        "cover_url": front.get("url", ""), "cover_ipfs": (front.get("altloc") or {}).get("ipfs", ""), "cover_sha256": front.get("sha256", ""),
        "video_url": vid, "breakaway_url": ln.get("source_url", "").replace("nft.nhlbreakaway.com/series", "nhlbreakaway.com/series"),
        "meta_url": ln.get("source_url", ""), "card_url": r["card_url"], "id": r["id"],
        "moment_uuid": ln.get("moment_uuid", ""), "raw_meta_path": ln.get("meta_path", ""),
        "offchain_path": ln.get("offchain_path", ""), "link_via": ln.get("link_via", ""),
        "source": " + ".join(x for x, ok in (("card list", True), ("nft. metadata", bool(r["_meta"])), ("Breakaway off-chain", bool(r["_off"]))) if ok),
        "missing": "" if r["_meta"] else ("no Breakaway token found" if not ln else f"metadata fetch failed ({ln.get('status')})"),
    }


def sort_rows(rows):
    for r in rows: r["_s"] = summary(r)
    rows.sort(key=lambda r: (r["_s"]["issued"] or "9999", r["_s"]["set"].lower(), r["_s"]["date"] or "", r["player"].lower(), r["id"]))
    for i, r in enumerate(rows, 1): r["_s"]["row"] = i
    return rows


def safe(s): return re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_")[:50]
def cover_path(r):
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        fp = os.path.join(OUT, "covers_full", f"{r['id']}{ext}")
        if os.path.exists(fp): return fp


COLS = [("row", "#"), ("cover", "Cover"), ("player", "Player"), ("team", "Team"), ("position", "Pos"), ("jersey", "Jersey"),
        ("date", "Highlight Date"), ("play", "Play"), ("tagline", "Highlight"), ("period", "Period"), ("clock", "Clock"),
        ("final_score", "Final Score"), ("venue", "Venue"), ("flags", "Flags"), ("set", "Set"), ("list_set", "Set (list label)"),
        ("series", "Series"), ("rarity", "Rarity"), ("editions", "Edition Size"), ("description", "Description"),
        ("issued", "Released"), ("audio", "Audio"), ("lowest_ask", "Lowest Ask"), ("fmv", "FMV"),
        ("cover_url", "Cover Art (full res)"), ("cover_ipfs", "Cover IPFS CID"), ("cover_sha256", "Cover sha256"),
        ("video_url", "Video"), ("breakaway_url", "NHL Breakaway Page"), ("meta_url", "Metadata URL"),
        ("card_url", "Card Page"), ("cover_file", "Cover File"), ("id", "Card ID"),
        ("moment_uuid", "Moment UUID"), ("raw_meta_path", "raw_meta_path"), ("offchain_path", "offchain_path"),
        ("link_via", "How Linked"), ("source", "Data Source"), ("missing", "Missing / Notes")]
LINKS = {"cover_url": "Cover art", "video_url": "Watch", "breakaway_url": "Breakaway", "meta_url": "JSON", "card_url": "Card page"}


def cmd_build(a):
    """Offline. Reads data/ (and output/covers_full/ for thumbnails if present)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image as XImg
    rows = sort_rows(load_model())
    try: from PIL import Image
    except ImportError: Image = None
    os.makedirs(OUT, exist_ok=True)
    wb = Workbook(); ws = wb.active; ws.title = "Highlights"
    hdr_font, hdr_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3A5F")
    link_font = Font(color="0563C1", underline="single")

    def header(sheet, names):
        sheet.append(names)
        for c in sheet[1]: c.font, c.fill = hdr_font, hdr_fill
    header(ws, [h for _, h in COLS]); ws.freeze_panes = "D2"
    keys = [k for k, _ in COLS]; cc = keys.index("cover") + 1
    widths = {i: len(h) + 2 for i, (_, h) in enumerate(COLS, 1)}
    tdir = os.path.join(CACHE, "thumbs"); os.makedirs(tdir, exist_ok=True)
    for r in rows:
        s = r["_s"]; cp = cover_path(r)
        s["cover_file"] = f"covers/{s['row']:04d}_{safe(r['player'])}_{safe(s['set'])}{os.path.splitext(cp)[1]}" if cp else ""
        ws.append([("" if k == "cover" else s.get(k, "")) for k in keys]); ri = ws.max_row
        for ci, k in enumerate(keys, 1):
            c = ws.cell(ri, ci); c.alignment = Alignment(vertical="center"); v = c.value
            if k in LINKS and v: c.hyperlink = v; c.value = v = LINKS[k]; c.font = link_font
            elif k == "cover_file" and v: c.hyperlink = v; c.font = link_font
            widths[ci] = min(max(widths[ci], len(str(v if v is not None else "")) + 2), 70 if k == "description" else 48)
        if cp and Image:
            tp = os.path.join(tdir, f"{r['id']}.png")
            if not os.path.exists(tp) or os.path.getmtime(tp) < os.path.getmtime(cp):
                im = Image.open(cp).convert("RGB"); im.thumbnail((72, 72)); im.save(tp, "PNG")
            xi = XImg(tp); xi.anchor = f"{get_column_letter(cc)}{ri}"; ws.add_image(xi); ws.row_dimensions[ri].height = 58
    widths[cc] = 11
    for ci, w in widths.items(): ws.column_dimensions[get_column_letter(ci)].width = max(w, 6)
    ws.auto_filter.ref = ws.dimensions
    # every field: on-chain (meta.*) + off-chain (offchain.*), flattened
    fl = []
    for r in rows:
        f = {"#": r["_s"]["row"], "id": r["id"], "raw_meta_path": r["_s"]["raw_meta_path"], "offchain_path": r["_s"]["offchain_path"]}
        if r["_meta"]: f.update({f"meta.{k}": v for k, v in flat(r["_meta"]).items()})
        if r["_off"]: f.update({f"offchain.{k}": v for k, v in flat(r["_off"]).items()})
        fl.append(f)
    cols = list(dict.fromkeys(k for f in fl for k in f))
    fs = wb.create_sheet("All Metadata"); header(fs, cols); fs.freeze_panes = "C2"
    for f in fl:
        fs.append([(json.dumps(v) if isinstance(v, (dict, list)) else (str(v)[:32000] if isinstance(v, str) else v)) for v in (f.get(c, "") for c in cols)])
    for i, c in enumerate(cols, 1): fs.column_dimensions[get_column_letter(i)].width = min(max(len(c), 10) + 2, 40)
    # IPFS sheet: every CID + sha256
    ip = wb.create_sheet("IPFS"); header(ip, ["#", "id", "field", "ipfs", "sha256", "url"])
    for r in rows:
        for e in (r["_man"].get("ipfs") or []): ip.append([r["_s"]["row"], r["id"], e["path"], e["ipfs"], e["sha256"], e["url"]])
    for col, w in zip("ABCDEF", (6, 8, 40, 56, 48, 80)): ip.column_dimensions[col].width = w
    bs = wb.create_sheet("By Set"); header(bs, ["Set (list label)", "Highlights", "With Breakaway metadata"])
    agg = {}
    for r in rows: x = agg.setdefault(r["set"], [0, 0]); x[0] += 1; x[1] += 1 if r["_meta"] else 0
    for k in sorted(agg): bs.append([k, *agg[k]])
    bs.column_dimensions["A"].width = 48; bs.column_dimensions["C"].width = 24
    wb.save(os.path.join(OUT, "highlights.xlsx"))
    jdump([{k: v for k, v in r["_s"].items()} for r in rows], os.path.join(OUT, "highlights_summary.json"))
    n = sum(1 for r in rows if r["_meta"]); o = sum(1 for r in rows if r["_off"])
    p(f"Built output/highlights.xlsx: {len(rows)} rows, {n} with nft. metadata, {o} with off-chain data, "
      f"{sum(1 for r in rows if cover_path(r))} with cover thumbnails, {len(cols)} flattened fields")
    return rows


# ------------------------------------------------------------------ covers
def cmd_covers(a):
    rows = load_model(); cd = os.path.join(OUT, "covers_full"); os.makedirs(cd, exist_ok=True)
    stats = {"ok": 0, "cached": 0, "fail": 0, "sha_mismatch": 0}; lock = threading.Lock()
    def one(r):
        d = r["_meta"] or {}; front = (d.get("images") or {}).get("front") or {}; url = front.get("url")
        if not url: return
        ext = os.path.splitext(url.split("?")[0])[1] or ".png"; fp = os.path.join(cd, f"{r['id']}{ext}")
        if os.path.exists(fp): 
            with lock: stats["cached"] += 1
            return
        st, b, _ = http(url, timeout=120)
        with lock:
            if not b: stats["fail"] += 1; return
            if front.get("sha256") and b64sha(b).rstrip("=") != front["sha256"].rstrip("="): stats["sha_mismatch"] += 1
            wbytes(fp, b); stats["ok"] += 1
    with cf.ThreadPoolExecutor(THR.sem._value) as ex:
        for n, _ in enumerate(ex.map(one, rows), 1):
            if n % 250 == 0: p(f"  covers {n}/{len(rows)}")
    size = sum(os.path.getsize(os.path.join(cd, f)) for f in os.listdir(cd))
    p(f"Covers: {stats}; output/covers_full = {size/1e6:.0f} MB")


# ------------------------------------------------------------------ package for sharing
FRIEND_README = """NHL BREAKAWAY HIGHLIGHTS
Generated {when}. {n} highlights; {m} with full NHL Breakaway details, {c} with cover art.

FILES
  highlights.xlsx   Sheet "Highlights": one row per highlight with a small cover thumbnail (column B).
                    Sheet "All Metadata": every field NHL Breakaway publishes for each highlight.
                    Sheet "IPFS": IPFS copies (CID + sha256) of every image/video, in case the site goes away.
                    Sheet "By Set": highlight count per set.
  covers/           Full-resolution cover art named <row #>_<player>_<set>, matching the "#" column.
  breakaway.py      The script that made all this (optional; see below).

KEY COLUMNS
  # / Cover / Player / Team / Pos / Jersey     who and the cover art
  Highlight Date / Play / Highlight / Period / Clock / Final Score / Venue / Flags   what happened
  Set / Series / Rarity / Edition Size / Released   collectible details (official NHL Breakaway values;
                    "Set (list label)" is the set label used in the card list)
  Description       The official write-up, good for album captions
  Lowest Ask / FMV  Price snapshot from the card list (USD)
  Cover Art, Video, NHL Breakaway Page, Metadata URL, Card Page   clickable links
  Cover IPFS CID / Cover sha256   permanent IPFS address and checksum of the cover image
  Cover File        matching image in covers/
  Data Source / Missing / Notes   where the row's data came from, or why something is missing

RE-RUNNING OR DOWNLOADING VIDEOS (optional)
  1. Install Python 3 from https://www.python.org/downloads/ (tick "Add Python to PATH" on Windows).
  2. In this folder open a terminal and run:   pip install -r requirements.txt
     (or: pip install openpyxl pillow)
  3. Rebuild everything:                       python breakaway.py all
  4. Videos are OFF by default. To save them:  python breakaway.py videos --out-dir videos
     It shows the estimated total size and asks y/n first. Try --limit 5 for a small test,
     --series "Series 3" or --ids 12,40 to pick some. Re-running resumes and skips finished files.
"""


def cmd_package(a):
    rows = sort_rows(load_model())
    cov = os.path.join(OUT, "covers"); os.makedirs(cov, exist_ok=True)
    for fn in os.listdir(cov): os.remove(os.path.join(cov, fn))
    names = []
    for r in rows:
        cp = cover_path(r)
        if cp:
            fn = f"{r['_s']['row']:04d}_{safe(r['player'])}_{safe(r['_s']['set'])}{os.path.splitext(cp)[1]}"
            os.link(cp, os.path.join(cov, fn)); names.append(fn)
    with zipfile.ZipFile(os.path.join(OUT, "covers.zip"), "w", zipfile.ZIP_STORED) as z:
        for fn in names: z.write(os.path.join(cov, fn), f"covers/{fn}")
    readme = FRIEND_README.format(when=time.strftime("%Y-%m-%d"), n=len(rows), m=sum(1 for r in rows if r["_meta"]), c=len(names))
    open(os.path.join(OUT, "README.txt"), "w").write(readme)
    zp = os.path.join(ROOT, "Breakaway-Highlights.zip")
    with zipfile.ZipFile(zp, "w") as z:
        D = zipfile.ZIP_DEFLATED
        z.write(os.path.join(OUT, "highlights.xlsx"), "Breakaway-Highlights/highlights.xlsx", D)
        z.writestr("Breakaway-Highlights/README.txt", readme, D)
        z.write(os.path.abspath(__file__), "Breakaway-Highlights/breakaway.py", D)
        z.write(os.path.join(ROOT, "requirements.txt"), "Breakaway-Highlights/requirements.txt", D)
        for fn in names: z.write(os.path.join(cov, fn), f"Breakaway-Highlights/covers/{fn}", zipfile.ZIP_STORED)
    p(f"Packaged {zp} ({os.path.getsize(zp)/1e6:.0f} MB, {len(names)} covers)")


# ------------------------------------------------------------------ videos (opt-in)
def video_size(url):
    """Size from a 1-byte ranged GET (Content-Range total); falls back to HEAD."""
    st, _, h = http(url, timeout=30, headers={"Range": "bytes=0-0"})
    m = re.search(r"/(\d+)$", (h or {}).get("Content-Range", "") or "")
    if m: return int(m.group(1))
    st, _, h = http(url, method="HEAD", timeout=30)
    return int(h["Content-Length"]) if h and h.get("Content-Length") else None


def cmd_videos(a):
    rows = sort_rows(load_model())
    if a.series: rows = [r for r in rows if r["_s"]["series"].lower() == a.series.lower()]
    if a.ids: want = {int(x) for x in a.ids.split(",") if x.strip()}; rows = [r for r in rows if r["id"] in want]
    rows = [r for r in rows if r["_s"]["video_url"]]
    if a.limit: rows = rows[: a.limit]
    out = os.path.abspath(a.out_dir); os.makedirs(out, exist_ok=True)
    def fname(r): return os.path.join(out, f"{r['_s']['row']:04d}_{safe(r['player'])}_{safe(r['_s']['set'])}.mp4")
    todo = [r for r in rows if not os.path.exists(fname(r))]
    p(f"{len(rows)} videos selected, {len(rows) - len(todo)} already saved, {len(todo)} to download into {out}")
    if not todo: return
    sample = todo if len(todo) <= 30 else todo[:: max(1, len(todo) // 30)][:30]
    sizes = []
    for r in sample:
        n = video_size(r["_s"]["video_url"])
        if n: sizes.append(n)
    est = (sum(sizes) / len(sizes) * len(todo)) if sizes else None
    p(f"Estimated total: {est/1e9:.2f} GB (avg {sum(sizes)/len(sizes)/1e6:.1f} MB from {len(sizes)} size checks)" if est else "Could not estimate size.")
    if not a.yes and input("Download now? [y/N] ").strip().lower() not in ("y", "yes"): p("Cancelled."); return
    def one(r):
        dst = fname(r); part = dst + ".part"; have = os.path.getsize(part) if os.path.exists(part) else 0
        for i in range(6):
            THR.sem.acquire(); time.sleep(THR.delay)
            try:
                hdr = {**HDR, **({"Range": f"bytes={have}-"} if have else {})}
                with urllib.request.urlopen(urllib.request.Request(r["_s"]["video_url"], headers=hdr), timeout=120) as resp:
                    mode = "ab" if have and resp.status == 206 else "wb"
                    with open(part, mode) as f:
                        while True:
                            ch = resp.read(1 << 20)
                            if not ch: break
                            f.write(ch)
                os.replace(part, dst); THR.ok(); return True
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 404): p(f"  skip {r['id']}: HTTP {e.code}"); return False
                THR.bad(); time.sleep(min(60, 2 ** (i + 1)))
            except Exception:
                THR.bad(); time.sleep(min(60, 2 ** (i + 1)))
                have = os.path.getsize(part) if os.path.exists(part) else 0
            finally: THR.sem.release()
        return False
    with cf.ThreadPoolExecutor(THR.sem._value) as ex:
        ok = sum(1 for x in ex.map(one, todo) if x)
    p(f"Videos: {ok}/{len(todo)} downloaded to {out}")


def main():
    global THR
    ap = argparse.ArgumentParser(description="breakaway-data: NHL Breakaway highlight archive")
    ap.add_argument("command", choices=["all", "fetch", "covers", "build", "package", "videos"])
    ap.add_argument("--concurrency", type=int, default=6, help="parallel requests to NHL Breakaway / CDN (1-8, default 6)")
    ap.add_argument("--refresh", action="store_true", help="re-fetch the master list and all metadata")
    ap.add_argument("--no-crawl", action="store_true", help="never fetch card pages")
    ap.add_argument("--out-dir", default=os.path.join(OUT, "videos"), help="videos: where to save")
    ap.add_argument("--limit", type=int, help="videos: at most N")
    ap.add_argument("--series", help='videos: only this series, e.g. "Series 3"')
    ap.add_argument("--ids", help="videos: comma-separated Card IDs")
    ap.add_argument("--yes", action="store_true", help="videos: don't ask before downloading")
    a = ap.parse_args(); THR = Throttle(max(1, min(a.concurrency, 8)))
    if a.command in ("fetch", "all"): cmd_fetch(a)
    if a.command in ("covers", "all"): cmd_covers(a)
    if a.command in ("build", "all"): cmd_build(a)
    if a.command in ("package", "all"): cmd_package(a)
    if a.command == "videos": cmd_videos(a)


if __name__ == "__main__":
    main()

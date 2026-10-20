#!/usr/bin/env python3
"""
breakaway-data: a preservation archive of NHL Breakaway highlight metadata.

USAGE
  python breakaway.py                     # no arguments: simple numbered menu (also what the standalone app shows)
  python breakaway.py all                 # fetch (only new/missing) -> covers -> build -> package
  python breakaway.py fetch [--refresh] [--ids 12,40] [--discover]
                                          # highlight->token links + raw nft. metadata for the card list
  python breakaway.py covers [--repair]   # full-res cover art into output/covers_full/ (IPFS first, sha256-checked)
  python breakaway.py build               # OFFLINE: rebuild output/highlights.xlsx from data/ only
  python breakaway.py package             # output/covers/, covers.zip, Breakaway-Highlights.zip
  python breakaway.py videos [--video-dir DIR] [--limit N] [--player/--team/--set/--series ..] [--ids ..] [--yes] [--repair]
                                          # OPT-IN video download, IPFS originals first (asks y/n after a size estimate)
  python breakaway.py verify              # re-hash data/meta, covers and videos: original / reencoded / unverified
  python breakaway.py add <url|seriesId/tokenId> ...   # add moments (also reads data/extra_moments.txt)
  python breakaway.py album [--layout 1up|2x2|3x3] [--page letter|a4] [--set ..] [--series ..] [--player ..]
                            [--team ..] [--bleed] [--out file.pdf] [--max-px N --jpeg Q]   # printable PDF album
  python breakaway.py view                # offline viewer/index.html (search, filters, details, video)
  python breakaway.py check-ipfs [--sample N | --full]   # which IPFS CIDs still answer -> data/ipfs_status.json
  python breakaway.py pin [--kubo | --service pinata|filebase|URL] [--types video,cover]   # help keep files alive
  IPFS: --gateway URL (repeatable) adds gateways tried first; --ipfs-only never uses the Breakaway CDN;
        --offline never touches the network. Settings: breakaway.config.json (see breakaway.config.example.json).

SOURCES (all public, no login)
  card list     data/highlights.json (committed), plus moments added with `add` / data/extra_moments.txt,
                plus (with `fetch --discover`) moments NHL Breakaway's own set listings show that aren't in it yet
  links         NHL Breakaway set listings (apigw.sweet.io/catalog/search/moment/set/<set>), matched on
                set + player + series; existing links in data/links.json are kept as they are
  on-chain-ish  https://nft.nhlbreakaway.com/series/<series>/<token>  saved byte-for-byte to data/meta/<id>.json
  off-chain     raw set listings + set completion + quest data in data/offchain/
  covers/video  IPFS gateways first (the originals), then the nft.nhlbreakaway.com / mediagateway.sweet.io CDN,
                which now serves re-encoded videos (output/, gitignored; output/download_log.json says which)

IDS
  "id" in data/highlights.json is the card id from the original card list (1..1818, not contiguous). Moments
  added later (`add`, `fetch --discover`) get the next free numbers and "on_site": false.
"""
import argparse, base64, concurrent.futures as cf, csv, datetime as dt, hashlib, html, io, json, os, re
import shutil, sys, threading, time, unicodedata, urllib.error, urllib.parse, urllib.request, zipfile

FROZEN = getattr(sys, "frozen", False)          # running as the standalone app (PyInstaller)
ROOT = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))


def _app_root():
    """Standalone app: use the data/ folder next to the app if there is one (so it can be updated);
    otherwise unpack the copy bundled inside the app next to it (or into ~/Breakaway-Archive if that folder is read-only)."""
    if not FROZEN or os.path.isdir(os.path.join(ROOT, "data")): return ROOT
    home = os.path.join(os.path.expanduser("~"), "Breakaway-Archive")
    if os.path.isdir(os.path.join(home, "data")) and not os.access(ROOT, os.W_OK): return home
    bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "data.zip")
    if not os.path.exists(bundled): return ROOT
    for base in (ROOT, os.path.join(os.path.expanduser("~"), "Breakaway-Archive")):
        try:
            os.makedirs(base, exist_ok=True); print(f"First run: unpacking the archive data into {base}/data ...", flush=True)
            with zipfile.ZipFile(bundled) as z: z.extractall(base)
            return base
        except OSError: continue
    return ROOT


ROOT = _app_root()
DATA, OUT, CACHE = (os.path.join(ROOT, d) for d in ("data", "output", "cache"))
NFT = "https://nft.nhlbreakaway.com/series"
APIGW = "https://apigw.sweet.io"
UA = "Mozilla/5.0 (breakaway-data preservation export; polite, cached)"
HDR = {"User-Agent": UA}   # plain public requests: no cookies, logins, tokens or spoofed Referer/Origin headers
VERSION = "1.1.3"       # the one place the version lives: menu header, --version, viewer footer
TAGLINE = "Made for the community, by the community. Fork it, build on it, do whatever you like with it."
WARRANTY = "Unofficial fan tool, provided AS IS with no warranty. Use at your own risk. See LICENSE."
ISSUES_URL = "https://github.com/breakaway-vault/breakaway-data/issues"   # override with "issues_url" in breakaway.config.json
OFFLINE = False          # --offline: never touch the network (build/view/album from local files only)
MEDIA_CONC = 2           # parallel media downloads per run (each host is also throttled separately)


_PROG = None                  # the live progress line currently on screen, if any
_PLOCK = threading.RLock()
STOP = threading.Event()      # set by Ctrl+C: downloads stop at their next chunk and the run ends cleanly
_TL = threading.local()       # worker threads keep their own run's stop flag here (see run_pool)


def stopping():
    """True once Ctrl+C was pressed for the run this thread belongs to."""
    ev = getattr(_TL, "stop", None)
    return (ev or STOP).is_set()


def stop_wait(seconds):
    """Sleep, but wake up at once (returning True) when Ctrl+C was pressed."""
    ev = getattr(_TL, "stop", None)
    return (ev or STOP).wait(max(0.0, seconds))


def p(*a):
    """print(), but first clear a live progress line and redraw it afterwards so messages never get mixed into it."""
    with _PLOCK:
        pr = _PROG
        if pr: pr.clear()
        print(*a, flush=True)
        if pr: pr.draw(force=True)


def _is_tty():
    try: return bool(sys.stdout) and sys.stdout.isatty()
    except Exception: return False


def _mb(n): return f"{n / 1e6:.1f} MB" if n < 1e7 else (f"{n / 1e6:,.0f} MB" if n < 1e10 else f"{n / 1e9:,.1f} GB")


def _dur(s):
    s = int(max(0, s))
    if s < 60: return f"{s} s"
    if s < 3600: return f"{s // 60} min"
    return f"{s // 3600} h {s % 3600 // 60:02d} min"


class Progress:
    """One status line for a long loop: done/total, percent, ok/skipped/failed, MB, rough time left.
    On a terminal (Windows console, Mac Terminal, Linux) it is redrawn in place with \r, at most ~4 times a second.
    Otherwise (a log file or pipe) a plain line is printed every `every` items or ~10 s. Ends with a summary."""
    def __init__(self, label, total, folder=None, ok="ok", failed="failed", skipped="skipped",
                 show_bytes=False, expect_bytes=None, resumable=True, every=None):
        self.label, self.total, self.folder = label, total, folder
        self.names = {"ok": ok, "failed": failed, "skipped": skipped}
        self.n = {"ok": 0, "failed": 0, "skipped": 0}; self.bytes = 0
        self.show_bytes, self.expect, self.resumable = show_bytes, expect_bytes, resumable
        self.tty = _is_tty(); self.every = every or max(10, total // 20)
        self.t0 = self.last = time.time(); self.last_n = 0; self.width = 0; self.lock = threading.Lock()

    def __enter__(self):
        global _PROG
        STOP.clear()
        with _PLOCK: _PROG = self
        self.draw(force=True); return self

    def __exit__(self, et, ev, tb):
        global _PROG
        with _PLOCK: self.clear(); self._shown = None; _PROG = None
        if et is not None and issubclass(et, SystemExit): return False   # its own message explains what happened
        self.summary(stopped=et is not None and issubclass(et, KeyboardInterrupt) or STOP.is_set())
        return False

    @property
    def done(self): return sum(self.n.values())

    def add(self, what="ok", nbytes=0):
        with self.lock: self.n[what] += 1; self.bytes += nbytes
        self.draw()

    def add_bytes(self, nbytes):
        with self.lock: self.bytes += nbytes
        self.draw()

    def text(self):
        d, t = self.done, self.total; el = time.time() - self.t0; worked = self.n["ok"] + self.n["failed"]
        s = f"{self.label}: {d:,} / {t:,}" + (f" ({d * 100 // t}%)" if t else "")
        s += f"  {self.names['ok']} {self.n['ok']:,}"
        if self.n["skipped"] or self.names["skipped"] == "skipped": s += f"  {self.names['skipped']} {self.n['skipped']:,}"
        s += f"  {self.names['failed']} {self.n['failed']:,}"
        if self.show_bytes: s += f"  {_mb(self.bytes)}"
        left = None
        if el > 3 and d < t:
            if self.expect and self.bytes > 1e6: left = el / self.bytes * max(0, self.expect - self.bytes)
            elif worked: left = el / worked * (t - d)
        if left is not None: s += f"  ~{_dur(left)} left"
        return s

    def clear(self):
        self._shown = None
        if self.tty and self.width:
            sys.stdout.write("\r" + " " * self.width + "\r"); sys.stdout.flush(); self.width = 0

    def draw(self, force=False):
        nowt = time.time()
        with _PLOCK:
            if _PROG is not self: return
            if self.tty:
                if not force and nowt - self.last < 0.25: return
                self.last = nowt
                cols = shutil.get_terminal_size((100, 24)).columns
                s = self.text()[: max(20, cols - 1)]          # never wrap: a wrapped line can't be redrawn with \r
                if s == getattr(self, "_shown", None) and self.width: return
                self._shown = s
                sys.stdout.write("\r" + s + " " * max(0, self.width - len(s))); sys.stdout.flush(); self.width = len(s)
            elif not force and (self.done - self.last_n >= self.every or nowt - self.last >= 10):
                self.last, self.last_n = nowt, self.done
                print("  " + self.text(), flush=True)

    def summary(self, stopped=False):
        el = time.time() - self.t0
        if stopped:
            head = f"{self.label}: stopped at {self.done:,} / {self.total:,}." + (" Run the same command again to resume." if self.resumable else "")
        else: head = f"{self.label}: finished {self.done:,} / {self.total:,}."
        parts = [f"{self.names['ok']} {self.n['ok']:,}"]
        if self.n["skipped"] or self.names["skipped"] == "skipped": parts.append(f"{self.names['skipped']} (already had) {self.n['skipped']:,}")
        parts.append(f"{self.names['failed']} {self.n['failed']:,}")
        if self.show_bytes: parts.append(f"{_mb(self.bytes)} downloaded")
        parts.append(f"took {_dur(el)}")
        p(head + " " + ", ".join(parts) + (f". Folder: {self.folder}" if self.folder else ""))


def run_pool(fn, items, workers, prog=None):
    """fn(item) on a few daemon worker threads while the main thread stays free to notice Ctrl+C (on Windows
    a thread blocked in a plain join or result() can't be interrupted, which is why Ctrl+C used to be ignored).
    Ctrl+C: this run's stop flag is set, queued items are dropped, files in flight stop at their next chunk
    (their .part file is discarded; finished files are kept), we wait a few seconds at most, then
    KeyboardInterrupt goes up to the caller (the menu catches it and shows the menu again)."""
    import queue
    items = list(items)
    if not items: return
    q = queue.Queue(); ev = threading.Event()
    for x in items: q.put(x)
    def worker():
        _TL.stop = ev
        while not ev.is_set():
            try: x = q.get_nowait()
            except queue.Empty: return
            try: fn(x)
            except Exception as e: p(f"  error: {type(e).__name__}: {e}")
    ts = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, min(workers, len(items))))]
    for th in ts: th.start()
    try:
        while any(th.is_alive() for th in ts):
            for th in ts: th.join(0.2)      # short timed joins: Ctrl+C is handled within a fraction of a second
            if prog: prog.draw()
    except KeyboardInterrupt:
        ev.set(); STOP.set(); p("Stopping: dropping the rest and closing the files in progress...")
        end = time.time() + 2
        try:
            for th in ts: th.join(max(0.0, end - time.time()))
        except KeyboardInterrupt: pass      # a second Ctrl+C: don't wait at all
        raise


def idkey(x):
    x = str(x[0] if isinstance(x, tuple) else x)
    return (0, int(x), "") if x.isdigit() else (1, 0, x)
def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def jload(path, default=None):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default
def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
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
    if OFFLINE: return None, None, None
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
            time.sleep(min(300, float(ra)) if ra and ra.isdigit() else min(60, 2 ** (i + 1)))
        except Exception:
            thr.bad(); time.sleep(min(60, 2 ** (i + 1)))
        finally:
            thr.sem.release()
    return None, None, None


def norm(s):
    s = unicodedata.normalize("NFKD", html.unescape(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)
def strip(s): return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


# ------------------------------------------------------------------ card list
def load_cards():
    """The card list is data/highlights.json (it ships with the repo). New moments come from `add`,
    data/extra_moments.txt or `fetch --discover`; nothing is scraped from any third-party site."""
    rows = jload(os.path.join(DATA, "highlights.json"))
    if not rows: sys.exit("data/highlights.json is missing or empty. Restore it from the repo, then re-run.")
    rows.sort(key=lambda r: idkey(r["id"]))
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


def build_links(rows, moments):
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
    if todo:
        p(f"{len(todo)} highlight(s) could not be matched to an NHL Breakaway set listing: "
          f"{', '.join(map(str, todo[:10]))}{' ...' if len(todo) > 10 else ''}. "
          "Add them by URL with `python breakaway.py add <nhlbreakaway.com URL>`.")
    jdump(dict(sorted(links.items(), key=idkey)), path)
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


def get_nft(sid, tok, exact=False):
    """GET nft.nhlbreakaway.com metadata. Edition #1 of a moment can be missing (never minted / burned);
    unless the token is exact, try the next few serials of the same moment (one request each)."""
    tok = int(tok); tries = [tok] if exact or tok & 0xFFFFFFFFFFFF else [tok + n for n in range(4)]
    st = b = h = None
    for t in tries:
        st, b, h = http(f"{NFT}/{sid}/{t}")
        if b or st != 404: return st, b, h, str(t)
    return st, b, h, str(tries[-1])


def fetch_meta(links, refresh, only=None):
    mdir = os.path.join(DATA, "meta"); mpath = os.path.join(DATA, "manifest.json")
    man = jload(mpath, {}); lock = threading.Lock()
    def one(k):
        ln = links[k]; url = f"{NFT}/{ln['series_id']}/{ln['token_id']}"; fp = os.path.join(mdir, f"{k}.json")
        e = man.get(k, {})
        if not refresh and os.path.exists(fp) and e.get("status") == 200 and e.get("source_url") == url:
            return
        st, b, h, tok = get_nft(ln["series_id"], ln["token_id"], ln.get("exact"))
        if b and tok != str(ln["token_id"]):  # edition #1 missing: keep the exact token that answered
            with lock: links[k] = ln = {**ln, "token_id": tok, "exact": True,
                                        "via": f"{ln.get('via', '')} (edition #1 token missing; serial {int(tok) & 0xFFFF} used)".strip()}
            url = f"{NFT}/{ln['series_id']}/{tok}"
        e = {"id": int(k) if k.isdigit() else k, "source_url": url, "fetched_at": now(), "status": st, "link_via": ln.get("via")}
        if b:
            wbytes(fp, b)
            e.update({"meta_path": f"data/meta/{k}.json", "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                      "content_type": h.get("Content-Type") if h else None})
            try: e["ipfs"] = ipfs_entries(json.loads(b))
            except Exception: e["parse_error"] = True
        with lock: man[k] = e
    keys = sorted((k for k in links if only is None or k in only), key=idkey)
    with cf.ThreadPoolExecutor(THR.sem._value) as ex:
        for n, _ in enumerate(ex.map(one, keys), 1):
            if n % 250 == 0: p(f"  metadata {n}/{len(keys)}")
    for _ in range(2):  # retry failures, slower
        bad = [k for k in keys if man.get(k, {}).get("status") != 200]
        if not bad: break
        p(f"  retrying {len(bad)} failed metadata fetches"); time.sleep(10)
        for k in bad: one(k)
    jdump(dict(sorted(man.items(), key=idkey)), mpath)
    jdump(dict(sorted(links.items(), key=idkey)), os.path.join(DATA, "links.json"))
    return man


def discover_refs(rows, moments, man):
    """Moments in NHL Breakaway's public set listings that aren't in the card list yet -> (series, token)."""
    known = {e.get("moment_uuid") for e in man.values()} | {v.get("moment_uuid") for v in jload(os.path.join(DATA, "links.json"), {}).values()}
    out = []
    for m in moments:
        if m["uuid"] in known or not m["series_id"]: continue
        out.append((m["series_id"], str(int(m["uuid"][16:20], 16) << 48))); known.add(m["uuid"])
    return out


def cmd_fetch(a):
    rows = load_cards()
    only = {x.strip() for x in a.ids.split(",") if x.strip()} if a.ids else None
    if only:
        unknown = only - {str(r["id"]) for r in rows}
        if unknown: sys.exit(f"Not in data/highlights.json: {', '.join(sorted(unknown))}")
    moments = fetch_offchain(a.refresh and not only)
    links = build_links(rows, moments)
    man = fetch_meta(links, a.refresh, only)
    if a.discover:
        refs = discover_refs(rows, moments, man)
        p(f"Discover: {len(refs)} moment(s) in NHL Breakaway set listings aren't in the card list yet")
        if a.limit: refs = refs[:a.limit]
        if refs: add_refs(refs, "found in NHL Breakaway set listing (fetch --discover)")
        rows = load_cards(); man = jload(os.path.join(DATA, "manifest.json"), {}); links = jload(os.path.join(DATA, "links.json"), {})
    # attach off-chain moment pointer to manifest
    by_uuid = {m["uuid"]: m for m in moments}
    for k, e in man.items():
        try:
            u = {t["name"]: t["value"] for t in jload(os.path.join(DATA, "meta", f"{k}.json")).get("attributes", [])}.get("Moment UUID")
        except Exception: u = None
        if u: e["moment_uuid"] = u
        if u in by_uuid: e["offchain_path"] = by_uuid[u]["file"]
    jdump(dict(sorted(man.items(), key=idkey)), os.path.join(DATA, "manifest.json"))
    write_cids(man)
    ok = sum(1 for e in man.values() if e.get("status") == 200)
    size = sum(os.path.getsize(os.path.join(DATA, "meta", f)) for f in os.listdir(os.path.join(DATA, "meta")))
    off = sum(1 for e in man.values() if e.get("offchain_path"))
    p(f"Fetch done: {len(rows)} highlights, {len(links)} linked, {ok} metadata OK, "
      f"{len(man) - ok} failed, {off} with off-chain data; data/meta = {size/1e6:.1f} MB"
      + (f" (refreshed ids: {', '.join(sorted(only, key=idkey))})" if only else ""))


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
        "description": re.sub(r"\n+Officially Licensed Product.*$", "", (d.get("description") or off.get("description") or "").strip(), flags=re.S).strip(),
        "issued": (d.get("issued") or off.get("issued") or "")[:10], "audio": a.get("Audio Type", ""),
        "lowest_ask": r.get("lowest_ask", ""), "fmv": r.get("fmv", ""),
        "cover_url": front.get("url", ""), "cover_ipfs": (front.get("altloc") or {}).get("ipfs", ""), "cover_sha256": front.get("sha256", ""),
        "video_url": vid, "breakaway_url": ln.get("source_url", "").replace("nft.nhlbreakaway.com/series", "nhlbreakaway.com/series"),
        "meta_url": ln.get("source_url", ""), "id": r["id"], "on_site": "yes" if r.get("on_site", True) else "no",
        "site_url": r.get("site_url", ""), "status": r.get("status", "unverified"), "status_basis": r.get("status_basis", ""),
        "ipfs_health": r.get("ipfs_health", ""), "ipfs_missing": ", ".join(r.get("ipfs_missing") or []),
        "listed_now": "" if "listed_now" not in r else ("yes" if r["listed_now"] else "no"),
        "my_editions": my_editions(r),
        "video_ipfs": asset_ipfs(d, "primary-asset")[0] or "", "video_sha256": asset_ipfs(d, "primary-asset")[1] or "",
        "card_image_ipfs": asset_ipfs(d, "card-image")[0] or "",
        "moment_uuid": ln.get("moment_uuid", ""), "raw_meta_path": ln.get("meta_path", ""),
        "offchain_path": ln.get("offchain_path", ""), "link_via": ln.get("link_via", ""),
        "source": " + ".join(x for x, ok in (("card list", True), ("nft. metadata", bool(r["_meta"])), ("Breakaway off-chain", bool(r["_off"]))) if ok),
        "missing": "" if r["_meta"] else ("no Breakaway token found" if not ln else f"metadata fetch failed ({ln.get('status')})"),
    }


def sort_rows(rows):
    for r in rows: r["_s"] = summary(r)
    rows.sort(key=lambda r: (r["_s"]["issued"] or "9999", r["_s"]["set"].lower(), r["_s"]["date"] or "", r["player"].lower(), idkey(r["id"])))
    for i, r in enumerate(rows, 1): r["_s"]["row"] = i
    return rows


def safe(s): return re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_")[:50]
def cover_path(r):
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        fp = os.path.join(OUT, "covers_full", f"{r['id']}{ext}")
        if os.path.exists(fp): return fp


COLS = [("row", "#"), ("cover", "Cover"), ("my_editions", "My Editions"), ("player", "Player"), ("team", "Team"), ("position", "Pos"), ("jersey", "Jersey"),
        ("date", "Highlight Date"), ("play", "Play"), ("tagline", "Highlight"), ("period", "Period"), ("clock", "Clock"),
        ("final_score", "Final Score"), ("venue", "Venue"), ("flags", "Flags"), ("set", "Set"), ("list_set", "Set (list label)"),
        ("series", "Series"), ("rarity", "Rarity"), ("editions", "Edition Size"), ("status", "Status"), ("status_basis", "Status Basis"), ("ipfs_health", "IPFS Health"),
        ("ipfs_missing", "Missing on IPFS"), ("listed_now", "Listed Now"), ("description", "Description"),
        ("issued", "Released"), ("audio", "Audio"), ("lowest_ask", "Lowest Ask"), ("fmv", "FMV"),
        ("cover_url", "Cover Art (full res)"), ("cover_ipfs", "Cover IPFS CID"), ("cover_sha256", "Cover sha256"),
        ("video_url", "Video"), ("video_ipfs", "Video IPFS CID"), ("video_sha256", "Video sha256"),
        ("card_image_ipfs", "Card Image IPFS CID"), ("breakaway_url", "NHL Breakaway Page"), ("meta_url", "Metadata URL"),
        ("cover_file", "Cover File"), ("id", "Card ID"), ("on_site", "In Original List"), ("site_url", "Card List Page"),
        ("moment_uuid", "Moment UUID"), ("raw_meta_path", "raw_meta_path"), ("offchain_path", "offchain_path"),
        ("link_via", "How Linked"), ("source", "Data Source"), ("missing", "Missing / Notes")]
LINKS = {"cover_url": "Cover art", "video_url": "Watch", "breakaway_url": "Breakaway", "meta_url": "JSON", "site_url": "The Fifth Line"}


def cmd_build(a):
    """Offline. Reads data/ (and output/covers_full/ for thumbnails if present)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image as XImg
    rows = mine_only(sort_rows(load_model()))
    xlsx = "my_cards.xlsx" if MINE is not None else "highlights.xlsx"
    COLS = [c for c in globals()["COLS"] if c[0] != "my_editions" or MINE is not None]
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
    wb.save(os.path.join(OUT, xlsx))
    if MINE is None: jdump([{k: v for k, v in r["_s"].items()} for r in rows], os.path.join(OUT, "highlights_summary.json"))
    n = sum(1 for r in rows if r["_meta"]); o = sum(1 for r in rows if r["_off"])
    p(f"Built {os.path.relpath(os.path.join(OUT, xlsx), ROOT)}: {len(rows)} rows, {n} with nft. metadata, {o} with off-chain data, "
      f"{sum(1 for r in rows if cover_path(r))} with cover thumbnails, {len(cols)} flattened fields")
    return rows


# ------------------------------------------------------------------ media: IPFS-first, sha256-verified
# Sweet's mediagateway now serves RE-ENCODED videos whose bytes no longer match the sha256 in the metadata.
# The IPFS CIDs in the metadata point at the ORIGINAL files, so media is fetched from IPFS gateways first
# and every file is checked against the metadata sha256. The NHL Breakaway CDN is only a last resort, and
# anything taken from it that doesn't match is kept but logged as "reencoded".
DEFAULT_GATEWAYS = ["https://ipfs.filebase.io/ipfs/", "https://gateway.pinata.cloud/ipfs/", "https://ipfs.io/ipfs/",
                    "https://dweb.link/ipfs/", "https://w3s.link/ipfs/", "https://4everland.io/ipfs/"]
GATEWAYS = list(DEFAULT_GATEWAYS)
IPFS_ONLY = False
CDN_FIRST = False
COOLDOWN = {}            # host -> unix time before which we don't ask it again (after a 429)
HOST_THR = {}
_HLOCK = threading.Lock()


def host_of(u): return urllib.parse.urlsplit(u).netloc


def host_thr(u, n=2, base=0.4):
    """One polite throttle per host, shared by every thread."""
    with _HLOCK:
        return HOST_THR.setdefault(host_of(u), Throttle(n, base))


def cool(u, retry_after=None):
    try: s = float(retry_after)
    except (TypeError, ValueError): s = 60.0
    with _HLOCK: COOLDOWN[host_of(u)] = time.time() + min(max(s, 30.0), 900.0)


def cooled(u):
    return COOLDOWN.get(host_of(u), 0) > time.time()


CID_RE = re.compile(r"^[A-Za-z0-9]+(?:/\S*)?")


def clean_cid(c):
    """'ipfs://Qm.../a.png  sha256=...' -> 'Qm.../a.png': the CID plus any path, nothing after whitespace."""
    s = re.sub(r"^(?:ipfs://|/?ipfs/)", "", str(c or "").strip(), flags=re.I)
    m = CID_RE.match(s); return m.group(0) if m else ""


def ipfs_url(gw, cid): return gw.rstrip("/") + "/" + clean_cid(cid)


def sources(primary, cid, ipfs_only=None):
    """[(kind, url)]: IPFS gateways first (originals), the NHL Breakaway CDN last (may be re-encoded)."""
    ipfs_only = IPFS_ONLY if ipfs_only is None else ipfs_only
    out = [("ipfs", ipfs_url(g, cid)) for g in GATEWAYS] if cid else []
    if primary and not ipfs_only:
        out = [("cdn", primary)] + out if CDN_FIRST else out + [("cdn", primary)]
    return out


def candidate_urls(primary, cid): return [u for _, u in sources(primary, cid)]


def sha_ok(b, expected):
    return (not expected) or b64sha(b).rstrip("=") == expected.rstrip("=")


def file_sha_b64(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""): h.update(ch)
    return base64.urlsafe_b64encode(h.digest()).decode()


def file_matches(path, expected):
    return bool(expected) and file_sha_b64(path).rstrip("=") == expected.rstrip("=")


def stream_to(url, part, kind, timeout=120):
    """Stream url into part (resuming a partial file). Returns 'ok', 429, an HTTP code, or 'err'."""
    if OFFLINE: return "offline"
    thr = host_thr(url); have = os.path.getsize(part) if os.path.exists(part) else 0
    hdr = dict(HDR) if kind == "cdn" else {"User-Agent": UA}
    if have: hdr["Range"] = f"bytes={have}-"
    thr.sem.acquire(); stop_wait(thr.delay)
    try:
        if stopping(): return "stopped"
        with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "text/html" in ctype: thr.bad(); return "err"          # gateway error page, not the file
            with open(part, "ab" if have and r.status == 206 else "wb") as f:
                for ch in iter(lambda: r.read(1 << 18), b""):
                    if stopping(): return "stopped"
                    f.write(ch)
                    if _PROG: _PROG.add_bytes(len(ch))
        thr.ok(); return "ok"
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            thr.bad(); cool(url, e.headers.get("Retry-After") if e.headers else None); return 429
        if e.code == 416 and have: return "ok"                        # already complete
        if e.code in (400, 401, 403, 404, 410, 451): return e.code
        thr.bad(); return "err"
    except Exception:
        thr.bad(); return "err"
    finally:
        thr.sem.release()


class DownloadLog:
    """output/download_log.json: where every downloaded file came from and whether it is the original."""
    def __init__(self):
        self.path = os.path.join(OUT, "download_log.json"); self.lock = threading.Lock()
        self.d = jload(self.path, {}) or {}; self.n = 0
    def get(self, kind, key): return (self.d.get(kind) or {}).get(str(key))
    def set(self, kind, key, rec):
        with self.lock:
            self.d.setdefault(kind, {})[str(key)] = rec; self.n += 1
            if self.n % 25 == 0: jdump(self.d, self.path)
    def save(self):
        with self.lock: jdump(self.d, self.path)


def fetch_asset(primary, cid, sha, dest, log, kind, key, ipfs_only=None):
    """Download one file, IPFS first. Returns 'original', 'reencoded', 'unverified' or None (failed).
    'original' = bytes match the metadata sha256. 'reencoded' = only the CDN had it and its bytes differ."""
    part = dest + ".part"; os.makedirs(os.path.dirname(dest), exist_ok=True)
    for src_kind, url in sources(primary, cid, ipfs_only):
        if cooled(url): continue
        if stopping(): break
        if os.path.exists(part): os.remove(part)                      # never mix bytes from two sources
        res = None
        for attempt in range(3):
            res = stream_to(url, part, src_kind, timeout=25 if src_kind == "ipfs" else 60)   # per-read timeout, not total
            if res != "err": break
            if not (os.path.exists(part) and os.path.getsize(part)): break   # never started: next source
            if stop_wait(min(60, 3 * 2 ** attempt)): break           # broke mid-file: back off, resume
        if res == "stopped" or stopping(): break
        if res != "ok": continue
        b64 = file_sha_b64(part)
        if sha and b64.rstrip("=") == sha.rstrip("="): status = "original"
        elif not sha: status = "unverified"
        elif src_kind == "cdn": status = "reencoded"
        else: os.remove(part); continue                               # a gateway served other bytes: try the next
        os.replace(part, dest)
        log.set(kind, key, {"file": os.path.relpath(dest, ROOT), "status": status, "source": src_kind,
                            "host": host_of(url), "sha256": b64, "expected_sha256": sha, "bytes": os.path.getsize(dest),
                            "cid": (cid or "").replace("ipfs://", ""), "at": now()})
        return status
    if os.path.exists(part): os.remove(part)   # never leave half a file behind (also when stopped)
    return None


def clean_partials(folder):
    """Remove leftovers of an interrupted run (e.g. the window was closed mid-file). Downloads are written to
    <name>.part and only renamed to <name> once complete and checked, so these are never mistaken for files."""
    n = 0
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.endswith((".part", ".new", ".new.part")):
                try: os.remove(os.path.join(folder, f)); n += 1
                except OSError: pass
    if n: p(f"Removed {n} unfinished file(s) left by an interrupted run; they will be downloaded again.")
    return n


def saved_ok(path, log, kind, key, sha):
    """Is the file already saved *completely*? Not just 'it exists': its size must match what was recorded
    when it was saved, or (no record, e.g. copied in by hand or from an old version) its sha256 must match."""
    if not path or not os.path.exists(path): return False
    size = os.path.getsize(path)
    if size == 0: return False
    rec = log.get(kind, key)
    if rec and rec.get("bytes"): return rec["bytes"] == size and os.path.basename(rec.get("file", path)) == os.path.basename(path)
    if sha: return file_matches(path, sha)
    return True                                             # nothing to check it against


def asset_ipfs(meta, purpose_or_path):
    """(IPFS CID, sha256) for a media purpose ('primary-asset', 'card-image', ...) or image key ('front')."""
    d = meta or {}
    if purpose_or_path in (d.get("images") or {}):
        x = d["images"][purpose_or_path]; return (x.get("altloc") or {}).get("ipfs"), x.get("sha256")
    for m in (d.get("assets") or {}).get("media") or []:
        if m.get("purpose") == purpose_or_path: return (m.get("altloc") or {}).get("ipfs"), m.get("sha256")
    return None, None


def get_with_fallback(primary, cid, timeout=120):
    for _, u in sources(primary, cid):
        if cooled(u): continue
        st, b, _ = http(u, timeout=timeout, tries=2, thr=host_thr(u))
        if b: return b, u
        if st == 429: cool(u)
    return None, None


# ------------------------------------------------------------------ covers
def cover_dest(r, url):
    ext = os.path.splitext((url or "").split("?")[0])[1] or ".png"
    return os.path.join(OUT, "covers_full", f"{r['id']}{ext}")


def pick(rows, a):
    if getattr(a, "series", None): rows = [r for r in rows if r["_s"]["series"].lower() == a.series.lower()]
    if getattr(a, "set", None): rows = [r for r in rows if a.set.lower() in (r["_s"]["set"] or "").lower()]
    if getattr(a, "player", None): rows = [r for r in rows if a.player.lower() in (r["_s"]["player"] or "").lower()]
    if getattr(a, "team", None): rows = [r for r in rows if a.team.lower() in (r["_s"]["team"] or "").lower()]
    if getattr(a, "ids", None):
        want = {x.strip() for x in a.ids.split(",") if x.strip()}; rows = [r for r in rows if str(r["id"]) in want]
    rows = mine_only(rows)
    if getattr(a, "at_risk", False):   # moments whose originals couldn't be reached on IPFS (see data/at_risk.md)
        kind = {"videos": "video", "covers": "cover"}.get(getattr(a, "command", ""))
        rows = [r for r in rows if r.get("ipfs_missing") and (not kind or kind in r["ipfs_missing"])]
        global CDN_FIRST
        if kind and not IPFS_ONLY: CDN_FIRST = True   # IPFS couldn't serve these: ask the CDN first, IPFS after
        p(f"--at-risk: {len(rows)} moment(s) with {kind or 'any file'} missing on IPFS")
    return rows


def cmd_covers(a, rows=None):
    rows = rows if rows is not None else pick(sort_rows(load_model()), a)[: getattr(a, "limit", None) or None]
    import_downloads(getattr(a, "video_dir", None))   # files saved by the viewer's Download buttons
    if getattr(a, "ask", False):
        missing = [r for r in rows if not cover_path(r)]
        p(f"{len(rows)} covers selected, {len(rows) - len(missing)} already saved, {len(missing)} to download "
          f"(about {len(missing) * 0.87:,.0f} MB).")
        if missing and len(missing) > 20 and not yes("Download them now?", True): p("Cancelled."); return
    log = DownloadLog(); stats = {"original": 0, "reencoded": 0, "unverified": 0, "cached": 0, "failed": 0, "repaired": 0}
    lock = threading.Lock(); cd = os.path.join(OUT, "covers_full"); os.makedirs(cd, exist_ok=True); clean_partials(cd)
    def one(r):
        if stopping(): return
        d = r["_meta"] or {}; front = (d.get("images") or {}).get("front") or {}; url = front.get("url")
        cid, sha = asset_ipfs(d, "front")
        if not url and not cid: pr.add("failed"); return
        fp = cover_path(r) or cover_dest(r, url)
        if os.path.exists(fp) and not saved_ok(fp, log, "cover", r["id"], sha):
            p(f"  cover {r['id']} ({r['player']}): the saved file is incomplete or damaged; downloading it again")
        elif os.path.exists(fp):
            if not (a.repair and sha and not file_matches(fp, sha)):
                with lock: stats["cached"] += 1
                pr.add("skipped"); return
            st = fetch_asset(None, cid, sha, fp, log, "cover", r["id"], ipfs_only=True)   # replace with the original
            if stopping() and st is None: return
            with lock: stats["repaired" if st == "original" else "failed"] += 1
            pr.add("ok" if st == "original" else "failed"); return
        st = fetch_asset(url, cid, sha, fp, log, "cover", r["id"])
        if stopping() and st is None: return
        with lock: stats[st or "failed"] += 1
        pr.add("ok" if st else "failed")
        if not st: p(f"  cover {r['id']} ({r['player']}): no source answered")
    with Progress("Covers", len(rows), folder=cd, show_bytes=True) as pr:
        try: run_pool(one, rows, min(MEDIA_CONC, 4), pr)
        finally: log.save()
    if stats["reencoded"] or stats["unverified"] or stats["repaired"]:
        p(f"  of the new covers: {stats['original']} original, {stats['reencoded']} re-encoded (CDN), "
          f"{stats['unverified']} unverified, {stats['repaired']} repaired")
    size = sum(os.path.getsize(os.path.join(cd, f)) for f in os.listdir(cd))
    p(f"  The covers folder now holds {len(os.listdir(cd)):,} files ({_mb(size)}).")


# ------------------------------------------------------------------ package for sharing
FRIEND_README = """NHL BREAKAWAY HIGHLIGHTS
Unofficial fan preservation project. Not affiliated with or endorsed by the NHL, NHLPA, NHLAA, Sweet (SocialSweet Inc.) or any team. All trademarks, names, logos, videos and images belong to their respective owners. This repository contains no media; anyone who downloads media with the tool does so only for personal archival use. Takedown requests are honored: please open a GitHub issue.
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
                    "Set (list label)" is the set name as written in data/highlights.json)
  Description       The official write-up, good for album captions
  Lowest Ask / FMV  Price snapshot (USD) saved with the card list in October 2026
  Cover Art, Video, NHL Breakaway Page, Metadata URL, Card List Page   clickable links
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
  5. Printable flip-book PDF:                  python breakaway.py album   (saved as output/album.pdf)
     Options: --layout 1up|2x2|3x3, --page letter|a4, --set/--series/--player/--team "name", --bleed
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
        for src, name in ((os.path.abspath(__file__), "breakaway.py"), (os.path.join(ROOT, "requirements.txt"), "requirements.txt")):
            if not FROZEN and os.path.exists(src): z.write(src, f"Breakaway-Highlights/{name}", D)
        for fn in names: z.write(os.path.join(cov, fn), f"Breakaway-Highlights/covers/{fn}", zipfile.ZIP_STORED)
    p(f"Packaged {zp} ({os.path.getsize(zp)/1e6:.0f} MB, {len(names)} covers)")


# ------------------------------------------------------------------ videos (opt-in)
def video_size(r):
    """Size from a 1-byte ranged GET (Content-Range total) on the first source that answers."""
    cid, _ = asset_ipfs(r["_meta"], "primary-asset")
    for kind, u in sources(r["_s"]["video_url"], cid)[:3]:
        if cooled(u): continue
        st, _, h = http(u, timeout=20, tries=1, thr=host_thr(u), headers={"Range": "bytes=0-0"})
        if st == 429: cool(u); continue
        m = re.search(r"/(\d+)$", (h or {}).get("Content-Range", "") or "")
        if m: return int(m.group(1))
    return None


def cmd_videos(a):
    rows = [r for r in pick(sort_rows(load_model()), a) if r["_s"]["video_url"] or asset_ipfs(r["_meta"], "primary-asset")[0]]
    if a.limit: rows = rows[: a.limit]
    out = os.path.abspath(a.video_dir); os.makedirs(out, exist_ok=True)
    def fname(r): return os.path.join(out, video_name(r))
    clean_partials(out); import_downloads(out); log = DownloadLog()
    repair = []
    if a.repair:   # files that exist but aren't the original (e.g. re-encoded CDN copies): replace from IPFS
        for r in rows:
            fp = fname(r); _, sh = asset_ipfs(r["_meta"], "primary-asset")
            if os.path.exists(fp) and sh and not file_matches(fp, sh): repair.append(r)
    def have(r):
        fp = fname(r)
        if not os.path.exists(fp): return False
        if saved_ok(fp, log, "video", r["id"], asset_ipfs(r["_meta"], "primary-asset")[1]): return True
        p(f"  video {r['id']} ({r['player']}): the saved file is incomplete or damaged; it will be downloaded again")
        return False
    todo = [r for r in rows if not have(r)]
    repair = [r for r in repair if r not in todo]   # an incomplete file is simply downloaded again
    p(f"{len(rows)} videos selected, {len(rows) - len(todo)} already saved, {len(todo)} to download into {out}"
      + (f", {len(repair)} to repair from IPFS" if a.repair else ""))
    if not todo and not repair: return
    sample = todo if len(todo) <= 20 else todo[:: max(1, len(todo) // 20)][:20]
    sizes = [n for n in (video_size(r) for r in sample) if n]
    est = (sum(sizes) / len(sizes) * (len(todo) + len(repair))) if sizes else None
    p(f"Estimated total: {est/1e9:.2f} GB (avg {sum(sizes)/len(sizes)/1e6:.1f} MB from {len(sizes)} size checks)" if est else "Could not estimate size.")
    if not a.yes and input("Download now? [y/N] ").strip().lower() not in ("y", "yes"): p("Cancelled."); return
    stats = {"original": 0, "reencoded": 0, "unverified": 0, "failed": 0}; lock = threading.Lock()
    def one(r, ipfs_only=None):
        if stopping(): return
        cid, sh = asset_ipfs(r["_meta"], "primary-asset"); dst = fname(r)
        if ipfs_only:   # repair: download next to the old file, swap only if we got the original
            tmp = dst + ".new"
            st = fetch_asset(None, cid, sh, tmp, log, "video", r["id"], ipfs_only=True)
            if st == "original": os.replace(tmp, dst); log.d["video"][str(r["id"])]["file"] = os.path.relpath(dst, ROOT)
            elif os.path.exists(tmp): os.remove(tmp)
        else:
            st = fetch_asset(r["_s"]["video_url"], cid, sh, dst, log, "video", r["id"])
        if stopping() and st is None: return
        with lock: stats[st or "failed"] += 1
        pr.add("ok" if st else "failed")
        if not st: p(f"  failed {r['id']} ({r['player']}): no source answered")
        elif st == "reencoded": p(f"  {r['id']}: only the CDN had it; saved, but it is a re-encoded copy (not the original)")
        return st
    skip_n = len(rows) - len(todo) - len(repair)
    with Progress("Videos", len(rows), folder=out, show_bytes=True, expect_bytes=est) as pr:
        pr.n["skipped"] = skip_n
        try:
            run_pool(one, todo, min(MEDIA_CONC, 4), pr)
            run_pool(lambda r: one(r, True), repair, min(MEDIA_CONC, 4), pr)
        finally: log.save()
    p(f"  {stats['original']} original, {stats['reencoded']} re-encoded (CDN only), {stats['unverified']} unverified, "
      f"{stats['failed']} failed  (log: {os.path.relpath(log.path, ROOT)})")


# ------------------------------------------------------------------ IPFS / preservation
def write_cids(man):
    """data/cids.txt: one CID per line (deduplicated) so anyone can `ipfs pin add` them."""
    seen = {}
    for k, e in sorted(man.items(), key=idkey):
        for x in e.get("ipfs") or []:
            cid = x["ipfs"].replace("ipfs://", "").strip("/")
            seen.setdefault(cid, f"{k} {x['path']}")
    with open(os.path.join(DATA, "cids.txt"), "w") as f:
        f.write("# IPFS CIDs referenced by the NHL Breakaway metadata in data/meta/ (deduplicated)\n")
        f.write("# pin them:  python breakaway.py pin --kubo   (or see README: Help keep it alive)\n")
        for cid, where in seen.items(): f.write(f"{cid}  # {where}\n")
    return len(seen)


TYPE_ORDER = ["video", "cover", "card-image", "cover-16x9", "poster", "thumbnail", "other"]


def asset_type(path):
    """Classify a manifest ipfs entry ('images.front', 'assets.media[3]' + url) into a simple file type."""
    s = path.lower()
    if "video" in s or "primary-asset" in s: return "video"
    if "card-image" in s: return "card-image"
    if "poster" in s: return "poster"
    if re.search(r"(350|500)x", s): return "thumbnail"
    if "16x9" in s: return "cover-16x9"
    if "front" in s: return "cover"
    return "other"


def cid_index(man=None, rows=None):
    """{cid: {"type", "ids": [card ids], "sha256"}} for every CID in the manifest (optionally only some cards)."""
    man = man if man is not None else (jload(os.path.join(DATA, "manifest.json"), {}) or {})
    keep = None if rows is None else {str(r["id"]) for r in rows}
    idx = {}
    for k, e in sorted(man.items(), key=idkey):
        if keep is not None and str(k) not in keep: continue
        for x in e.get("ipfs") or []:
            cid = x["ipfs"].replace("ipfs://", "").strip("/")
            t = asset_type(f"{x.get('path', '')} {(x.get('url') or '').rsplit('/', 1)[-1]}")
            d = idx.setdefault(cid, {"type": t, "ids": [], "sha256": x.get("sha256")})
            if TYPE_ORDER.index(t) < TYPE_ORDER.index(d["type"]): d["type"] = t
            if k not in d["ids"]: d["ids"].append(k)
    return idx


CHECK_GATEWAYS, CHECK_TIMEOUT, CHECK_PER_HOST = 2, 20, 3


def check_one(cid, n_gateways=None, timeout=None):
    """Range 0-0 GET on up to n_gateways gateways, in order (first gateway = the fast one).
    Reachable = any of them returns the first byte."""
    tried = []; n_gateways = n_gateways or CHECK_GATEWAYS
    for g in GATEWAYS:
        u = ipfs_url(g, cid)
        if cooled(u): continue
        if len(tried) >= n_gateways: break
        thr = host_thr(u, n=CHECK_PER_HOST, base=0.25)
        st, _, h = http(u, tries=1, timeout=timeout or CHECK_TIMEOUT, thr=thr, headers={"Range": "bytes=0-0"})
        tried.append(f"{host_of(u)}:{st}")
        if st is None:   # a timeout on cold (uncached) content isn't the gateway telling us to slow down
            with thr.lock: thr.delay = thr.base
        if st in (200, 206):
            return {"ok": True, "gateway": host_of(u), "http": st, "tried": tried}
        if st == 429: cool(u, (h or {}).get("Retry-After"))
    return {"ok": False, "gateway": None, "http": None, "tried": tried}


def ipfs_summary(cids, idx):
    by = {}
    for cid, e in cids.items():
        t = (idx.get(cid) or {}).get("type") or e.get("type") or "other"
        b = by.setdefault(t, {"checked": 0, "reachable": 0, "unreachable": 0})
        b["checked"] += 1; b["reachable" if e.get("ok") else "unreachable"] += 1
    tot = {k: sum(b[k] for b in by.values()) for k in ("checked", "reachable", "unreachable")}
    return {"total_cids": len(idx), **tot, "by_type": dict(sorted(by.items(), key=lambda x: TYPE_ORDER.index(x[0])))}


def cmd_check_ipfs(a):
    """Lightweight reachability check of IPFS CIDs. Default: a stratified sample; --full: every CID (slow)."""
    idx = cid_index(); path = os.path.join(DATA, "ipfs_status.json")
    st = jload(path, {}) or {}; cids = st.get("cids") or {}
    import random
    rnd = random.Random(a.seed)
    if a.full: pool = sorted(idx, key=lambda c: TYPE_ORDER.index(idx[c]["type"]))   # videos and covers first
    else:
        by = {}
        for cid, e in idx.items(): by.setdefault(e["type"], []).append(cid)
        pool = []
        for t, lst in sorted(by.items()):
            k = min(len(lst), max(15, round(a.sample * len(lst) / len(idx))))
            pool += rnd.sample(sorted(lst), k)
    fresh = time.time() - a.max_age * 86400
    def is_fresh(c):
        t = (cids.get(c) or {}).get("checked_at")
        try: return time.mktime(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")) > fresh and not a.refresh
        except Exception: return False
    todo = [c for c in pool if not is_fresh(c)]
    if a.recheck:   # second pass: only what failed, on more gateways with a longer timeout
        want = {t.strip() for t in (a.types or "").split(",") if t.strip()}
        todo = sorted((c for c, e in cids.items() if not e.get("ok") and c in idx and e.get("verdict") != "gone"
                       and (not want or idx[c]["type"] in want)), key=lambda c: TYPE_ORDER.index(idx[c]["type"]))
        p(f"check-ipfs --recheck: {len(todo)} unreachable CID(s), trying up to 4 gateways, 30 s each...")
    else: p(f"check-ipfs: {len(idx)} CIDs in the archive; checking {len(todo)} "
      f"({'full scan' if a.full else f'stratified sample of {len(pool)}'}; {len(pool) - len(todo)} checked recently) "
      f"via {', '.join(host_of(g) for g in GATEWAYS[:3])}...")
    lock = threading.Lock(); n = [0]
    def one(c):
        if stopping(): return
        if a.recheck:
            r = check_one(c, n_gateways=4, timeout=30); old = cids.get(c) or {}
            r.update({"type": idx[c]["type"], "checked_at": now(), "example_id": idx[c]["ids"][0],
                      "first_pass": {"ok": old.get("ok"), "tried": old.get("tried"), "checked_at": old.get("checked_at")},
                      "verdict": "uncached" if r["ok"] else "gone"})
        else:
            r = check_one(c); r.update({"type": idx[c]["type"], "checked_at": now(), "example_id": idx[c]["ids"][0],
                                        "verdict": "reachable" if r["ok"] else "unreachable"})
        with lock:
            cids[c] = r; n[0] += 1
            if n[0] % 20 == 0: st.update({"cids": dict(sorted(cids.items()))}); jdump(st, path)
        pr.add("ok" if r["ok"] else "failed")
    global CHECK_PER_HOST
    CHECK_PER_HOST = max(1, min(a.ipfs_concurrency, 6))
    with Progress("Checking IPFS", len(todo), ok="reachable", failed="not reachable", skipped="") as pr:
        try: run_pool(one, todo, CHECK_PER_HOST, pr)
        finally:
            with lock: st.update({"cids": dict(sorted(cids.items()))}); jdump(st, path)   # keep what was checked
    by_t = {}
    for c, e in idx.items():
        b_ = by_t.setdefault(e["type"], [0, 0]); b_[0] += 1; b_[1] += 1 if c in cids else 0
    complete = all(c in cids for c in idx)
    st.update({"updated_at": now(), "mode": "full" if complete else ("partial full scan" if (a.full or a.recheck or st.get("mode") != "sample") else "sample"),
               "complete": complete, "coverage": {t: f"{v[1]}/{v[0]}" for t, v in sorted(by_t.items(), key=lambda x: TYPE_ORDER.index(x[0]))},
               "note": ("Every CID checked." if complete else
                        "PARTIAL: the full scan was stopped before every CID was checked (see coverage); run "
                        "`python breakaway.py check-ipfs --full` to resume, then `--recheck`." if (a.full or a.recheck) else
                        f"Stratified random sample (seed {a.seed}); run `python breakaway.py check-ipfs --full` for every CID."),
               "method": f"1-byte ranged GET, {CHECK_TIMEOUT}s timeout; reachable if any of the first {CHECK_GATEWAYS} "
                         "gateways returns it. `--recheck` retries failures on up to 4 gateways with a 30s timeout. "
                         "verdict: reachable | unreachable (first pass only) | uncached (failed, then answered on retry) | "
                         "gone (failed on both passes; nobody seems to serve it, but that isn't proof it's deleted).",
               "gateways": [host_of(g) for g in GATEWAYS], "summary": ipfs_summary(cids, idx), "cids": dict(sorted(cids.items()))})
    jdump(st, path)
    s = st["summary"]
    p(f"IPFS: {s['reachable']}/{s['checked']} reachable, {s['unreachable']} not (of {s['total_cids']} CIDs) -> data/ipfs_status.json")
    for t, b in s["by_type"].items(): p(f"  {t:12s} {b['reachable']:>5}/{b['checked']:<5} reachable")
    if a.full or a.recheck: apply_health()


# ------------------------------------------------------------------ moment health: IPFS + current listings + CDN
HEALTH = ["all_ok", "some_missing", "video_missing", "all_missing", "unchecked"]
KEY_TYPES = ("video", "cover", "card-image")


def moment_files(man_entry):
    """{cid: type} for one moment's manifest entry."""
    out = {}
    for x in man_entry.get("ipfs") or []:
        cid = x["ipfs"].replace("ipfs://", "").strip("/")
        t = asset_type(f"{x.get('path', '')} {(x.get('url') or '').rsplit('/', 1)[-1]}")
        if cid not in out or TYPE_ORDER.index(t) < TYPE_ORDER.index(out[cid]): out[cid] = t
    return out


def health_of(files, cids):
    """all_ok / some_missing / video_missing / all_missing / unchecked, plus the missing file types.
    Missing = not reachable on IPFS in the last check-ipfs run (after --recheck if it was run)."""
    missing, unchecked = set(), 0
    for cid, t in files.items():
        e = cids.get(cid)
        if not e: unchecked += 0 if t == "thumbnail" else 1   # small derived thumbnails don't decide the health
        elif not e.get("ok"): missing.add(t)
    if not files: return "unchecked", []
    nmiss = sum(1 for cid in files if cids.get(cid) and not cids[cid].get("ok"))
    if nmiss and nmiss == len(files): h = "all_missing"
    elif "video" in missing: h = "video_missing"
    elif missing: h = "some_missing"
    elif unchecked: h = "unchecked"
    else: h = "all_ok"
    return h, sorted(missing, key=TYPE_ORDER.index)


def cmd_check_live(a):
    """Is each moment still in NHL Breakaway's current public set listings, and does the CDN still serve
    its cover and video? Range-0 GETs only. Raw data/offchain/ files are NOT overwritten (they keep the
    data as first archived); the current listings go to cache/live_sets/."""
    rows = load_model(); man = jload(os.path.join(DATA, "manifest.json"), {})
    path = os.path.join(DATA, "live_status.json"); st = jload(path, {}) or {}; per = st.get("moments") or {}
    ld = os.path.join(CACHE, "live_sets"); os.makedirs(ld, exist_ok=True)
    sets = sorted(f[:-5] for f in os.listdir(os.path.join(DATA, "offchain", "sets")) if f.endswith(".json"))
    thr = Throttle(2, 0.5); failed_sets = []
    def grab(u):
        s_, b, _ = http(f"{APIGW}/catalog/search/moment/set/{u}?campaign_id=826", thr=thr, tries=4)
        if b and s_ == 200: wbytes(os.path.join(ld, f"{u}.json"), b); return True
        failed_sets.append(u); return False
    with cf.ThreadPoolExecutor(2) as ex: list(ex.map(grab, sets))
    if failed_sets: p(f"  {len(failed_sets)} set listing(s) couldn't be fetched; their moments are left as they were")
    live = set()
    for u in sets:
        if u in failed_sets: continue
        for m in jload(os.path.join(ld, f"{u}.json"), []) or []: live.add(m["uuid"])
    p(f"Current listings: {len(sets) - len(failed_sets)} sets, {len(live)} moments")
    lock = threading.Lock(); n = [0]; blocked = set()
    def probe(u):
        """HTTP status, or None if unknown. A 403/429 from a host that served fine before means it is
        throttling us: stop asking that host for the rest of the run (never worked around)."""
        if not u or host_of(u) in blocked: return None
        s_, _, _ = http(u, tries=2, timeout=30, thr=host_thr(u, n=1, base=1.0), headers={"Range": "bytes=0-0"})
        if s_ in (403, 429):
            with lock:
                if host_of(u) not in blocked:
                    blocked.add(host_of(u)); p(f"  {host_of(u)} answered {s_}: stopping CDN checks there for this run (results left unknown)")
            return None
        return s_
    def one(r):
        k = str(r["id"]); e = man.get(k, {}); u = e.get("moment_uuid"); s = summary(r)
        set_uuid = ((r["_off"] or {}).get("token_set") or {}).get("uuid") or ""
        rec = dict(per.get(k) or {})
        if any(u and u.startswith(x[:12]) for x in failed_sets) and "listed_now" in rec: pass
        else: rec["listed_now"] = bool(u and u in live)
        if not a.no_cdn:
            for key, url in (("cdn_cover", s["cover_url"]), ("cdn_video", s["video_url"])):
                if rec.get(key) in (200, 206) and not a.refresh: continue   # resumable: already known to be served
                code = probe(url)
                if code is not None or key not in rec: rec[key] = code
        rec["checked_at"] = now()
        with lock:
            per[k] = rec; n[0] += 1
            if n[0] % 200 == 0: p(f"  {n[0]}/{len(rows)}"); st["moments"] = per; jdump(st, path)
    with cf.ThreadPoolExecutor(2 if not a.no_cdn else 1) as ex: list(ex.map(one, rows))
    if blocked: p(f"  Some CDN checks were skipped because {', '.join(sorted(blocked))} started refusing; re-run later to fill them in.")
    st.update({"updated_at": now(), "method": "listed_now: moment UUID present in the current apigw.sweet.io set listing. "
               "cdn_cover / cdn_video: HTTP status of a 1-byte ranged GET (206/200 = still served; null = not checked, "
               "e.g. the host was throttling us). Hosts that answer 403/429 are not asked again in the same run.",
               "moments": dict(sorted(per.items(), key=idkey))})
    jdump(st, path)
    gone = [k for k, v in per.items() if v.get("listed_now") is False]
    p(f"Live check: {len(per) - len(gone)} still listed, {len(gone)} not in the current listings; -> data/live_status.json")
    apply_health()


def cdn_ok(code): return code in (200, 206)


def apply_health(quiet=False):
    """Write ipfs_health / ipfs_missing / listed_now / status into data/highlights.json and data/at_risk.md."""
    hp = os.path.join(DATA, "highlights.json"); hl = jload(hp)
    man = jload(os.path.join(DATA, "manifest.json"), {}) or {}
    cids = (jload(os.path.join(DATA, "ipfs_status.json"), {}) or {}).get("cids") or {}
    live = (jload(os.path.join(DATA, "live_status.json"), {}) or {}).get("moments") or {}
    counts, risk = {}, []
    for r in hl:
        k = str(r["id"]); h, miss = health_of(moment_files(man.get(k, {})), cids)
        r["ipfs_health"] = h
        if miss: r["ipfs_missing"] = miss
        else: r.pop("ipfs_missing", None)
        lv = live.get(k) or {}
        if "listed_now" in lv:
            r["listed_now"] = lv["listed_now"]
            if lv["listed_now"] is False:
                if r.get("status") != "delisted": r["status_before_delisting"] = r.get("status", "unverified")
                r["status"] = "delisted"
            elif r.get("status") == "delisted":
                r["status"] = r.pop("status_before_delisting", "unverified")
        counts[h] = counts.get(h, 0) + 1
        if miss: risk.append((r, miss, lv))
    jdump(hl, hp)
    write_at_risk(risk, len(hl), counts, cids)
    if not quiet:
        p("IPFS health: " + ", ".join(f"{counts.get(h, 0)} {h}" for h in HEALTH)
          + f"; {sum(1 for r in hl if r.get('status') == 'delisted')} delisted -> data/highlights.json, data/at_risk.md")
    return counts


AT_RISK_HEAD = """# Moments at risk

These NHL Breakaway moments have **original files that could not be reached on IPFS** in the last check
(`python breakaway.py check-ipfs`, then `--recheck` on at least two gateways). "Missing" means no gateway we
asked could serve it. That can mean nobody pins it anymore, or just that it's very cold, so treat it as at risk,
not proven lost.

> **Did you download any of these?** Please check your copies with `python breakaway.py verify`:
> a file marked **original** matches the official sha256 and is the real thing. If you have one, help
> re-pin it (`ipfs add` the file on your own node: it gets the same CID back) or open an issue so
> others know a copy exists. To grab them while the CDN still has them:
> `python breakaway.py covers --at-risk` and `python breakaway.py videos --at-risk`. Note that the CDN serves
> re-encoded videos, so a CDN copy is better than nothing but isn't the original.

"""


def write_at_risk(risk, total, counts, cids):
    checked = len(cids)
    idx = cid_index(); by_t = {}
    for c, e in idx.items():
        b_ = by_t.setdefault(e["type"], [0, 0]); b_[0] += 1; b_[1] += 1 if c in cids else 0
    cov = ", ".join(f"{t} {v[1]:,}/{v[0]:,}" for t, v in sorted(by_t.items(), key=lambda x: TYPE_ORDER.index(x[0])))
    gone = sum(1 for e in cids.values() if e.get("verdict") == "gone")
    first_only = sum(1 for e in cids.values() if not e.get("ok") and e.get("verdict") != "gone")
    partial = ""
    if not all(c in cids for c in idx):
        partial = ("\n> **PARTIAL SCAN.** Not every file has been checked yet (checked/total: " + cov + "). "
                   "Thumbnails are mostly unchecked, so they don't count toward `unchecked` health. "
                   f"{gone} file(s) failed twice on up to 4 gateways (`gone`); {first_only} failed the first pass only and "
                   "weren't re-checked yet. Anyone can finish the scan: `python breakaway.py check-ipfs --full` (it resumes, "
                   "skipping files checked in the last 30 days), then `check-ipfs --recheck`, then `health`.\n")
    lines = [AT_RISK_HEAD + partial, f"Generated {now()[:16].replace('T', ' ')} UTC from `data/ipfs_status.json` ({checked:,} CIDs checked) "
             f"and `data/live_status.json`. {len(risk)} of {total:,} moments have at least one missing file.\n",
             "| IPFS health | moments |", "|---|---|"] + [f"| {h} | {counts.get(h, 0)} |" for h in HEALTH] + [""]
    def cdn(lv, key):
        c = lv.get(key)
        return "-" if c is None and key not in lv else ("yes" if cdn_ok(c) else f"no ({c})")
    order = {"all_missing": 0, "video_missing": 1, "some_missing": 2}
    risk.sort(key=lambda x: (order.get(x[0]["ipfs_health"], 3), idkey(str(x[0]["id"]))))
    lines += ["| Card | Player | Set | Rarity | Health | Missing on IPFS | CDN cover | CDN video | Listed now |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r, miss, lv in risk:
        lines.append(f"| {r['id']} | {r['player']} | {r['set']} | {r.get('rarity', '')} | {r['ipfs_health']} | {', '.join(miss)} "
                     f"| {cdn(lv, 'cdn_cover')} | {cdn(lv, 'cdn_video')} | {'-' if 'listed_now' not in lv else ('yes' if lv['listed_now'] else 'no')} |")
    if not risk: lines.append("| - | none | | | | | | | |")
    open(os.path.join(DATA, "at_risk.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def cmd_health(a): apply_health()


# ------------------------------------------------------------------ pin (help keep the files alive)
PIN_SERVICES = {   # IPFS Pinning Service API (https://ipfs.github.io/pinning-services-api-spec/)
    "pinata": "https://api.pinata.cloud/psa",
    "filebase": "https://api.filebase.io/v1/ipfs",
}


def cmd_pin(a):
    rows = pick(sort_rows(load_model()), a); idx = cid_index(rows=rows)
    types = {t.strip() for t in (a.types or "").split(",") if t.strip()}
    if types: idx = {c: e for c, e in idx.items() if e["type"] in types}
    pd = os.path.join(OUT, "pin"); os.makedirs(pd, exist_ok=True)
    by = {}
    for c, e in idx.items(): by.setdefault(e["type"], []).append(c)
    for t, lst in by.items(): open(os.path.join(pd, f"{t}.txt"), "w").write("\n".join(lst) + "\n")
    open(os.path.join(pd, "all.txt"), "w").write("\n".join(idx) + "\n")
    p(f"Pin lists ({len(idx)} CIDs) in {os.path.relpath(pd, ROOT)}/: all.txt, " + ", ".join(f"{t}.txt ({len(v)})" for t, v in by.items()))
    if not a.kubo and not a.service:
        p("Nothing pinned. To pin: --kubo (your own IPFS node) or --service pinata|filebase|<API URL> "
          "with your key in PIN_SERVICE_TOKEN. Start small, e.g. --types video,cover --series \"Series 1\".")
        return
    done_path = os.path.join(pd, f"pinned_{'kubo' if a.kubo else re.sub(r'[^a-z0-9]+', '_', a.service.lower())}.txt")
    done = set(open(done_path).read().split()) if os.path.exists(done_path) else set()
    todo = [c for c in idx if c not in done]
    if a.limit: todo = todo[: a.limit]
    p(f"{len(todo)} to pin ({len(done)} already done according to {os.path.relpath(done_path, ROOT)})")
    if not todo: return
    if not a.yes and input("Pin now? [y/N] ").strip().lower() not in ("y", "yes"): p("Cancelled."); return
    ok = fail = 0
    with Progress("Pinning", len(todo), ok="pinned", skipped="") as pr, open(done_path, "a") as log:
        if a.kubo:
            import shutil, subprocess
            exe = shutil.which("ipfs")
            if not exe: sys.exit("`ipfs` (Kubo) isn't on your PATH: https://docs.ipfs.tech/install/command-line/")
            for i in range(0, len(todo), 20):
                batch = todo[i:i + 20]
                r = subprocess.run([exe, "pin", "add", "--progress=false", *batch], capture_output=True, text=True)
                if r.returncode == 0: ok += len(batch); log.write("\n".join(batch) + "\n"); log.flush()
                else:
                    for c in batch:   # retry one by one so one bad CID doesn't block the rest
                        if subprocess.run([exe, "pin", "add", "--progress=false", c], capture_output=True).returncode == 0:
                            ok += 1; log.write(c + "\n"); log.flush()
                        else: fail += 1
                pr.n["ok"], pr.n["failed"] = ok, fail; pr.draw()
        else:
            base = PIN_SERVICES.get(a.service.lower(), a.service).rstrip("/")
            tok = os.environ.get("PIN_SERVICE_TOKEN")
            if not tok: sys.exit("Set PIN_SERVICE_TOKEN to your pinning service API token (it is never saved).")
            thr = Throttle(1, 0.5)
            for i, c in enumerate(todo, 1):
                body = json.dumps({"cid": c, "name": f"breakaway-{idx[c]['type']}-{idx[c]['ids'][0]}"}).encode()
                for attempt in range(5):
                    try:
                        thr.sem.acquire(); time.sleep(thr.delay)
                        req = urllib.request.Request(base + "/pins", data=body, method="POST", headers={
                            "Authorization": f"Bearer {tok}", "Content-Type": "application/json", "User-Agent": UA})
                        with urllib.request.urlopen(req, timeout=60): pass
                        ok += 1; log.write(c + "\n"); log.flush(); thr.ok(); break
                    except urllib.error.HTTPError as e:
                        if e.code == 429 or e.code >= 500:
                            thr.bad(); ra = e.headers.get("Retry-After") if e.headers else None
                            time.sleep(float(ra) if ra and ra.isdigit() else min(120, 5 * 2 ** attempt)); continue
                        if e.code in (401, 403): sys.exit(f"The pinning service refused the token (HTTP {e.code}).")
                        fail += 1; p(f"  {c}: HTTP {e.code}"); break
                    except Exception:
                        thr.bad(); time.sleep(min(120, 5 * 2 ** attempt))
                    finally: thr.sem.release()
                else: fail += 1
                pr.n["ok"], pr.n["failed"] = ok, fail; pr.draw()
    p(f"Pinned {ok}, failed {fail}. Services pin asynchronously: check their dashboard for 'pinned' status.")


# ------------------------------------------------------------------ verify
def classify(path, expected, logrec):
    if not expected: return "unverified"
    if file_matches(path, expected): return "original"
    if logrec and logrec.get("source") == "ipfs": return "corrupt"
    return "reencoded"


def cmd_verify(a):
    rows = load_model(); man = jload(os.path.join(DATA, "manifest.json"), {})
    res = {"meta_ok": 0, "meta_bad": 0, "meta_missing": 0}
    files = {"cover": {}, "video": {}}; notes = []
    for k, e in sorted(man.items(), key=idkey):
        fp = os.path.join(DATA, "meta", f"{k}.json")
        if not os.path.exists(fp): res["meta_missing"] += 1; continue
        if hashlib.sha256(open(fp, "rb").read()).hexdigest() == e.get("sha256"): res["meta_ok"] += 1
        else: res["meta_bad"] += 1; notes.append(f"meta {k}: sha256 differs from manifest")
    log = DownloadLog(); vdir = os.path.abspath(a.video_dir); per = {}
    jobs = [(r, kind, path, purpose) for r in sort_rows(rows)
            for kind, path, purpose in (("cover", cover_path(r), "front"), ("video", os.path.join(vdir, video_name(r)), "primary-asset"))
            if path and os.path.exists(path)]
    with Progress("Verifying files", len(jobs), ok="ok", failed="not original", skipped="", resumable=False) as pr:
        for r, kind, path, purpose in jobs:
            _, sh = asset_ipfs(r["_meta"], purpose); st = classify(path, sh, log.get(kind, r["id"]))
            files[kind][st] = files[kind].get(st, 0) + 1; per.setdefault(str(r["id"]), {})[kind] = st
            if st in ("reencoded", "corrupt"): notes.append(f"{kind} {r['id']}: {st}")
            with pr.lock: pr.n["ok" if st in ("original", "unverified") else "failed"] += 1; pr.bytes += os.path.getsize(path)
            pr.draw()
    jdump({"checked_at": now(), "results": res, "files": files, "per_card": per, "not_original": notes},
          os.path.join(OUT, "verify_report.json"))
    p(f"Metadata: {res}")
    for kind, d in files.items(): p(f"{kind.capitalize()}s: " + (", ".join(f"{v} {k}" for k, v in sorted(d.items())) or "none downloaded"))
    for b in notes[:40]: p("  ", b)
    if any(d.get("reencoded") or d.get("corrupt") for d in files.values()):
        p("original = matches the sha256 in the NHL Breakaway metadata. reencoded = a different copy (the CDN "
          "now re-encodes). Run the same command with --repair to replace them with originals from IPFS.")
    p(f"Report: {os.path.relpath(os.path.join(OUT, 'verify_report.json'), ROOT)}")


# ------------------------------------------------------------------ add moments by URL
URL_RE = re.compile(r"(?:nft\.)?nhlbreakaway\.com/series/([A-Za-z0-9]{6,12})/(\d{6,})|^([A-Za-z0-9]{6,12})/(\d{6,})$")


def parse_moment_refs(items):
    out = []
    for it in items:
        it = it.strip()
        if not it or it.startswith("#"): continue
        m = URL_RE.search(it)
        if m: out.append((m.group(1) or m.group(3), m.group(2) or m.group(4)))
        else: p("  can't read:", it)
    return out


# ------------------------------------------------------------------ "my collection" (local and private)
# my_cards.txt / my_cards.csv is YOUR file: it is read locally, never uploaded or sent anywhere, and is in .gitignore.
MINE = None          # {card id: [edition numbers you listed]} when --mine is used
SITE_PLAYER_RE = re.compile(r"/player/(\d+)\b")
MINE_DEFAULT = "my_cards.txt"


def mine_lines(path):
    """[(raw line, values to try in order, edition or None)]: plain lines, or CSV rows (any column names).
    The Fifth Line export header is card_id,url,series_id,token_id,edition,player,set: matched on card_id,
    then url, then series_id+token_id."""
    txt = open(path, encoding="utf-8-sig", errors="replace").read()
    lines = [ln for ln in txt.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines: return []
    is_csv = path.lower().endswith(".csv") or ("," in lines[0] and not URL_RE.search(lines[0].split(",")[0] or "x"))
    if not is_csv: return [(ln.strip(), [ln.strip()], None) for ln in lines]
    rows = list(csv.reader(lines))
    head = [re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_") for h in rows[0]]
    looks_header = not any(URL_RE.search(c) or SITE_PLAYER_RE.search(c) or c.strip().isdigit() for c in rows[0])
    body = rows[1:] if looks_header else rows
    col = lambda *names: next((i for i, h in enumerate(head) if looks_header and h in names), None)
    c_id = col("card_id", "cardid", "id", "card", "card_number")
    c_url = col("url", "link", "card_url", "breakaway_url", "nft_url", "site_url")
    c_ser, c_tok, c_ed = col("series_id", "series"), col("token_id", "token"), col("edition", "edition_number", "serial")
    pref = [i for i, h in enumerate(head) if looks_header and re.search(r"url|link|card.?id|^id$|token|moment", h)]
    out = []
    for r in body:
        g = lambda i: r[i].strip() if i is not None and i < len(r) else ""
        cells = [g(c_id), g(c_url)]
        if g(c_ser) and g(c_tok): cells.append(f"{g(c_ser)}/{g(c_tok)}")
        # other id-like columns, then any other column holding a link (a bare number there may be a quantity)
        cells += [r[i] for i in pref if i < len(r)] + [c for i, c in enumerate(r) if i not in pref and (not pref or not c.strip().isdigit())]
        ed = g(c_ed).lstrip("#")
        out.append((",".join(r), [c.strip() for c in cells if c and c.strip()], int(ed) if ed.isdigit() else None))
    return out


def load_mine(path, quiet=False):
    """-> ({card id: [editions]}, [unmatched lines]). Accepts NHL Breakaway URLs (any edition), series/token,
    archive card ids, and https://thefifthlinecode.onrender.com/player/<id> links, as text lines or a CSV."""
    if not os.path.exists(path):
        sys.exit(f"Can't find your card list: {path}\nMake a text file with one card per line (see README: Show only my cards).")
    links = jload(os.path.join(DATA, "links.json"), {}) or {}
    by_moment = {}
    for k, v in links.items():
        try: by_moment[(v["series_id"], int(v["token_id"]) >> 48)] = k
        except (KeyError, ValueError, TypeError): pass
    ids = {str(r["id"]) for r in jload(os.path.join(DATA, "highlights.json"), [])}
    def card_of(c):
        """(card id, edition from a URL or None) for one value, or None."""
        m = URL_RE.search(c)
        if m:
            sid, tok = m.group(1) or m.group(3), int(m.group(2) or m.group(4))
            k = by_moment.get((sid, tok >> 48))
            return (k, (tok & 0xFFFFFFFFFFFF) + 1) if k else None   # edition number = low 48 bits + 1
        m = SITE_PLAYER_RE.search(c)
        if m and m.group(1) in ids: return (m.group(1), None)
        if c.isdigit() and c in ids and len(c) <= 6: return (c, None)
        return None
    mine, unmatched = {}, []
    for raw, cells, ed in mine_lines(path):
        hit = next((h for h in map(card_of, cells) if h), None)
        if not hit: unmatched.append(raw); continue
        edition = ed or hit[1] or next((h[1] for h in map(card_of, cells) if h and h[0] == hit[0] and h[1]), None)
        eds = mine.setdefault(hit[0], [])
        if edition and edition not in eds: eds.append(edition)
    for v in mine.values(): v.sort()
    if not quiet:
        p(f"My cards ({os.path.basename(path)}, read on this computer only, nothing is sent anywhere): "
          f"{len(mine)} moment(s), {sum(len(v) for v in mine.values())} edition number(s); {len(unmatched)} line(s) not matched")
        for u in unmatched[:20]: p(f"  not matched: {u[:120]}")
        if len(unmatched) > 20: p(f"  ... and {len(unmatched) - 20} more")
    return mine, unmatched


def mine_only(rows):
    return rows if MINE is None else [r for r in rows if str(r["id"]) in MINE]


def my_editions(r):
    """Full sorted list of your edition numbers ('#26, #94, ...'); the spreadsheet keeps all of them."""
    eds = (MINE or {}).get(str(r["id"])) or []
    return ", ".join(f"#{e}" for e in eds)


def owned_short(eds, show=3):
    """'Owned x12: #26, #94, #322 +9 more' (lowest first) for tight spaces like album cards."""
    if not eds: return "Owned"
    head = ", ".join(f"#{e}" for e in eds[:show])
    return f"Owned \u00d7{len(eds)}: {head}" + (f" +{len(eds) - show} more" if len(eds) > show else "")


def cmd_add(a):
    items = list(a.refs or [])
    extra = os.path.join(DATA, "extra_moments.txt")
    if os.path.exists(extra): items += open(extra, encoding="utf-8").read().splitlines()
    refs = parse_moment_refs(items)
    if not refs: p("Nothing to add. Pass URLs or put them in data/extra_moments.txt"); return
    add_refs(refs, "added by URL")


def add_refs(refs, via):
    rows = jload(os.path.join(DATA, "highlights.json"), []); links = jload(os.path.join(DATA, "links.json"), {})
    man = jload(os.path.join(DATA, "manifest.json"), {})
    known_uuid = {e.get("moment_uuid"): k for k, e in man.items() if e.get("moment_uuid")}
    known_tok = {(v["series_id"], str(int(v["token_id"]) >> 48)): k for k, v in links.items()}
    added = 0
    nid = max([int(r["id"]) for r in rows if str(r["id"]).isdigit()] + [int(k) for k in man if k.isdigit()] + [0]) + 1
    for sid, tok in refs:
        if (sid, str(int(tok) >> 48)) in known_tok: p(f"  already have {sid}/{tok} (id {known_tok[(sid, str(int(tok) >> 48))]})"); continue
        st, b, h, tok = get_nft(sid, tok); url = f"{NFT}/{sid}/{tok}"
        if not b: p(f"  {url}: HTTP {st}, skipped"); continue
        d = json.loads(b); at = {t["name"]: t["value"] for t in d.get("attributes", [])}
        u = at.get("Moment UUID")
        if u in known_uuid: p(f"  {sid}/{tok} is the same moment as id {known_uuid[u]}, skipped"); continue
        k = str(nid); nid += 1  # new card ids go after the existing ones; nothing is renumbered
        wbytes(os.path.join(DATA, "meta", f"{k}.json"), b)
        man[k] = {"id": int(k), "source_url": url, "fetched_at": now(), "status": st, "link_via": via,
                  "meta_path": f"data/meta/{k}.json", "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                  "content_type": h.get("Content-Type") if h else None, "ipfs": ipfs_entries(d), "moment_uuid": u}
        links[k] = {"series_id": sid, "token_id": tok, "exact": True, "via": via}
        if at.get("Set UUID"):  # off-chain set listing for this moment
            sp = os.path.join(DATA, "offchain", "sets", f"{at['Set UUID']}.json")
            if not os.path.exists(sp):
                st2, b2, _ = http(f"{APIGW}/catalog/search/moment/set/{at['Set UUID']}?campaign_id=826")
                if b2: wbytes(sp, b2)
            if os.path.exists(sp) and any(m.get("uuid") == u for m in jload(sp, [])):
                man[k]["offchain_path"] = f"data/offchain/sets/{at['Set UUID']}.json"
        rows.append({"id": int(k), "player": at.get("Player", d.get("name", "")), "set": at.get("Set", ""),
                     "rarity": at.get("Rarity", ""), "editions": int(at["Total Editions"]) if str(at.get("Total Editions", "")).isdigit() else None,
                     "team": at.get("Team", ""), "lowest_ask": "", "fmv": "", "on_site": False, "status": "unverified"})
        known_uuid[u] = k; known_tok[(sid, str(int(tok) >> 48))] = k; added += 1; p(f"  added {k}: {at.get('Player')} / {at.get('Set')}")
    rows.sort(key=lambda r: idkey(r["id"]))
    jdump(rows, os.path.join(DATA, "highlights.json"))
    jdump(dict(sorted(links.items(), key=idkey)), os.path.join(DATA, "links.json"))
    jdump(dict(sorted(man.items(), key=idkey)), os.path.join(DATA, "manifest.json"))
    write_cids(man); p(f"Added {added} moment(s). Run `python breakaway.py build` to refresh the spreadsheet.")


# ------------------------------------------------------------------ offline viewer
VIEWER = r"""<!doctype html><html><head><meta charset="utf-8"><title>breakaway-data viewer</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="generator" content="Breakaway Archive v__VERSION__">
<style>
body{margin:0;font:14px system-ui,sans-serif;background:#0f141a;color:#e6edf3}
header{position:sticky;top:0;background:#16202b;padding:10px;display:flex;flex-wrap:wrap;gap:8px;z-index:2}
input,select{background:#0f141a;color:#e6edf3;border:1px solid #33414f;border-radius:6px;padding:6px}
#count{align-self:center;color:#8b9aa8}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;padding:10px}
.card{position:relative;background:#16202b;border-radius:8px;overflow:hidden;cursor:pointer}.card:hover{outline:2px solid #3b82f6}
.card img{width:100%;aspect-ratio:1;object-fit:cover;background:#222;display:block}
.card div{padding:6px 8px}.card b{display:block}.card small{color:#8b9aa8}
.card .own{display:block;color:#facc15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.badge{position:absolute;top:6px;right:6px;background:#facc15;color:#111;font-weight:700;font-size:12px;border-radius:10px;padding:1px 7px}
.badge.one{background:#0f141acc;color:#facc15;font-weight:600}
#dlg{position:fixed;inset:0;background:#000c;display:none;overflow:auto;z-index:3}
#box{max-width:1000px;margin:30px auto;background:#16202b;border-radius:10px;padding:16px}
#box img,#box video{max-width:100%;max-height:60vh;display:block;margin:0 auto 10px}
#box .lead{font-size:15px;line-height:1.5;margin:6px 0 12px}
.btns{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:8px 0}
.btns button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:8px 14px;font-size:14px;cursor:pointer}
.btns button:disabled{background:#33414f;cursor:wait}.btns button.saved{background:#166534}.again{font-size:12px}.dlw{display:inline-flex;gap:8px;align-items:center}
.st{color:#a7f3d0;font-size:12px;min-height:1em}.note{color:#8b9aa8;font-size:12px;margin:2px 0 12px}
.yours{color:#facc15}
details{margin-top:14px;border-top:1px solid #26323e;padding-top:8px}summary{cursor:pointer;color:#8b9aa8}
table{border-collapse:collapse;width:100%;font-size:12px}td{border-top:1px solid #26323e;padding:3px 6px;vertical-align:top;word-break:break-all}
td:first-child{color:#8b9aa8;white-space:nowrap;word-break:normal}a{color:#60a5fa}
#more{display:block;margin:10px auto;padding:8px 20px}
</style></head><body>
<header><input id="q" placeholder="Search player, set, description…" size="30">
<select id="f_team"></select><select id="f_set"></select><select id="f_rarity"></select><select id="f_series"></select>
<label id="minebox" style="display:none;align-self:center"><input type="checkbox" id="f_mine" checked> My cards</label>
<select id="f_sort" style="display:none"><option value="">Default order</option><option value="owned">Most owned</option></select>
<span id="count"></span></header>
<div id="grid"></div><button id="more">Show more</button>
<footer style="padding:16px;color:#8b9aa8;font-size:12px;text-align:center">Unofficial fan preservation project. Not affiliated with or endorsed by the NHL, NHLPA, NHLAA, Sweet (SocialSweet Inc.) or any team. All trademarks, names, logos, videos and images belong to their respective owners. This repository contains no media; anyone who downloads media with the tool does so only for personal archival use. Takedown requests are honored: please open a GitHub issue at <a href="__ISSUES__">__ISSUES__</a>.<br>__TAGLINE__ __WARRANTY__<br>Breakaway Archive v__VERSION__</footer>
<div id="dlg"><div id="box"></div></div>
<script>
const DATA = __DATA__;
const HAS_MINE = DATA.some(r=>r.mine);
if(HAS_MINE){document.getElementById('minebox').style.display='';document.getElementById('f_sort').style.display=''}
const MY_MOMENTS = DATA.filter(r=>r.mine).length, MY_EDS = DATA.reduce((n,r)=>n+(r.mine?(r.eds||[]).length:0),0);
const GW = __GATEWAYS__;
const $ = s => document.querySelector(s);
const fmt = n => Number(n).toLocaleString('en-US');
function opts(sel, key, label){const v=[...new Set(DATA.map(r=>r.s[key]).filter(Boolean))].sort();
  sel.innerHTML=`<option value="">All ${label}</option>`+v.map(x=>`<option>${esc(x)}</option>`).join('');}
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
opts($('#f_team'),'team','teams');opts($('#f_set'),'set','sets');opts($('#f_rarity'),'rarity','rarities');opts($('#f_series'),'series','series');
// a clean CID (with an optional /path), never anything after a space: "ipfs://Qm.../a.png  sha256=..." -> "Qm.../a.png"
function cidOf(c){const m=String(c||'').trim().replace(/^ipfs:\/\//i,'').replace(/^\/?ipfs\//i,'').match(/^[A-Za-z0-9]+(\/[^\s]*)?/);return m?m[0]:''}
function ipfsUrl(cid,g){const c=cidOf(cid);return c?(GW[g||0]||GW[0]).replace(/\/+$/,'')+'/'+c:''}
function ipfsAll(cid){return cidOf(cid)?GW.map((g,i)=>ipfsUrl(cid,i)):[]}
// covers: your local file first (works offline), then the first IPFS gateway, then the NHL Breakaway CDN,
// then the other gateways. A source that errors or hasn't loaded after STALL_MS is skipped; at most MAX_SRC tries.
const STALL_MS=6000, MAX_SRC=5;
function coverSources(r){const s=r.s,ip=ipfsAll(s.cover_ipfs);
  return [...new Set([r.local_cover,ip[0],s.cover_url,...ip.slice(1)].filter(Boolean))].slice(0,MAX_SRC)}
function imgTag(r){const a=coverSources(r);if(!a.length)return '<img alt="">';
  return `<img loading="lazy" decoding="async" src="${esc(a[0])}" data-alts="${esc(a.slice(1).join('|'))}" onerror="nextSrc(this)" alt="">`}
function nextSrc(img){clearTimeout(img._t);const a=(img.dataset.alts||'').split('|').filter(Boolean);
  if(!a.length){img.onerror=null;return}
  img.src=a.shift();img.dataset.alts=a.join('|');arm(img)}
function arm(img){clearTimeout(img._t);img._t=setTimeout(()=>{if(!(img.complete&&img.naturalWidth))nextSrc(img)},STALL_MS)}
const io=('IntersectionObserver' in window)?new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){io.unobserve(e.target);arm(e.target)}}),{rootMargin:'200px'}):null;
function watch(root){root.querySelectorAll('img[data-alts]').forEach(i=>{if(i._w)return;i._w=1;
  i.addEventListener('load',()=>clearTimeout(i._t));if(i.complete&&i.naturalWidth)return;io?io.observe(i):arm(i)})}
function ownedLine(r,show){const e=r.eds||[];if(!e.length)return 'yours';
  return 'yours '+e.slice(0,show).map(x=>'#'+x).join(', ')+(e.length>show?` +${e.length-show} more`:'')}
let list=[],shown=0;
function apply(){const q=$('#q').value.toLowerCase();
  const fv={team:$('#f_team').value,set:$('#f_set').value,rarity:$('#f_rarity').value,series:$('#f_series').value};
  const onlyMine=HAS_MINE&&$('#f_mine').checked;
  list=DATA.filter(r=>(!onlyMine||r.mine)&&(!q||r.text.includes(q))&&Object.entries(fv).every(([k,v])=>!v||r.s[k]===v));
  if(HAS_MINE&&$('#f_sort').value==='owned')list.sort((a,b)=>((b.eds||[]).length-(a.eds||[]).length)||(b.mine-a.mine)||(a.i-b.i));
  shown=0;$('#grid').innerHTML='';more();}
function tile(r){const n=(r.eds||[]).length;
  const badge=r.mine?(n>1?`<span class="badge" title="you own ${n} editions">\u00d7${n}</span>`:`<span class="badge one">owned</span>`):'';
  const own=r.mine?`<small class="own" title="${esc((r.eds||[]).map(x=>'#'+x).join(', ')||'yours')}">${esc(ownedLine(r,3))}</small>`:'';
  return `<div class="card" data-i="${r.i}">${imgTag(r)}${badge}<div><b>${esc(r.s.player)}</b>${own}<small>${esc(r.s.set)} · ${esc(r.s.rarity)} · ${esc(r.s.date)}</small></div></div>`}
function more(){const part=list.slice(shown,shown+120);shown+=part.length;
  $('#grid').insertAdjacentHTML('beforeend',part.map(tile).join(''));watch($('#grid'));
  const onlyMine=HAS_MINE&&$('#f_mine').checked;
  $('#count').textContent=onlyMine?`My cards: ${fmt(MY_MOMENTS)} moments, ${fmt(MY_EDS)} editions (showing ${fmt(list.length)})`:`${fmt(list.length)} of ${fmt(DATA.length)} highlights`;
  $('#more').style.display=shown<list.length?'':'none';}
function rowsOf(o,pre=''){let out=[];if(o&&typeof o==='object'){for(const[k,v]of Object.entries(o)){out=out.concat(rowsOf(v,pre?pre+'.'+k:k))}}else out.push([pre,o]);return out}
function link(v){v=String(v??'');if(/^https?:\/\//.test(v))return `<a href="${esc(v)}" target="_blank">${esc(v)}</a>`;
  if(/^ipfs:\/\//i.test(v)&&cidOf(v))return `<a href="${esc(ipfsUrl(v))}" target="_blank">${esc(v)}</a>`;return esc(v)}
// ---- downloads from the detail card: verified IPFS original first, the CDN copy after, a new tab only if all fail
function fname(s,kind,ext){return `${s.player} - ${s.set} - ${kind}.${ext}`.replace(/[\\\/:*?"<>|]+/g,'-')}
// small pure-JS SHA-256, used only when the browser has no crypto.subtle (e.g. some browsers on file://)
function sha256js(buf){const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
  const b=new Uint8Array(buf),n=b.length,L=((n+9+63)>>6)<<6,m=new Uint8Array(L);m.set(b);m[n]=0x80;const dv=new DataView(m.buffer);
  dv.setUint32(L-8,Math.floor(n/0x20000000));dv.setUint32(L-4,(n<<3)>>>0);
  let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;const w=new Uint32Array(64);
  const r=(x,k)=>(x>>>k)|(x<<(32-k));
  for(let o=0;o<L;o+=64){for(let i=0;i<16;i++)w[i]=dv.getUint32(o+i*4);
    for(let i=16;i<64;i++){const a=w[i-15],c=w[i-2];w[i]=(w[i-16]+(r(a,7)^r(a,18)^(a>>>3))+w[i-7]+(r(c,17)^r(c,19)^(c>>>10)))>>>0}
    let a=h0,bb=h1,c=h2,d=h3,e=h4,f=h5,g=h6,hh=h7;
    for(let i=0;i<64;i++){const t1=(hh+(r(e,6)^r(e,11)^r(e,25))+((e&f)^(~e&g))+K[i]+w[i])>>>0,t2=((r(a,2)^r(a,13)^r(a,22))+((a&bb)^(a&c)^(bb&c)))>>>0;
      hh=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=bb;bb=a;a=(t1+t2)>>>0}
    h0=(h0+a)>>>0;h1=(h1+bb)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+hh)>>>0}
  const out=new Uint8Array(32),ov=new DataView(out.buffer);[h0,h1,h2,h3,h4,h5,h6,h7].forEach((v,i)=>ov.setUint32(i*4,v));return out}
async function b64sha(buf){let h=null;
  try{if(window.crypto&&crypto.subtle)h=new Uint8Array(await crypto.subtle.digest('SHA-256',buf))}catch(e){console.info('crypto.subtle unavailable, using the built-in SHA-256:',e)}
  try{if(!h)h=sha256js(buf)}catch(e){console.warn('could not hash the file:',e);return null}
  let s='';for(let i=0;i<h.length;i++)s+=String.fromCharCode(h[i]);return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
// plain GET (no custom headers, so no CORS preflight). Gives up only if the server sends nothing for 30 s;
// a slow but moving download just keeps going and shows its progress on the button.
async function fetchBuf(url,btn){const ac=new AbortController();let timer;const idle=(ms)=>{clearTimeout(timer);timer=setTimeout(()=>ac.abort(),ms||30000)};
  idle(15000);   // no answer at all within 15 s: next source
  try{const r=await fetch(url,{signal:ac.signal});if(!r.ok)throw new Error('HTTP '+r.status);
    if((r.headers.get('content-type')||'').includes('text/html'))throw new Error('got an HTML page, not the file');
    const total=+(r.headers.get('content-length')||0);
    if(!(r.body&&r.body.getReader)){const b=await r.arrayBuffer();return b}
    const rd=r.body.getReader(),parts=[];let got=0;
    for(;;){idle();const {done,value}=await rd.read();if(done)break;parts.push(value);got+=value.length;
      btn.textContent=total?`Downloading ${Math.floor(got*100/total)}%...`:`Downloading ${(got/1e6).toFixed(1)} MB...`}
    if(!got)throw new Error('empty response');
    const out=new Uint8Array(got);let o=0;for(const p of parts){out.set(p,o);o+=p.length}return out.buffer}
  catch(e){if(e&&e.name==='AbortError')throw new Error('no data in time (15 s to start, 30 s between chunks)');throw e}
  finally{clearTimeout(timer)}}
function saveBuf(buf,name,type){const u=URL.createObjectURL(new Blob([buf],{type:type||'application/octet-stream'}));const a=document.createElement('a');
  a.href=u;a.download=name;a.style.display='none';document.body.appendChild(a);a.click();
  setTimeout(()=>{a.remove();URL.revokeObjectURL(u)},120000)}   // keep the URL alive long enough for big files
// a gateway link that downloads under the app's own file name (gateways honour ?filename=...&download=true)
function ipfsDlUrl(cid,name,g){const u=ipfsUrl(cid,g);return u?u+'?filename='+encodeURIComponent(name)+'&download=true':''}
// ---- saving straight into the archive folder (Chrome/Edge: File System Access API; the folder is remembered)
const FS_OK=typeof window.showDirectoryPicker==='function';let OUT_DIR=null,FS_DECLINED=false;
function idb(){return new Promise((res,rej)=>{const q=indexedDB.open('breakaway-viewer',1);q.onupgradeneeded=()=>q.result.createObjectStore('kv');q.onsuccess=()=>res(q.result);q.onerror=()=>rej(q.error)})}
async function kv(k,v){try{const db=await idb();return await new Promise(res=>{const st=db.transaction('kv',v===undefined?'readonly':'readwrite').objectStore('kv');
  const q=v===undefined?st.get(k):st.put(v,k);q.onsuccess=()=>res(v===undefined?q.result:true);q.onerror=()=>res(null)})}catch(e){return null}}
async function archiveDir(say){   // call first thing in a click: the folder picker needs the click's "user activation"
  if(!FS_OK||FS_DECLINED)return null;
  try{let h=OUT_DIR||await kv('outdir');
    if(h){let p=await h.queryPermission({mode:'readwrite'});if(p!=='granted')p=await h.requestPermission({mode:'readwrite'});if(p==='granted')return OUT_DIR=h}
    say('Pick your Breakaway-Archive/output folder (only asked once)...');
    h=await window.showDirectoryPicker({id:'breakaway-output',mode:'readwrite'});
    try{h=await h.getDirectoryHandle('output')}catch(e){}            // picked Breakaway-Archive itself: use its output folder
    await kv('outdir',h);return OUT_DIR=h}
  catch(e){console.info('[download] no archive folder picked, saving to Downloads instead:',e&&e.message||e);FS_DECLINED=true;return null}}
async function writeInto(dir,sub,name,buf){const d=await dir.getDirectoryHandle(sub,{create:true});const fh=await d.getFileHandle(name,{create:true});
  const w=await fh.createWritable();await w.write(buf);await w.close()}   // written to a temp file, renamed on close
// ---- "already saved?" check for the detail card: the picked archive folder first, then the viewer's own relative paths
const SUBDIR={video:'videos',cover:'covers_full'};
const mbs=n=>(n/1e6).toFixed(1)+' MB';
async function dirIfGranted(){   // never prompts: only uses a remembered folder that still has permission
  if(!FS_OK)return null;
  try{const h=OUT_DIR||await kv('outdir');if(!h)return null;const p=await h.queryPermission({mode:'readwrite'});
    if(p==='granted'){OUT_DIR=h;return h}return 'ask'}catch(e){return null}}
async function fileIn(dir,kind,name){try{const d=await dir.getDirectoryHandle(SUBDIR[kind]);return await (await d.getFileHandle(name)).getFile()}catch(e){return null}}
function probeLocal(url,kind){return new Promise(res=>{if(!url)return res(false);let done=false,el;
  const fin=v=>{if(done)return;done=true;res(v);if(kind==='video'){el.removeAttribute('src');el.load()}};
  if(kind==='video'){el=document.createElement('video');el.preload='metadata';el.muted=true;el.onloadedmetadata=()=>fin(true)}
  else{el=new Image();el.onload=()=>fin(el.naturalWidth>0)}
  el.onerror=()=>fin(false);setTimeout(()=>fin(false),5000);el.src=url})}
function shaOf(r,kind){return String((kind==='video'?r.s.video_sha256:r.s.cover_sha256)||'').replace(/=+$/,'')}
// deep=true also hashes (on click). Covers are small, so they are always hashed; videos only get a size check on open.
async function checkSaved(i,kind,deep){const r=DATA[i],name=kind==='video'?r.video_name:r.cover_name,sha=shaOf(r,kind),want=(r.dlb||{})[kind]||0;
  const dir=await dirIfGranted();
  if(dir&&dir!=='ask'){const f=await fileIn(dir,kind,name),where=`${dir.name}/${SUBDIR[kind]}/${name}`;
    if(f){if(!f.size)return {state:'bad',where,why:'it is empty'};
      if(want&&f.size!==want)return {state:'bad',where,why:`its size (${mbs(f.size)}) doesn't match the original (${mbs(want)})`};
      if(sha&&(deep||kind==='cover')){const h=await b64sha(await f.arrayBuffer());
        if(h&&h!==sha)return {state:'bad',where,why:"its fingerprint (sha256) doesn't match the original"};
        if(h)return {state:'ok',how:'verified',where}}
      return {state:'ok',how:want?'size':'unchecked',where}}}
  const url=kind==='video'?r.video_rel:r.cover_rel;
  if(await probeLocal(url,kind))return {state:'ok',how:'local',where:url};
  return {state:dir==='ask'?'ask':'none'}}
const LABEL={video:'Download video',cover:'Download cover'},CHECKS={};
function render(i,kind,res){const w=document.querySelector(`#box .dlw_${kind}`);if(!w||+w.dataset.i!==i)return;
  const b=w.querySelector('.main'),again=w.querySelector('.again'),say=t=>{const s=document.querySelector('#box .st_'+kind);if(s)s.textContent=t};
  w.dataset.state=res.state;w.dataset.how=res.how||'';b.disabled=false;b.classList.toggle('saved',res.state==='ok');again.style.display=res.state==='ok'?'':'none';
  if(res.state==='ok'){b.textContent='Already saved \u2713';
    say({verified:`Already saved and verified (sha256 matches the original): ${res.where}`,size:`Already saved (size matches the original): ${res.where}. Click to check its fingerprint.`,
         unchecked:`Already saved: ${res.where}. Click to check it.`,local:`Already saved in your archive folder (${res.where}).`,
         downloads:`Saved to your Downloads as ${res.where}. The app will move it into the archive next time you run it.`}[res.how]||'Already saved.')}
  else if(res.state==='bad'){b.textContent='Download again';say(`The saved copy (${res.where}) looks incomplete: ${res.why}. Click "Download again" to replace it.`)}
  else{b.textContent=LABEL[kind];say(res.state==='ask'?'':'')}}
async function onMain(i,kind,btn){const w=btn.closest('.dlw'),st=w.dataset.state,how=w.dataset.how;
  if(st==='ok'){if(how==='verified'){render(i,kind,{state:'ok',how:'verified',where:(await CHECKS[kind]||{}).where||''});return}
    if(how==='local'||how==='downloads'){const s=document.querySelector('#box .st_'+kind);if(s&&how==='local')s.textContent='Already saved in your archive folder. To check it, use 7) Check my downloaded files in the app, or "Download again" to replace it.';return}
    btn.disabled=true;btn.textContent='Checking...';const res=await checkSaved(i,kind,true);CHECKS[kind]=Promise.resolve(res);render(i,kind,res);return}
  if(st==='ask'){btn.disabled=true;   // a remembered folder that needs permission again: ask now (this is a click)
    try{const h=await kv('outdir');if(h&&await h.requestPermission({mode:'readwrite'})==='granted'){OUT_DIR=h;const res=await checkSaved(i,kind,true);
      if(res.state==='ok'||res.state==='bad'){CHECKS[kind]=Promise.resolve(res);render(i,kind,res);if(res.state==='ok')return}}}catch(e){console.info('[download] permission not granted:',e&&e.message||e)}
    btn.disabled=false}
  return dl(i,kind,btn)}
async function dl(i,kind,btn){const r=DATA[i],s=r.s,isV=kind==='video';
  const stEl=document.querySelector('#box .st_'+kind),say=t=>{if(stEl)stEl.textContent=t};
  const cid=isV?s.video_ipfs:s.cover_ipfs,sha=shaOf(r,kind),cdn=isV?s.video_url:s.cover_url;
  const name=(isV?r.video_name:r.cover_name)||fname(s,kind,isV?'mp4':'png'),ext=(name.split('.').pop()||'').toLowerCase();
  const type=isV?'video/mp4':(ext==='png'?'image/png':ext==='webp'?'image/webp':ext==='gif'?'image/gif':'image/jpeg');
  const sub=SUBDIR[kind];btn.disabled=true;
  const done=res=>{CHECKS[kind]=Promise.resolve(res);render(i,kind,res)};
  const fail=t=>{btn.disabled=false;btn.textContent=LABEL[kind];say(t)};
  const dir=await archiveDir(say);
  // sources: the first IPFS gateways, then NHL Breakaway's copy, then the other gateways; every one is checked by sha256
  const ip=ipfsAll(cid),srcs=[...ip.slice(0,2).map(u=>['ipfs',u]),...(cdn?[['cdn',cdn]]:[]),...ip.slice(2,4).map(u=>['ipfs',u])];
  let got=null,verified=false;
  try{
    for(const [k,u] of srcs){const host=u.split('/')[2];
      try{say('Trying '+(k==='cdn'?'the NHL Breakaway CDN':host)+'...');btn.textContent='Downloading...';
        const b=await fetchBuf(u,btn);btn.textContent='Checking...';const h=sha?await b64sha(b):null;
        if(h&&h===sha){got=b;verified=true;break}
        if(k==='cdn'&&!got){got=b;console.warn('[download] the CDN copy is not the original (sha256 differs); keeping it as a fallback')}
        else console.warn(`[download] ${host}: sha256 differs from the metadata, trying the next source`)}
      catch(e){console.warn(`[download] ${host} failed:`,e&&e.message||e)}}
  }catch(e){console.error('[download] unexpected error:',e)}
  if(got&&verified&&dir){   // createWritable writes to a temporary file and swaps it in on close, so a broken write never replaces a good file
    try{await writeInto(dir,sub,name,got);return done({state:'ok',how:'verified',where:`${dir.name}/${sub}/${name}`})}
    catch(e){console.warn('[download] could not write into the archive folder, saving to Downloads instead:',e&&e.message||e)}}
  if(got){saveBuf(got,name,type);
    if(verified)return done({state:'ok',how:'downloads',where:name});
    return fail(`Saved to your Downloads as ${name} (${mbs(got.byteLength)}). This copy is from the NHL Breakaway CDN and may be re-encoded, so the app will leave it there.`)}
  const u=cidOf(cid)?ipfsDlUrl(cid,name,0):cdn;
  if(u){console.warn('[download] every source failed; opening a download link in a new tab instead:',u);window.open(u,'_blank');
    return fail(`Couldn't download it here, so a download link opened in a new tab. If it shows the file instead, right-click > Save as and name it ${name}.`)}
  fail('No source answered. Please try again later.')}
function open_(i){const r=DATA[i],s=r.s;const gwName=u=>u.split('/')[2];
  const cov=coverSources(r);const poster=r.local_cover||s.cover_url||cov[0]||'';
  // playback: your local file, then the CDN (fast; may be a re-encoded copy), then IPFS. Downloads prefer the IPFS original.
  const vsrc=[r.local_video,s.video_url,...ipfsAll(s.video_ipfs).slice(0,2)].filter(Boolean);
  const video=vsrc.length?`<video controls preload="none" poster="${esc(poster)}">${vsrc.map(v=>`<source src="${esc(v)}" type="video/mp4">`).join('')}</video>`:imgTag(r);
  const eds=r.eds||[];
  const mine=r.mine?`<p class="yours"><b>Yours${eds.length?` (${eds.length} edition${eds.length>1?'s':''})`:''}:</b> ${esc(eds.map(x=>'#'+x).join(', ')||'on your list')}</p>`:'';
  const one=k=>`<span class="dlw dlw_${k}" data-i="${i}" data-state="none"><button class="main" onclick="onMain(${i},'${k}',this)">${LABEL[k]}</button> <a href="#" class="again" style="display:none" onclick="event.preventDefault();dl(${i},'${k}',this.parentNode.querySelector('.main'))">Download again</a></span>`;
  const btns=`<div class="btns">${vsrc.length?one('video'):''}${cov.length?one('cover'):''}</div>
   <div class="st st_video"></div><div class="st st_cover"></div>
   <p class="note">In Chrome or Edge you can pick your Breakaway-Archive/output folder once and files are saved straight into the archive. Otherwise they go to your Downloads folder and the app moves them into the archive the next time you run it.</p>`;
  const L=(u,t)=>u?`<a href="${esc(u)}" target="_blank">${esc(t)}</a>`:'';
  const links=`<p><b>Links:</b> ${[L(s.breakaway_url,'NHL Breakaway page'),L(s.site_url,'The Fifth Line'),L(s.meta_url,'Metadata (JSON)'),L(s.cover_url,'Cover on the CDN'),L(s.video_url,'Video on the CDN (may be re-encoded)')].filter(Boolean).join(' · ')}<br>
   Original video via IPFS: ${ipfsAll(s.video_ipfs).map(v=>L(v,gwName(v))).join(' · ')||'none'}</p>`;
  const st=v=>v?` <small>(local file: ${esc(v)})</small>`:'';
  const cidLink=c=>cidOf(c)?`<a href="${esc(ipfsUrl(c))}" target="_blank">${esc(cidOf(c))}</a>`:'—';
  const ident=`<h3>Permanent identity (IPFS)</h3><table>
   <tr><td>Cover CID</td><td>${cidLink(s.cover_ipfs)}${st(r.dl&&r.dl.cover)}</td></tr>
   <tr><td>Cover sha256</td><td>${esc(s.cover_sha256)}</td></tr>
   <tr><td>Video CID</td><td>${cidLink(s.video_ipfs)}${st(r.dl&&r.dl.video)}</td></tr>
   <tr><td>Video sha256</td><td>${esc(s.video_sha256)}</td></tr>
   <tr><td>Card image CID</td><td>${cidLink(s.card_image_ipfs)}</td></tr>
   <tr><td>Status</td><td>${esc(s.status)}</td></tr></table>
   <p><small>A CID is the file's fingerprint: any IPFS gateway or node can serve the exact original with it, even if NHL Breakaway is gone.</small></p>`;
  const files=`<h3>Every IPFS file for this moment</h3><table><tr><td>file</td><td>CID (link)</td><td>sha256</td></tr>${Object.entries(r.ipfs||{}).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${cidLink(v.cid)}</td><td>${esc(v.sha256||'')}</td></tr>`).join('')}</table>`;
  const tbl=(title,o)=>`<h3>${title}</h3><table>${rowsOf(o).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${link(v)}</td></tr>`).join('')}</table>`;
  $('#box').innerHTML=`<button onclick="$('#dlg').style.display='none'" style="float:right">Close</button>
  <h2>${esc(s.player)} — ${esc(s.set)}</h2>${video}<p class="lead">${esc(s.description)}</p>${mine}${btns}${links}
  <details><summary>Technical details (IPFS CIDs, sha256, all metadata)</summary>${ident}${files}${tbl('Summary',s)}${tbl('Source',r.src)}${tbl('All metadata (nft.nhlbreakaway.com)',r.meta||{})}${tbl('Off-chain (NHL Breakaway set listing)',r.off||{})}</details>`;
  watch($('#box'));$('#dlg').style.display='block';$('#dlg').scrollTop=0;
  for(const k of ['video','cover']){if(!document.querySelector('#box .dlw_'+k))continue;const p=checkSaved(i,k,false).catch(e=>({state:'none'}));CHECKS[k]=p;p.then(res=>render(i,k,res))}}
$('#grid').onclick=e=>{const c=e.target.closest('.card');if(c)open_(+c.dataset.i)};
$('#dlg').onclick=e=>{if(e.target.id==='dlg'){$('#dlg').style.display='none';const v=$('#box video');if(v)v.pause()}};
document.onkeydown=e=>{if(e.key==='Escape'){$('#dlg').style.display='none';const v=$('#box video');if(v)v.pause()}};
['#q','#f_team','#f_set','#f_rarity','#f_series','#f_mine','#f_sort'].forEach(s=>{const e=$(s);if(e){e.oninput=apply;e.onchange=apply}});$('#more').onclick=more;apply();
</script></body></html>"""


def video_name(r): return f"{r['_s']['row']:04d}_{safe(r['player'])}_{safe(r['_s']['set'])}.mp4"


def cover_name(r):
    """File name the app uses for a cover in output/covers_full/ (e.g. 22.png)."""
    cp = cover_path(r)
    if cp: return os.path.basename(cp)
    front = ((r["_meta"] or {}).get("images") or {}).get("front") or {}
    return os.path.basename(cover_dest(r, front.get("url")))


# ------------------------------------------------------------------ pick up files saved by the viewer's Download buttons
IMPORT_COVER_RE = re.compile(r"^\d+(?: \(\d+\))?\.(?:png|jpe?g|webp|gif)$", re.I)          # 22.png, 22 (1).png
IMPORT_VIDEO_RE = re.compile(r"^\d{4}_[A-Za-z0-9_]+(?: \(\d+\))?\.mp4$", re.I)              # 0001_Mark_Stone_Base (1).mp4


def downloads_dirs():
    """The user's Downloads folder(s): BREAKAWAY_DOWNLOADS_DIR if set, else the standard place on Windows/Mac/Linux."""
    if os.environ.get("BREAKAWAY_DOWNLOADS_DIR"): return [os.environ["BREAKAWAY_DOWNLOADS_DIR"]]
    out = []
    if sys.platform == "win32":
        try:   # the real Downloads folder, even if it was moved (Known Folder FOLDERID_Downloads)
            import ctypes, uuid
            from ctypes import wintypes
            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
            u = uuid.UUID("374DE290-123F-4565-9164-39C4925E467B"); g = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            buf = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(buf)) == 0:
                out.append(buf.value); ctypes.windll.ole32.CoTaskMemFree(buf)
        except Exception: pass
    elif sys.platform.startswith("linux"):
        try:   # xdg-user-dirs: XDG_DOWNLOAD_DIR="$HOME/Downloads"
            cfg = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "user-dirs.dirs")
            m = re.search(r'^XDG_DOWNLOAD_DIR="([^"]+)"', open(cfg, encoding="utf-8").read(), re.M)
            if m: out.append(os.path.expandvars(m.group(1).replace("$HOME", os.path.expanduser("~"))))
        except OSError: pass
    out.append(os.path.join(os.path.expanduser("~"), "Downloads"))
    return [d for d in dict.fromkeys(out) if d and os.path.isdir(d)]


def import_downloads(video_dir=None, rows=None):
    """Move covers/videos saved by the viewer's Download buttons from Downloads into the archive.
    Only files named like the app's own files are looked at, and a file is only moved if its sha256 matches
    an original in the archive (that also decides where it goes). Everything else is left exactly where it is."""
    found = []
    for d in downloads_dirs():
        try: names = os.listdir(d)
        except OSError: continue
        for f in names:
            kind = "cover" if IMPORT_COVER_RE.match(f) else "video" if IMPORT_VIDEO_RE.match(f) else None
            if kind and os.path.isfile(os.path.join(d, f)): found.append((kind, os.path.join(d, f)))
    if not found: return 0
    rows = rows if rows is not None else sort_rows(load_model())
    vdir = os.path.abspath(video_dir or os.path.join(OUT, "videos"))
    index = {}
    for r in rows:
        for kind, purpose in (("cover", "front"), ("video", "primary-asset")):
            sha = asset_ipfs(r["_meta"], purpose)[1]
            if sha: index[(kind, sha.rstrip("="))] = r
    log = DownloadLog(); moved, have, left = 0, 0, []
    for kind, src in found:
        # cheap check first, so big videos already in the archive aren't re-hashed on every start
        base = re.sub(r" \(\d+\)(?=\.[^.]+$)", "", os.path.basename(src))
        twin = os.path.join(vdir if kind == "video" else os.path.join(OUT, "covers_full"), base)
        try:
            if os.path.isfile(twin) and os.path.getsize(twin) == os.path.getsize(src): have += 1; continue
        except OSError: pass
        try: r = index.get((kind, file_sha_b64(src).rstrip("=")))
        except OSError: continue
        if not r: left.append(os.path.basename(src)); continue
        if kind == "cover":
            front = ((r["_meta"] or {}).get("images") or {}).get("front") or {}
            dest = cover_path(r) or cover_dest(r, front.get("url")); sha = asset_ipfs(r["_meta"], "front")[1]
        else:
            dest = os.path.join(vdir, video_name(r)); sha = asset_ipfs(r["_meta"], "primary-asset")[1]
        if os.path.exists(dest) and file_matches(dest, sha): have += 1; continue      # already in the archive: leave the copy
        os.makedirs(os.path.dirname(dest), exist_ok=True); tmp = dest + ".part"
        try:
            shutil.copy2(src, tmp); os.replace(tmp, dest); os.remove(src); moved += 1
        except OSError as e:
            if os.path.exists(tmp): os.remove(tmp)
            p(f"  couldn't import {os.path.basename(src)}: {e}"); continue
        log.set(kind, r["id"], {"file": os.path.relpath(dest, ROOT), "status": "original", "source": "browser download",
                                "host": "", "sha256": file_sha_b64(dest), "expected_sha256": sha, "bytes": os.path.getsize(dest),
                                "cid": "", "at": now()})
    log.save()
    if moved or left:   # copies that are already in the archive alone are not worth a line on every start
        msg = f"Imported {moved} file(s) from Downloads" if moved else "Nothing new to import from Downloads"
        if have: msg += f"; {have} already in the archive (left in Downloads)"
        if left: msg += f"; {len(left)} named like archive files but not matching an original (left in Downloads, e.g. {left[0]})"
        p(msg + ".")
    return moved


def cmd_view(a):
    rows = sort_rows(load_model()); vd = os.path.abspath(a.viewer_dir); os.makedirs(vd, exist_ok=True)
    vdir = os.path.abspath(a.video_dir); data = []; log = DownloadLog()
    for i, r in enumerate(rows):
        s = dict(r["_s"]); s["video_ipfs"], _ = asset_ipfs(r["_meta"], "primary-asset")
        for k in ("cover_ipfs", "video_ipfs", "card_image_ipfs"): s[k] = clean_cid(s.get(k))
        cp = cover_path(r); vp = os.path.join(vdir, video_name(r))
        rel = lambda x: os.path.relpath(x, vd).replace(os.sep, "/")
        data.append({"i": i, "s": s, "meta": r["_meta"], "off": {k: v for k, v in (r["_off"] or {}).items() if k not in ("series", "token_set", "badges")},
                     "ipfs": {e["path"]: {"cid": clean_cid(e["ipfs"]), "sha256": e.get("sha256") or ""} for e in (r["_man"].get("ipfs") or [])},
                     "src": {k: r["_man"].get(k) for k in ("source_url", "fetched_at", "sha256", "meta_path", "offchain_path", "link_via")},
                     "local_cover": rel(cp) if cp else "", "local_video": rel(vp) if os.path.exists(vp) else "",
                     "cover_name": cover_name(r), "video_name": video_name(r),
                     "cover_rel": rel(os.path.join(OUT, "covers_full", cover_name(r))), "video_rel": rel(os.path.join(vdir, video_name(r))),
                     "dlb": {k: (log.get(k, r["id"]) or {}).get("bytes") for k in ("cover", "video")},
                     "dl": {k: (log.get(k, r["id"]) or {}).get("status") for k in ("cover", "video")},
                     "mine": MINE is not None and str(r["id"]) in MINE, "eds": (MINE or {}).get(str(r["id"])) or [],
                     "text": " ".join(str(s.get(k, "")) for k in ("player", "team", "set", "series", "rarity", "description", "tagline", "date", "cover_ipfs", "video_ipfs")).lower()})
    out = VIEWER.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")).replace("__GATEWAYS__", json.dumps(GATEWAYS)).replace("__ISSUES__", html.escape(ISSUES_URL)).replace("__WARRANTY__", html.escape(WARRANTY)).replace("__TAGLINE__", html.escape(TAGLINE)).replace("__VERSION__", VERSION)
    open(os.path.join(vd, "index.html"), "w", encoding="utf-8").write(out)
    p(f"Wrote {os.path.relpath(os.path.join(vd, 'index.html'), ROOT)} ({len(out)/1e6:.1f} MB, {len(data)} highlights, "
      f"{sum(1 for d in data if d['local_cover'])} local covers, {sum(1 for d in data if d['local_video'])} local videos). Open it in a browser.")



# ------------------------------------------------------------------ printable album (PDF)
DISCLAIMER = ("Unofficial fan preservation project. Not affiliated with or endorsed by the NHL, NHLPA, NHLAA, "
              "Sweet (SocialSweet Inc.) or any team. All trademarks, names, logos, videos and images belong to "
              "their respective owners. For personal archival use only.")


def pdf_text(s):
    """Keep characters the built-in PDF fonts can draw (cp1252); transliterate the rest (e.g. c-caron -> c)."""
    out = []
    for ch in str(s if s is not None else ""):
        try: ch.encode("cp1252"); out.append(ch)
        except UnicodeEncodeError:
            out.append(unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode() or "?")
    return "".join(out)


def album_sections(rows):
    """[(series, set, [rows])]: every card of a set together, sets ordered by their first release date."""
    groups = {}
    for r in rows: groups.setdefault((r["_s"]["series"] or "", r["_s"]["set"]), []).append(r)
    secs = []
    for (series, name), rs in groups.items():
        rs.sort(key=lambda r: (r["_s"]["date"] or "", r["_s"]["row"]))
        secs.append([series, name, rs])
    secs.sort(key=lambda s: (min((r["_s"]["issued"] or "9999") for r in s[2]), s[0], s[1].lower()))
    return secs


def cmd_album(a):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.units import mm, inch
        from reportlab.lib.utils import ImageReader
    except ImportError:
        sys.exit("The album needs reportlab: python -m pip install -r requirements.txt")
    from PIL import Image
    rows = sort_rows(load_model())
    def has(val, *fields):
        return not val or any(val.lower() in str(f or "").lower() for f in fields)
    rows = [r for r in rows if has(a.set, r["_s"]["set"], r["_s"]["list_set"]) and has(a.series, r["_s"]["series"])
            and has(a.player, r["_s"]["player"]) and has(a.team, r["_s"]["team"], r["team"])]
    if a.at_risk: rows = [r for r in rows if r.get("ipfs_missing")]
    rows = mine_only(rows)
    if not rows: sys.exit("No highlights match those filters.")
    if any(not cover_path(r) for r in rows) and not OFFLINE:
        p("Some covers aren't downloaded yet; fetching them first (IPFS first). Use --offline to skip."); cmd_covers(a, rows)
    secs = album_sections(rows)
    cols, rws = {"1up": (1, 1), "2x2": (2, 2), "3x3": (3, 3)}[a.layout]; per = cols * rws
    TW, TH = A4 if a.page == "a4" else letter            # trim size
    BL = 3 * mm if a.bleed else 0                         # bleed on each side
    M = 0.5 * inch                                        # safe margin inside trim
    # --- page plan: cover, TOC, then per section a title page + card pages
    toc_lines = []
    for s in secs: toc_lines += ([("series", s[0])] if not toc_lines or s[0] != prev_series else []) + [("set", s)]; prev_series = s[0]
    toc_per_page = int((TH - 2 * M - 70) // 15)
    toc_pages = max(1, -(-len(toc_lines) // toc_per_page))
    page = 1 + toc_pages + 1; start = {}
    for s in secs:
        start[id(s)] = page; page += 1 + -(-len(s[2]) // per)
    total_pages = page - 1
    out = os.path.abspath(a.out or os.path.join(OUT, "my_album.pdf" if MINE is not None else "album.pdf")); os.makedirs(os.path.dirname(out), exist_ok=True)
    c = canvas.Canvas(out, pagesize=(TW + 2 * BL, TH + 2 * BL), pageCompression=1)
    c.setTitle("Breakaway Highlights Album"); c.setAuthor("breakaway-data (unofficial fan archive)")
    state = {"n": 0}

    def crop_marks():
        if not BL: return
        c.setLineWidth(0.25); c.setStrokeColorRGB(0, 0, 0); L = 6 * mm
        for x in (BL, BL + TW):
            for y in (BL, BL + TH):
                dx = -1 if x == BL else 1; dy = -1 if y == BL else 1
                c.line(x + dx * 1 * mm, y, x + dx * (1 * mm + L), y)   # horizontal mark outside trim
                c.line(x, y + dy * 1 * mm, x, y + dy * (1 * mm + L))   # vertical mark outside trim

    def begin():
        state["n"] += 1; c.translate(BL, BL)   # draw in trim coordinates

    def end(number=True):
        if number:
            c.setFont("Helvetica", 8); c.setFillGray(0.4)
            c.drawCentredString(TW / 2, M / 2, f"{state['n']}")
        c.translate(-BL, -BL); crop_marks(); c.showPage()

    def wrap(text, font, size, width):
        words, lines, cur = pdf_text(text).split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if c.stringWidth(t, font, size) <= width: cur = t
            else: lines.append(cur); cur = w
        if cur: lines.append(cur)
        return lines

    def fit(text, font, size, width):
        t = pdf_text(text)
        while t and c.stringWidth(t, font, size) > width: t = t[:-2] + "…" if len(t) > 2 else ""
        return t

    # cover
    begin(); c.setFillGray(0.08); c.rect(-BL, -BL, TW + 2 * BL, TH + 2 * BL, stroke=0, fill=1)
    c.setFillGray(1); c.setFont("Helvetica-Bold", 34); c.drawCentredString(TW / 2, TH * 0.62, "Breakaway Highlights Album")
    c.setFont("Helvetica", 16)
    c.drawCentredString(TW / 2, TH * 0.62 - 40, f"{len(rows):,} highlights · {len(secs)} sets")
    first = min((r["_s"]["issued"] for r in rows if r["_s"]["issued"]), default=""); last = max((r["_s"]["issued"] for r in rows if r["_s"]["issued"]), default="")
    if first: c.drawCentredString(TW / 2, TH * 0.62 - 62, f"Released {first[:7]} to {last[:7]}")
    c.setFont("Helvetica", 7); c.setFillGray(0.75); y = M + 30
    for ln in reversed(wrap(DISCLAIMER + " " + WARRANTY, "Helvetica", 7, TW - 2 * M)): c.drawCentredString(TW / 2, y, ln); y += 9
    end(number=False)
    # table of contents
    for tp in range(toc_pages):
        begin(); c.setFillGray(0); c.setFont("Helvetica-Bold", 20)
        c.drawString(M, TH - M - 10, "Contents" + (" (continued)" if tp else ""))
        y = TH - M - 50
        for kind, v in toc_lines[tp * toc_per_page:(tp + 1) * toc_per_page]:
            if kind == "series":
                c.setFont("Helvetica-Bold", 11); c.setFillGray(0.2); c.drawString(M, y, pdf_text(v or "Other"))
            else:
                c.setFont("Helvetica", 10); c.setFillGray(0)
                label = fit(f"{v[1]}  ({len(v[2])})", "Helvetica", 10, TW - 2 * M - 60)
                c.drawString(M + 14, y, label); c.drawRightString(TW - M, y, str(start[id(v)]))
                lw = c.stringWidth(label, "Helvetica", 10); c.setDash(1, 2); c.setStrokeGray(0.7)
                c.line(M + 18 + lw, y + 2, TW - M - 24, y + 2); c.setDash()
            y -= 15
        end()
    # sections
    max_px = a.max_px
    def image_for(path):
        if not max_px and not a.jpeg: return ImageReader(path)
        im = Image.open(path).convert("RGB")
        if max_px: im.thumbnail((max_px, max_px))
        b = io.BytesIO(); im.save(b, "JPEG", quality=a.jpeg or 88, optimize=True); b.seek(0)
        return ImageReader(b)
    done = 0
    for s in secs:
        series, setname, rs = s
        # set title page
        begin(); c.setFillGray(0)
        c.setFont("Helvetica", 12); c.setFillGray(0.35); c.drawCentredString(TW / 2, TH * 0.66, pdf_text(series))
        c.setFillGray(0); c.setFont("Helvetica-Bold", 28)
        for i, ln in enumerate(wrap(setname, "Helvetica-Bold", 28, TW - 2 * M)): c.drawCentredString(TW / 2, TH * 0.6 - i * 34, ln)
        mix = {}
        for r in rs: mix[r["_s"]["rarity"] or "?"] = mix.get(r["_s"]["rarity"] or "?", 0) + 1
        c.setFont("Helvetica", 13)
        c.drawCentredString(TW / 2, TH * 0.47, f"{len(rs)} highlight{'s' if len(rs) != 1 else ''}")
        c.drawCentredString(TW / 2, TH * 0.47 - 20, pdf_text(" · ".join(f"{k} {v}" for k, v in sorted(mix.items(), key=lambda x: -x[1]))))
        rel = rs[0]["_s"]["issued"]
        if rel: c.setFillGray(0.35); c.drawCentredString(TW / 2, TH * 0.47 - 40, f"Released {rel}")
        desc = re.sub(r"<[^>]+>", " ", html.unescape(((rs[0]["_off"] or {}).get("token_set") or {}).get("description") or ""))
        if desc.strip():
            c.setFont("Helvetica-Oblique", 9); c.setFillGray(0.3); y = TH * 0.47 - 75
            for ln in wrap(desc, "Helvetica-Oblique", 9, TW - 3 * M)[:12]: c.drawCentredString(TW / 2, y, ln); y -= 12
        end()
        # card pages
        fs = {1: 12, 2: 9, 3: 7}[cols]; lh = fs * 1.3; textblock = (5 if MINE is not None else 4) * lh + 8
        gw, gh = TW - 2 * M, TH - 2 * M - 22; cw, ch = gw / cols, gh / rws; pad = 8
        for i0 in range(0, len(rs), per):
            begin(); c.setFillGray(0.4); c.setFont("Helvetica", 8)
            c.drawString(M, TH - M - 8, fit(f"{series} · {setname}", "Helvetica", 8, TW - 2 * M))
            for j, r in enumerate(rs[i0:i0 + per]):
                s_ = r["_s"]; col, row = j % cols, j // cols
                x0 = M + col * cw + pad; y_top = TH - M - 22 - row * ch - pad; w = cw - 2 * pad; h = ch - 2 * pad
                ih = h - textblock; cp = cover_path(r)
                if cp:
                    iw0, ih0 = Image.open(cp).size; sc = min(w / iw0, ih / ih0); dw, dh = iw0 * sc, ih0 * sc
                    c.drawImage(image_for(cp), x0 + (w - dw) / 2, y_top - dh, dw, dh)
                    yt = y_top - dh - lh
                else:
                    c.setStrokeGray(0.7); c.rect(x0, y_top - ih, w, ih); yt = y_top - ih - lh
                c.setFillGray(0); c.setFont("Helvetica-Bold", fs + 1)
                c.drawString(x0, yt, fit(s_["player"], "Helvetica-Bold", fs + 1, w - 40))
                c.setFont("Helvetica-Bold", fs); c.setFillGray(0.45)
                c.drawRightString(x0 + w, yt, f"#{s_['row']}")
                c.setFillGray(0.15); c.setFont("Helvetica", fs)
                for k, ln in enumerate((s_["team"], " · ".join(x for x in (s_["date"], s_["play"]) if x),
                                        (f"{s_['rarity']} · edition size {s_['editions']:,}" if isinstance(s_["editions"], int) else f"{s_['rarity']} · edition size {s_['editions']}") if s_["editions"] else s_["rarity"])):
                    c.drawString(x0, yt - (k + 1) * lh, fit(ln, "Helvetica", fs, w))
                if MINE is not None:   # one short line; the full list is in the "My serials" pages at the end
                    eds = MINE.get(str(r["id"])) or []
                    c.setFont("Helvetica-Bold", fs); c.setFillColorRGB(0.55, 0.38, 0)
                    c.drawString(x0, yt - 4 * lh, fit(owned_short(eds), "Helvetica-Bold", fs, w))

            done += len(rs[i0:i0 + per]); end()
        p(f"  {setname}: {len(rs)} cards ({done}/{len(rows)})")
    if MINE is not None and any(MINE.get(str(r["id"])) for r in rows):
        # "My serials": every edition number per moment, small and in columns, so nothing is lost on the cards
        fsz, lhh, ncol, gap = 7, 8.6, 2, 14; colw = (TW - 2 * M - gap * (ncol - 1)) / ncol
        blocks = []
        for r in rows:
            eds = MINE.get(str(r["id"])) or []
            if not eds: continue
            s_ = r["_s"]; head = fit(f"{s_['player']} - {s_['set']} ({len(eds)})", "Helvetica-Bold", fsz, colw)
            blocks.append([("b", head)] + [("t", ln) for ln in wrap(", ".join(f"#{e}" for e in eds), "Helvetica", fsz, colw - 6)])
        top, bottom = TH - M - 40, M + 14; col = 0; y = None; pages = 0
        def new_page():
            nonlocal y, col, pages
            if pages: end()
            begin(); pages += 1; col = 0; y = top; c.setFillGray(0); c.setFont("Helvetica-Bold", 16)
            c.drawString(M, TH - M - 14, "My serials" + (" (continued)" if pages > 1 else ""))
            c.setFont("Helvetica", 8); c.setFillGray(0.4)
            c.drawString(M, TH - M - 28, f"Every edition number from your list, lowest first: {sum(len(v) for v in MINE.values()):,} editions across {sum(1 for r in rows if MINE.get(str(r["id"]))):,} moments.")
        new_page()
        for b in blocks:
            need = len(b) * lhh + 3
            if y - need < bottom and y != top:
                col += 1; y = top
                if col >= ncol: new_page()
            x = M + col * (colw + gap)
            for kind, ln in b:
                if y < bottom:
                    col += 1; y = top
                    if col >= ncol: new_page()
                    x = M + col * (colw + gap)
                c.setFont("Helvetica-Bold" if kind == "b" else "Helvetica", fsz); c.setFillGray(0 if kind == "b" else 0.25)
                c.drawString(x + (0 if kind == "b" else 6), y, ln); y -= lhh
            y -= 3
        end(); total_pages += pages
    c.save()
    p(f"Album: {out}  ({total_pages} pages, {os.path.getsize(out)/1e6:.1f} MB, layout {a.layout}, {a.page}{', bleed+crop marks' if BL else ''})")



CONFIG_KEYS = {   # breakaway.config.json key -> argparse dest (a flag on the command line always wins)
    "gateways": "gateway", "concurrency": "concurrency", "media_concurrency": "media_concurrency",
    "ipfs_concurrency": "ipfs_concurrency", "output_dir": "output_dir", "video_dir": "video_dir",
    "viewer_dir": "viewer_dir", "ipfs_only": "ipfs_only", "cdn_first": "cdn_first", "offline": "offline",
    "issues_url": "issues_url",
}
DEFAULTS = {"gateway": [], "concurrency": 6, "media_concurrency": 2, "ipfs_concurrency": 2, "output_dir": "output",
            "video_dir": None, "viewer_dir": "viewer", "ipfs_only": False, "cdn_first": False, "offline": False,
            "issues_url": None}
COMMANDS = ["all", "fetch", "covers", "build", "package", "videos", "verify", "add", "view", "album", "check-ipfs", "pin",
            "check-live", "health"]


def main(argv=None):
    global THR, GATEWAYS, IPFS_ONLY, CDN_FIRST, OFFLINE, OUT, MEDIA_CONC, ISSUES_URL
    ap = argparse.ArgumentParser(description="breakaway-data: NHL Breakaway highlight archive",
                                 epilog="Settings can also go in breakaway.config.json (see breakaway.config.example.json).")
    ap.add_argument("--version", action="version", version=f"Breakaway Archive v{VERSION}")
    ap.add_argument("command", choices=COMMANDS)
    ap.add_argument("refs", nargs="*", help="add: NHL Breakaway URLs or seriesId/tokenId")
    g = ap.add_argument_group("general")
    g.add_argument("--config", help="settings file (default: breakaway.config.json next to this script, if present)")
    g.add_argument("--output-dir", default=None, help="where generated files go (default output/)")
    g.add_argument("--offline", action="store_true", default=None, help="never use the network; work from local files only")
    g.add_argument("--concurrency", type=int, default=None, help="parallel metadata requests to NHL Breakaway (1-8, default 6)")
    g.add_argument("--media-concurrency", type=int, default=None, help="parallel cover/video downloads (1-4, default 2)")
    g.add_argument("--ipfs-concurrency", type=int, default=None, help="check-ipfs: parallel checks (1-6, default 2)")
    g.add_argument("--gateway", action="append", default=None, help="IPFS gateway to try first (repeatable), e.g. https://ipfs.io/ipfs/")
    g.add_argument("--ipfs-only", action="store_true", default=None, help="covers/videos: IPFS gateways only, never the NHL Breakaway CDN")
    g.add_argument("--cdn-first", action="store_true", default=None, help="covers/videos: try the CDN before IPFS (faster, but videos come re-encoded)")
    g.add_argument("--ids", help="comma-separated card IDs (the id in data/highlights.json)")
    g.add_argument("--series", help='only this series, e.g. "Series 3"')
    g.add_argument("--set", help="only sets whose name contains this")
    g.add_argument("--player", help="only this player (name contains)")
    g.add_argument("--team", help="only this team (name contains)")
    g.add_argument("--limit", type=int, help="videos/pin: at most N; fetch --discover: add at most N")
    g.add_argument("--yes", action="store_true", help="don't ask before downloading or pinning")
    f = ap.add_argument_group("fetch")
    f.add_argument("--refresh", action="store_true", help="fetch: re-download metadata (all, or just --ids); check-ipfs: re-check recent ones")
    f.add_argument("--discover", action="store_true", help="fetch: also add moments from NHL Breakaway set listings that aren't in the card list")
    m = ap.add_argument_group("covers / videos / verify / view")
    m.add_argument("--video-dir", "--out-dir", dest="video_dir", default=None, help="where videos are saved (default <output>/videos)")
    m.add_argument("--repair", action="store_true", help="covers/videos: replace files that don't match the original sha256 with the IPFS original")
    m.add_argument("--viewer-dir", default=None, help="view: where index.html goes (default viewer/)")
    c = ap.add_argument_group("check-ipfs / pin")
    c.add_argument("--sample", type=int, default=200, help="check-ipfs: how many CIDs to sample (default 200)")
    c.add_argument("--recheck", action="store_true", help="check-ipfs: retry only the unreachable ones on up to 4 gateways (uncached vs gone)")
    c.add_argument("--no-cdn", action="store_true", help="check-live: only check the set listings, not the CDN")
    g.add_argument("--mine", nargs="?", const=MINE_DEFAULT, default=None, metavar="PATH",
                   help="covers/videos/build/view/album/pin: only the cards in your own list (default my_cards.txt; read locally, never sent anywhere)")
    g.add_argument("--at-risk", action="store_true", help="covers/videos/pin/album: only moments whose originals are missing on IPFS (data/at_risk.md)")
    c.add_argument("--full", action="store_true", help="check-ipfs: check every CID (13k+, takes hours)")
    c.add_argument("--seed", type=int, default=1, help="check-ipfs: sample seed (same seed = same sample)")
    c.add_argument("--max-age", type=float, default=30, help="check-ipfs: skip CIDs checked within this many days")
    c.add_argument("--types", help="pin / check-ipfs --recheck: only these file types, e.g. video,cover (types: " + ", ".join(TYPE_ORDER) + ")")
    c.add_argument("--kubo", action="store_true", help="pin: pin on your own IPFS (Kubo) node with `ipfs pin add`")
    c.add_argument("--service", help="pin: pinata | filebase | <Pinning Service API URL>; token in PIN_SERVICE_TOKEN")
    al = ap.add_argument_group("album")
    al.add_argument("--layout", choices=["1up", "2x2", "3x3"], default="2x2", help="album: cards per page")
    al.add_argument("--page", choices=["letter", "a4"], default="letter", help="album: paper size")
    al.add_argument("--bleed", action="store_true", help="album: add 3 mm bleed and crop marks for print shops")
    al.add_argument("--out", help="album: output PDF path (default <output>/album.pdf)")
    al.add_argument("--max-px", type=int, default=0, help="album: downscale covers to this many pixels (smaller PDF)")
    al.add_argument("--jpeg", type=int, default=0, help="album: re-encode covers as JPEG at this quality (e.g. 80)")
    ap.add_argument("--ask", action="store_true", help=argparse.SUPPRESS)   # menu: confirm before big downloads
    a = ap.parse_args(argv)
    cfg_path = a.config or os.path.join(ROOT, "breakaway.config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        cfg = jload(cfg_path, {}) or {}
        unknown = set(cfg) - set(CONFIG_KEYS) - {"_comment"}
        if unknown: p(f"Note: {os.path.basename(cfg_path)} has unknown keys {sorted(unknown)} (ignored)")
    elif a.config: sys.exit(f"Config file not found: {a.config}")
    for dest in ("output_dir", "video_dir", "viewer_dir"):   # command-line paths are relative to where you run it
        if getattr(a, dest): setattr(a, dest, os.path.abspath(getattr(a, dest)))
    for key, dest in CONFIG_KEYS.items():
        if getattr(a, dest, None) is None: setattr(a, dest, cfg.get(key, DEFAULTS[dest]))
    for dest in ("output_dir", "video_dir", "viewer_dir"):   # config/default paths are relative to this folder
        if getattr(a, dest) and not os.path.isabs(getattr(a, dest)): setattr(a, dest, os.path.join(ROOT, getattr(a, dest)))
    for dest, v in DEFAULTS.items():
        if getattr(a, dest, None) is None: setattr(a, dest, v)
    if isinstance(a.gateway, str): a.gateway = [a.gateway]
    OUT = a.output_dir
    if not a.video_dir: a.video_dir = os.path.join(OUT, "videos")
    THR = Throttle(max(1, min(int(a.concurrency), 8))); MEDIA_CONC = max(1, min(int(a.media_concurrency), 4))
    a.ipfs_concurrency = max(1, min(int(a.ipfs_concurrency), 6))
    user_gw = [x if x.rstrip("/").endswith("/ipfs") or x.endswith("/ipfs/") else x.rstrip("/") + "/ipfs/" for x in a.gateway]
    GATEWAYS = list(dict.fromkeys([x.rstrip("/") + "/" for x in user_gw] + DEFAULT_GATEWAYS))
    IPFS_ONLY, CDN_FIRST, OFFLINE = bool(a.ipfs_only), bool(a.cdn_first), bool(a.offline)
    if a.issues_url: ISSUES_URL = a.issues_url
    global MINE
    MINE = None
    if a.mine is not None and a.command in ("covers", "videos", "build", "view", "album", "pin"):
        path = a.mine if os.path.isabs(a.mine) or os.path.exists(a.mine) else os.path.join(ROOT, a.mine)
        if a.mine == MINE_DEFAULT and not os.path.exists(path) and os.path.exists(os.path.join(ROOT, "my_cards.csv")):
            path = os.path.join(ROOT, "my_cards.csv")   # The Fifth Line export
        MINE, _ = load_mine(path)
    if OFFLINE and (a.command in ("fetch", "add", "videos", "check-ipfs", "all", "covers") or (a.command == "pin" and (a.kubo or a.service))):
        sys.exit(f"`{a.command}` needs the network; drop --offline.")
    if a.command in ("fetch", "all"): cmd_fetch(a)
    if a.command in ("covers", "all") and not OFFLINE: cmd_covers(a)
    if a.command in ("build", "all"): cmd_build(a)
    if a.command in ("package", "all"): cmd_package(a)
    {"videos": cmd_videos, "verify": cmd_verify, "add": cmd_add, "view": cmd_view, "album": cmd_album,
     "check-ipfs": cmd_check_ipfs, "pin": cmd_pin, "check-live": cmd_check_live, "health": cmd_health}.get(a.command, lambda a: None)(a)


# ------------------------------------------------------------------ interactive menu (no arguments)
MENU = """
  1) Get cover art
  2) Get videos (for a player, team or set)
  3) Build the spreadsheet (highlights.xlsx)
  4) Open the viewer (browse everything in your web browser)
  5) Make a printable album (PDF)
  6) Add a missing moment (paste its NHL Breakaway link)
  7) Check my downloaded files (verify)
  8) Help keep the files alive (IPFS pinning)
  9) Check which IPFS files are still online (quick sample)
 10) Show only my cards (uses your my_cards.csv or my_cards.txt)
  0) Quit"""


def refresh_viewer():
    """viewer/index.html is made by the app, not shipped in the zip, so an upgrade would leave an old copy behind
    (people often open it directly). Rebuild it quietly when it was made by another version."""
    vp = os.path.join(ROOT, "viewer", "index.html")
    if not os.path.exists(vp): return
    try:
        with open(vp, encoding="utf-8", errors="replace") as f: page = f.read()
    except OSError: return
    if f'content="Breakaway Archive v{VERSION}"' in page[:2000]: return
    argv = ["view", "--offline"]
    if '"mine": true' in page:   # it was made with "Show only my cards": keep that if the list is still here
        mine = next((os.path.join(ROOT, f) for f in ("my_cards.txt", "my_cards.csv") if os.path.exists(os.path.join(ROOT, f))), None)
        if mine: argv += ["--mine", mine]
    p(f"Updating your viewer (viewer/index.html) to v{VERSION}...")
    run(argv)


def ask(q, default=""):
    try: v = input(f"{q}{f' [{default}]' if default else ''}: ").strip()
    except EOFError: v = ""
    return v or default


def yes(q, default=False):
    v = ask(q + (" (Y/n)" if default else " (y/N)")).lower()
    return default if not v else v in ("y", "yes")


def ask_filter(what="highlights"):
    p(f"Which {what}?  1) everything  2) one player  3) one team  4) one set  5) one series")
    c = ask("Choose", "1")
    key = {"2": ("--player", "Player name (or part of it)"), "3": ("--team", "Team name (or part of it)"),
           "4": ("--set", "Set name (or part of it)"), "5": ("--series", 'Series, e.g. "Series 1"')}.get(c)
    if not key: return []
    v = ask(key[1])
    return [key[0], v] if v else []


def run(argv):
    try: main(argv); return True
    except SystemExit as e:
        if e.code not in (None, 0): p(f"Stopped: {e.code}")
    except KeyboardInterrupt: p("" if STOP.is_set() else "\nCancelled.")
    except Exception as e: p(f"Something went wrong: {type(e).__name__}: {e}")
    return False


def menu():
    p(f"Breakaway Archive v{VERSION}: NHL Breakaway highlight archive (unofficial fan preservation tool)")
    p(TAGLINE)
    p(WARRANTY + " Personal archival use only.")
    p(f"Files are saved in: {OUT}")
    p("Covers and videos you saved with the viewer's Download buttons are picked up from your Downloads folder automatically.")
    try: import_downloads()
    except Exception as e: p(f"(Couldn't check Downloads: {e})")
    refresh_viewer()
    while True:
        p(MENU); c = ask("Type a number and press Enter")
        if c in ("0", "q", "quit", "exit", ""):
            if c == "" and not yes("Quit?", True): continue
            return
        if c == "1":
            run(["covers", "--ask", *ask_filter("covers")])
        elif c == "2":
            f = ask_filter("videos")
            if not f: p("Tip: all videos are several hundred GB. Picking a player, team or set is much smaller.")
            run(["videos", *f])   # shows the estimated size and asks before downloading
        elif c == "3":
            run(["build"])
        elif c == "4":
            if run(["view"]):
                import webbrowser
                path = os.path.join(ROOT, "viewer", "index.html"); p(f"Opening {path}")
                webbrowser.open("file://" + os.path.abspath(path).replace(os.sep, "/"))
        elif c == "5":
            f = ask_filter("highlights for the album")
            lay = {"1": "1up", "2": "2x2", "3": "3x3"}.get(ask("Cards per page: 1) one big  2) four (2x2)  3) nine (3x3)", "2"), "2x2")
            page = "a4" if ask("Paper: 1) Letter  2) A4", "1") == "2" else "letter"
            extra = ["--bleed"] if yes("Is this for a print shop (adds bleed and crop marks)?") else []
            if run(["album", "--layout", lay, "--page", page, *extra, *f, "--ask"]):
                p(f"Your album is in {os.path.join(OUT, 'album.pdf')}")
        elif c == "6":
            p("Paste one or more NHL Breakaway links (like https://nhlbreakaway.com/series/XXXX/1234...), separated by spaces.")
            refs = ask("Links").split()
            if refs: run(["add", *refs])
        elif c == "7":
            run(["verify"])
        elif c == "8":
            p("Pinning keeps a copy of the original files on IPFS so they stay online. Nothing is pinned unless you choose to.\n"
              "  1) Just write the lists of CIDs (no upload)\n  2) Pin on my own IPFS node (Kubo installed)\n"
              "  3) Pin with a pinning service (Pinata or Filebase; your token in PIN_SERVICE_TOKEN)")
            m = ask("Choose", "1"); f = ask_filter("files"); t = ask("Only some file types? e.g. video,cover (Enter = all)")
            argv = ["pin", *f, *(["--types", t] if t else [])]
            if m == "2": argv.append("--kubo")
            elif m == "3": argv += ["--service", ask("Service: pinata or filebase", "pinata")]
            run(argv)
        elif c == "10":
            dflt = os.path.join(ROOT, MINE_DEFAULT)
            p(f"""SHOW ONLY MY CARDS (optional). Your list stays on this computer; it is never uploaded or sent anywhere.
  Step 1 - get your export: open https://thefifthlinecode.onrender.com, search your wallet address to open
    your portfolio, optionally filter by player, then click "Export my cards" (next to Compress) to download
    my_cards.csv.
  Step 2 - put my_cards.csv in this folder: {ROOT}
  The Fifth Line lists most moments (~1,800 of ~1,970), so the export is a head start, not a must:
    add any missing cards to the same file, one line each with the card's NHL Breakaway link or
    seriesId/tokenId. A moment missing from the archive itself can be added with option 6.
  No export? Make a plain text file my_cards.txt here instead, one card per line: a card number
    from this archive (like 22) or the card's NHL Breakaway link.
  Doesn't work? Check the file is in the folder above, not renamed (or type its path below),
    and not empty (export again without a player filter).
""")
            csvp = os.path.join(ROOT, "my_cards.csv")
            path = ask("Your list (press Enter for this one)", dflt if os.path.exists(dflt) else (csvp if os.path.exists(csvp) else dflt))
            if not os.path.exists(path): p("Couldn't find that file yet. Make it, then choose 10 again."); ask("\nPress Enter to go back to the menu"); continue
            what = ask("Now make: 1) album  2) viewer  3) spreadsheet  4) get covers  5) get videos", "1")
            cmd = {"1": "album", "2": "view", "3": "build", "4": "covers", "5": "videos"}.get(what, "album")
            if run([cmd, "--mine", path]) and cmd == "view":
                import webbrowser
                webbrowser.open("file://" + os.path.abspath(os.path.join(ROOT, "viewer", "index.html")).replace(os.sep, "/"))
        elif c == "9":
            run(["check-ipfs", "--sample", ask("How many to check", "100")])
        else:
            p("Please type a number from the list."); continue
        ask("\nPress Enter to go back to the menu")


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):   # a Windows console or pipe in cp1252 must never crash on a name like "Dvořák"
        try: _s.reconfigure(errors="replace")
        except Exception: pass
    if len(sys.argv) == 1:      # double-clicked or run with no arguments: friendly menu
        try: menu()
        except KeyboardInterrupt: pass
    else:
        try: main()
        except KeyboardInterrupt: sys.exit(130)   # Ctrl+C: the progress summary already said where it stopped

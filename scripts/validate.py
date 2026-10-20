#!/usr/bin/env python3
"""Validates data/highlights.json, data/manifest.json and data/extra_moments.txt (used by CI on PRs)."""
import hashlib, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(ROOT, "data")
errs = []
def err(m): errs.append(m)
try: rows = json.load(open(os.path.join(D, "highlights.json"), encoding="utf-8"))
except Exception as e: rows = []; err(f"highlights.json is not valid JSON: {e}")
ids = [str(r.get("id")) for r in rows]
if len(ids) != len(set(ids)): err("highlights.json has duplicate ids")
for r in rows:
    for k in ("id", "player", "set"):
        if k not in r: err(f"highlights.json row missing '{k}': {r}")
    if not isinstance(r.get("id"), int): err(f"highlights.json id is not an integer card id: {r.get('id')}")
    if r.get("site_url") and not r.get("on_site", True): err(f"id {r.get('id')}: has site_url but on_site is false")
try: man = json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8"))
except Exception as e: man = {}; err(f"manifest.json is not valid JSON: {e}")
uu = {}
for k, e in man.items():
    if k not in set(ids): err(f"manifest id {k} not in highlights.json")
    fp = os.path.join(D, "meta", f"{k}.json")
    if e.get("status") == 200:
        if not os.path.exists(fp): err(f"missing data/meta/{k}.json"); continue
        if hashlib.sha256(open(fp, "rb").read()).hexdigest() != e.get("sha256"): err(f"sha256 mismatch for data/meta/{k}.json")
    u = e.get("moment_uuid")
    if not u: err(f"manifest {k} has no moment_uuid")
    if u and u in uu: err(f"duplicate moment {u}: ids {uu[u]} and {k}")
    if u: uu[u] = k
    if os.path.exists(fp):
        try: mu = {t["name"]: t["value"] for t in json.load(open(fp, encoding="utf-8")).get("attributes", [])}.get("Moment UUID")
        except Exception: mu = None; err(f"data/meta/{k}.json is not valid JSON")
        if mu and mu != u: err(f"data/meta/{k}.json has Moment UUID {mu} but manifest says {u}")
missing = set(ids) - set(man)
if missing: err(f"{len(missing)} highlight(s) have no manifest entry, e.g. {sorted(missing)[:3]}")
try: links = json.load(open(os.path.join(D, "links.json"), encoding="utf-8"))
except Exception as e: links = {}; err(f"links.json is not valid JSON: {e}")
if set(links) != set(ids): err(f"links.json keys differ from highlights.json ids ({len(set(links) ^ set(ids))} differ)")
tok = {}
for k, ln in links.items():
    t = (ln.get("series_id"), int(ln.get("token_id", 0)) >> 48)
    if t in tok: err(f"duplicate token {t[0]}/{ln.get('token_id')}: {tok[t]} and {k}")
    tok[t] = k
metas = {f[:-5] for f in os.listdir(os.path.join(D, "meta")) if f.endswith(".json")} if os.path.isdir(os.path.join(D, "meta")) else set()
if metas - set(ids): err(f"{len(metas - set(ids))} stray file(s) in data/meta, e.g. {sorted(metas - set(ids))[:3]}")
pat = re.compile(r"^((https?://)?(nft\.)?nhlbreakaway\.com/series/[A-Za-z0-9]{6,12}/\d{6,}/?|[A-Za-z0-9]{6,12}/\d{6,})$")
xp = os.path.join(D, "extra_moments.txt")
if os.path.exists(xp):
    for n, line in enumerate(open(xp, encoding="utf-8"), 1):
        s = line.strip()
        if s and not s.startswith("#") and not pat.match(s): err(f"extra_moments.txt line {n} is not a Breakaway link: {s}")
for m in errs[:100]: print("ERROR:", m)
print(f"{len(rows)} highlights, {len(man)} manifest entries, {len(errs)} problem(s)")
sys.exit(1 if errs else 0)

#!/usr/bin/env python3
"""Builds site/data/moments.json, the compact data file used by the static community site in site/, and
site/data/hall.json, the Collector Hall entries compiled from collections/ (see scripts/hall.py).

It reads the archive the same way breakaway.py does (data/highlights.json, data/manifest.json, data/meta/,
data/offchain/, data/links.json) and keeps only what the museum and the collector showcase need. No media is
copied: the site links to the Internet Archive copies (data/archive_urls.json), the NHL Breakaway CDN and the
public IPFS gateways.

    python scripts/build_site.py
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import breakaway as b  # noqa: E402  (read-only use of the app's loaders, nothing is written by it)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import hall  # noqa: E402

OUT_DIR = os.path.join(ROOT, "site", "data")
CHUNK = 100
NFT = "https://nft.nhlbreakaway.com/series/"
MG = "https://mediagateway.sweet.io/media/token/"
IA = "https://archive.org/"
IAP = "nhl-breakaway-moments-"   # shared item-name prefix, kept once in moments.json


def money(v):
    m = re.search(r"[\d,]+(?:\.\d+)?", str(v or ""))
    return round(float(m.group(0).replace(",", "")), 2) if m else None


def short(u, pre):
    return u[len(pre):] if u and u.startswith(pre) else (u or "")


def thumb(meta, size="500"):
    t = (((meta or {}).get("images") or {}).get("front") or {}).get("thumbnail") or {}
    x = t.get(size) or t.get("350") or {}
    return x.get("url", ""), b.clean_cid((x.get("altloc") or {}).get("ipfs", ""))


def main():
    rows = b.sort_rows(b.load_model())
    links = b.jload(os.path.join(b.DATA, "links.json"), {}) or {}
    archive = (b.jload(os.path.join(b.DATA, "archive_urls.json"), {}) or {}).get("moments", {})
    tables = {k: [] for k in ("team", "set", "series", "rarity")}

    def ix(k, v):
        t = tables[k]
        if v not in t: t.append(v)
        return t.index(v)

    core, detail = [], []
    for r in rows:
        s = r["_s"]; ln = links.get(str(r["id"])) or {}
        sid, tok = ln.get("series_id", ""), str(ln.get("token_id", ""))
        tu, tc = thumb(r["_meta"])
        cov = short(s["cover_url"], NFT); th = short(tu, NFT); vu = short(s["video_url"], MG)
        m = {
            "i": r["id"], "p": s["player"], "t": ix("team", s["team"] or ""), "s": ix("set", s["set"] or ""),
            "se": ix("series", s["series"] or ""), "r": ix("rarity", s["rarity"] or ""),
            "e": s["editions"] if isinstance(s["editions"], int) else None, "d": s["date"], "pl": s["play"],
            "fl": s["flags"], "la": money(s["lowest_ask"]), "fm": money(s["fmv"]),
            "k": [sid, tok] if sid and tok.isdigit() else None,      # NHL Breakaway series id + token id
            "c": cov, "tc": tc,                                      # cover thumbnail on IPFS (grid fallback)
            # thumbnail and CDN video follow a fixed pattern; spelled out only when they don't
            "th": th if th != cov.replace("front.png", "front-500x.png") else "",
            "vu": vu if vu != f"{sid}/{tok}/video.mp4" else "",
            "nv": 1 if not s["video_url"] else "",
            "f5": 1 if s["site_url"] else "",
            "h": s["ipfs_health"], "m": [x for x in (s["ipfs_missing"] or "").split(", ") if x],
            "ln": {"yes": 1, "no": 0}.get(s["listed_now"]), "u": 1 if s["status"] == "unverified" else "",
        }
        ia = archive.get(str(r["id"])) or {}                         # Internet Archive copies (path after IA/download/ + IAP)
        m["ia"] = short(ia.get("video", ""), IA + "download/" + IAP)
        m["ic"] = short(ia.get("cover", ""), IA + "download/" + IAP)
        core.append({k: v for k, v in m.items() if v not in ("", None, [])})
        x = {"i": r["id"], "ds": s["description"], "is": s["issued"], "pos": s["position"], "jn": s["jersey"],
             "pe": s["period"], "cl": s["clock"], "fs": s["final_score"], "v": s["venue"], "tg": s["tagline"],
             "au": s["audio"], "ci": b.clean_cid(s["cover_ipfs"]), "vi": b.clean_cid(s["video_ipfs"])}
        detail.append({k: v for k, v in x.items() if v not in ("", None, [])})
    nchunks = (len(detail) + CHUNK - 1) // CHUNK
    doc = {"v": 1, "nft": NFT, "mg": MG, "ia": IA, "iap": IAP, "gateways": b.DEFAULT_GATEWAYS, "price_snapshot": "Oct 2026",
           "chunk": CHUNK, "chunks": nchunks, "tables": tables, "moments": core}
    os.makedirs(os.path.join(OUT_DIR, "detail"), exist_ok=True)
    for fn in os.listdir(os.path.join(OUT_DIR, "detail")):
        if fn.endswith(".json"): os.remove(os.path.join(OUT_DIR, "detail", fn))
    dump = lambda o, path: json.dump(o, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    dump(doc, os.path.join(OUT_DIR, "moments.json"))
    for n in range(nchunks):   # details by position in moments.json, loaded only when a moment is opened
        dump(detail[n * CHUNK:(n + 1) * CHUNK], os.path.join(OUT_DIR, "detail", f"{n}.json"))
    kb = os.path.getsize(os.path.join(OUT_DIR, "moments.json")) // 1024
    print(f"wrote site/data/moments.json ({len(core)} moments, {kb} KB, {sum(1 for m in core if m.get('ia'))} with an "
          f"Internet Archive video) and {nchunks} detail files")
    entries, probs = hall.entries()
    for pr in probs: print("collector hall: skipped,", pr)
    entries.sort(key=lambda e: (not e["example"], e["updated"], e["h"]), reverse=True)   # newest first, examples last
    dump({"v": 1, "entries": entries}, os.path.join(OUT_DIR, "hall.json"))
    print(f"wrote site/data/hall.json ({len(entries)} collector{'s' if len(entries) != 1 else ''})")


if __name__ == "__main__":
    main()

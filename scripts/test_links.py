#!/usr/bin/env python3
"""Every IPFS link the tool generates must be exactly <gateway>/ipfs/<CID>[/path], with no spaces or sha256 text.

Checks the Python helpers on every CID in data/manifest.json, then builds the offline viewer into a temp folder
and checks its data, its gateway list and every literal IPFS URL in the page. If Node.js is installed, the
viewer's own cidOf()/ipfsUrl() JavaScript is run on every CID too. Exit code 1 on any problem."""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import breakaway as b   # noqa: E402

OK = re.compile(r"^https://[^/\s]+/ipfs/[A-Za-z0-9]+(/\S*)?$")
bad = []


def check(url, where):
    if not OK.match(url or ""): bad.append(f"{where}: {url!r}")


man = json.load(open(os.path.join(HERE, "data", "manifest.json"), encoding="utf-8"))
cids = sorted({e["ipfs"] for m in man.values() for e in (m.get("ipfs") or [])})
for c in cids:
    for g in b.DEFAULT_GATEWAYS: check(b.ipfs_url(g, c), f"python ipfs_url {c}")
# messy inputs seen in the wild
for raw in ("ipfs://QmAbc123  sha256=xyz=", " QmAbc123/a.png ", "/ipfs/QmAbc123", "ipfs://bafyAbc/dir/x.mp4\tsha"):
    check(b.ipfs_url(b.DEFAULT_GATEWAYS[0], raw), f"python ipfs_url {raw!r}")

tmp = tempfile.mkdtemp()
try:
    subprocess.run([sys.executable, os.path.join(HERE, "breakaway.py"), "view", "--offline", "--viewer-dir", tmp],
                   check=True, stdout=subprocess.DEVNULL)
    page = open(os.path.join(tmp, "index.html"), encoding="utf-8").read()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
data = json.loads(re.search(r"^const DATA = (.*);$", page, re.M).group(1))
gws = json.loads(re.search(r"^const GW = (.*);$", page, re.M).group(1))
for g in gws:
    if not re.match(r"^https://[^/\s]+/ipfs/$", g): bad.append(f"viewer gateway {g!r}")
vals = []
for r in data:
    s = r["s"]
    for k in ("cover_ipfs", "video_ipfs", "card_image_ipfs"):
        if s.get(k): vals.append((f"viewer {k} card {s['id']}", s[k]))
    for path, v in (r.get("ipfs") or {}).items():
        if not isinstance(v, dict) or " " in v.get("cid", ""): bad.append(f"viewer ipfs table card {s['id']} {path}: {v!r}")
        else: vals.append((f"viewer ipfs table card {s['id']} {path}", v["cid"]))
for where, c in vals:
    for g in gws: check(g.rstrip("/") + "/" + c, where)
for u in re.findall(r"https://[^\"'<>\s]+/ipfs/[^\"'<>]*", page):   # literal IPFS URLs anywhere in the page
    if u not in gws: check(u, "viewer page")   # the bare gateway bases themselves are fine
if shutil.which("node"):
    js = page[page.index("<script>") + 8: page.index("</script>")]
    fn = re.search(r"function cidOf\(c\)\{.*?\n", js).group(0) + re.search(r"function ipfsUrl\(cid,g\)\{.*?\n", js).group(0)
    prog = (f"const GW={json.dumps(gws)};{fn}const V={json.dumps([c for _, c in vals] + ['ipfs://QmAbc123  sha256=xyz='])};"
            "console.log(JSON.stringify(V.flatMap(c=>GW.map((g,i)=>ipfsUrl(c,i)))))")
    out = subprocess.run(["node", "-"], input=prog, capture_output=True, text=True, check=True).stdout
    for u in json.loads(out): check(u, "viewer JS ipfsUrl")
    print("viewer JS cidOf/ipfsUrl checked with Node.js")
print(f"{len(cids)} CIDs x {len(b.DEFAULT_GATEWAYS)} gateways (Python), {len(vals)} viewer CIDs x {len(gws)} gateways: "
      f"{len(bad)} bad IPFS URL(s)")
for x in bad[:30]: print("  BAD", x)
sys.exit(1 if bad else 0)

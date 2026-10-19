# breakaway-data

A preservation archive of NHL Breakaway digital highlight metadata, built from the 1,811 highlights
listed in the community card list (data/highlights.json).

NHL Breakaway may shut down, so the raw metadata is stored **in this repo, byte-for-byte as served**.
Everything else (the spreadsheet, cover art, videos) can be rebuilt from it.

## What's in the repo

| Path | What it is |
|---|---|
| `data/meta/<id>.json` | Raw response of `https://nft.nhlbreakaway.com/series/<series>/<token>` for each highlight (`<id>` = card id). It is JSON (`application/json`), not XML. |
| `data/manifest.json` | Per highlight: source URL, fetch time (UTC), HTTP status, bytes, sha256 of the stored file, moment UUID, how it was linked, off-chain file, and **every IPFS CID + sha256** found in its metadata (images and video). |
| `data/offchain/sets/<set_uuid>.json` | Raw NHL Breakaway set listings (`apigw.sweet.io/catalog/search/moment/set/...`): off-chain descriptions, game/play details, edition sizes, rarity, dates. |
| `data/offchain/setcompletion_826.json`, `collection_challenge_826.json` | Raw set-completion and quest data (set rewards, quest highlight lists). |
| `data/highlights.json` | The card list. |
| `data/links.json` | card id -> Breakaway series id + token id, and how each was found. |
| `data/cids.txt` | Every IPFS CID (cover images, posters, videos) referenced by the metadata, deduplicated, ready to pin. |
| `data/extra_moments.txt` | Anyone-editable list of extra NHL Breakaway links to add (see below). |
| `breakaway.py` | The tool. `export_highlights.py` is a shortcut for `breakaway.py all`. |
| `scripts/validate.py` | Format/integrity check run by CI on every pull request. |

Not committed (see `.gitignore`): `output/` (xlsx, covers, zips), `cache/`, videos.

## Quick start (non-technical)

1. Install Python 3 from https://www.python.org/downloads/ . On Windows tick **"Add Python to PATH"**.
2. Open a terminal in this folder (Windows: in File Explorer type `cmd` in the address bar and press Enter).
3. Run once: `pip install -r requirements.txt`
4. Build the spreadsheet from the saved data (works with no internet): `python breakaway.py build`
   -> `output/highlights.xlsx`
5. Optional, needs internet: `python breakaway.py all` to fetch anything new, download full-res covers
   and make `Breakaway-Highlights.zip`.

## Commands

```
python breakaway.py fetch   [--refresh] [--concurrency 6] [--no-crawl]
python breakaway.py covers  [--concurrency 6]        # full-res covers -> output/covers_full/, sha256-checked
python breakaway.py build                            # OFFLINE: data/ -> output/highlights.xlsx
python breakaway.py package                          # output/covers/, covers.zip, Breakaway-Highlights.zip
python breakaway.py all                              # fetch + covers + build + package
python breakaway.py videos  [--out-dir DIR] [--limit N] [--series "Series 3"] [--ids 12,40] [--yes]
python breakaway.py verify  [--out-dir DIR]          # re-hash data/meta, covers and videos vs stored sha256
python breakaway.py add     <url | seriesId/tokenId> ...   # also reads data/extra_moments.txt
python breakaway.py view    [--out-dir DIR]          # offline viewer/index.html
```

* `--gateway https://my-gateway/ipfs/` (repeatable) adds IPFS gateways to try first; built-in fallbacks are
  ipfs.io, dweb.link, w3s.link, gateway.pinata.cloud and 4everland.io. `--ipfs-only` skips
  mediagateway.sweet.io / nft.nhlbreakaway.com entirely (use this if NHL Breakaway goes offline).

* Re-runs only fetch what's new or missing. `--refresh` re-pulls everything.
* `--concurrency` (1-8, default 6) caps parallel requests to NHL Breakaway / its CDN. Requests retry with
  exponential backoff on 429/5xx/timeouts and slow down automatically when errors climb. 401/403/404 are
  never worked around.
* The card-list site was only hit once for the card list, plus (rarely) one card page at a time with a
  1 s pause when a highlight can't be matched from NHL Breakaway's own set listings.

### Videos (opt-in)

Videos are **off by default** and never downloaded by `all`. `python breakaway.py videos --out-dir videos`
estimates the total size with a few HEAD requests, then asks `y/n` (skip the question with `--yes`).
Downloads resume (`.part` files) and skip files that already exist. Try `--limit 5` first.

## Offline viewer

`python breakaway.py view` writes `viewer/index.html`, one self-contained file (no server, no CDN, opens from
`file://`). Search plus filters for team, set, rarity and series. Clicking a card shows every metadata field,
attributes, IPFS CIDs, sha256 and source URLs. It uses local covers and videos when you've downloaded them,
and falls back to the NHL Breakaway CDN and then to IPFS gateways when you're online.

## Keeping the archive alive

* **Keep a copy of the folder.** `data/` is the archive (about 46 MB). Clone or download this repo; add
  `output/` too if you downloaded covers/videos.
* **Pin the media on IPFS.** With an IPFS node (https://docs.ipfs.tech/install/):
  `grep -v '^#' data/cids.txt | cut -d' ' -f1 | xargs -n 50 ipfs pin add`
  or upload the CID list to a pinning service (Pinata, Filebase, 4EVERLAND...). Pinned CIDs stay retrievable
  even if NHL Breakaway's own servers disappear.
* **Check integrity** any time with `python breakaway.py verify`. Every raw file's sha256 and fetch time
  (UTC) are in `data/manifest.json`; covers/videos are checked against the sha256 in their metadata.
* Raw responses are stored exactly as served and are never rewritten by the tool.

## Missing a moment? Add it

Add its NHL Breakaway link to `data/extra_moments.txt` (one per line) and open a pull request, or run
`python breakaway.py add <link>` yourself and commit the changed `data/` files. Duplicates are skipped.
See [CONTRIBUTING.md](CONTRIBUTING.md). Contributions via PR are welcome; the maintainer merges.

## License

Code: MIT (see [LICENSE](LICENSE)). Data: the metadata in `data/` is a preservation copy of public NHL
Breakaway / Sweet metadata; it and all highlight media, names and marks remain the property of their
rights holders (NHL, NHLPA, NHLAA, SocialSweet Inc.). No media is stored in this repo.

## The spreadsheet

* **Highlights**: one row per highlight with an embedded cover thumbnail, player, team, date, play,
  game details, set, series, rarity, edition size, description, prices, links (cover, video, Breakaway,
  metadata JSON, card page), cover IPFS CID + sha256, `raw_meta_path`, `offchain_path`, and data source.
* **All Metadata**: every field of every stored metadata file, flattened (`meta.*` = nft. metadata,
  `offchain.*` = Breakaway set listing).
* **IPFS**: every IPFS CID and sha256 per highlight (images and video).
* **By Set**: counts.

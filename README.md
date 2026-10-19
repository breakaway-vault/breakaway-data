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
| `breakaway.py` | The tool. `export_highlights.py` is a shortcut for `breakaway.py all`. |

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
```

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

## The spreadsheet

* **Highlights**: one row per highlight with an embedded cover thumbnail, player, team, date, play,
  game details, set, series, rarity, edition size, description, prices, links (cover, video, Breakaway,
  metadata JSON, card page), cover IPFS CID + sha256, `raw_meta_path`, `offchain_path`, and data source.
* **All Metadata**: every field of every stored metadata file, flattened (`meta.*` = nft. metadata,
  `offchain.*` = Breakaway set listing).
* **IPFS**: every IPFS CID and sha256 per highlight (images and video).
* **By Set**: counts.

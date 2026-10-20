# breakaway-data

> **Disclaimer:** Unofficial fan preservation project. Not affiliated with or endorsed by the NHL, NHLPA, NHLAA, Sweet (SocialSweet Inc.) or any team. All trademarks, names, logos, videos and images belong to their respective owners. This repository contains no media; anyone who downloads media with the tool does so only for personal archival use. Takedown requests are honored: please open a GitHub issue.

A preservation archive of NHL Breakaway digital highlight metadata for 1,811 highlights. The card list
(`data/highlights.json`) ships with the repo and grows with `add` (see below).

NHL Breakaway may shut down, so the raw metadata is stored **in this repo, byte-for-byte as served**.
Everything else (the spreadsheet, cover art, videos) can be rebuilt from it.

## What's in the repo

| Path | What it is |
|---|---|
| `data/meta/<id>.json` | Raw response of `https://nft.nhlbreakaway.com/series/<series>/<token>` for each highlight (`<id>` = card id). It is JSON (`application/json`), not XML. |
| `data/manifest.json` | Per highlight: source URL, fetch time (UTC), HTTP status, bytes, sha256 of the stored file, moment UUID, how it was linked, off-chain file, and **every IPFS CID + sha256** found in its metadata (images and video). |
| `data/offchain/sets/<set_uuid>.json` | Raw NHL Breakaway set listings (`apigw.sweet.io/catalog/search/moment/set/...`): off-chain descriptions, game/play details, edition sizes, rarity, dates. |
| `data/offchain/setcompletion_826.json`, `collection_challenge_826.json` | Raw set-completion and quest data (set rewards, quest highlight lists). |
| `data/highlights.json` | The card list: id, player, set, rarity, edition size, team, and an October 2026 price snapshot (lowest ask / FMV). Every command starts from this file. |
| `data/links.json` | Card id -> NHL Breakaway series id + token id (+ moment UUID), and how each was found. |
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

## No git? Download and unzip

1. Get the zip (`Breakaway Tool (same as GitHub).zip`, or **Code > Download ZIP** on GitHub) and unzip it.
   Right-click > **Extract All** on Windows. You'll get a `breakaway-data` folder.
2. Install Python 3 from https://www.python.org/downloads/ and tick **"Add Python to PATH"** during setup.
3. Open the `breakaway-data` folder in File Explorer, click the address bar, type `cmd` and press Enter.
4. In that window run these (if `python` isn't found, type `py` instead):
   ```
   python -m pip install -r requirements.txt
   python breakaway.py covers
   python breakaway.py build
   python breakaway.py view
   ```
   * `covers` downloads the full-res cover art to `output\covers_full` (about 1.6 GB).
   * `build` makes the spreadsheet `output\highlights.xlsx`.
   * `view` makes the offline viewer `viewer\index.html` (double-click it to open).
   * `python breakaway.py album` makes a printable flip-book PDF, `output\album.pdf` (see "Make the flip-book").
   * Videos are optional: `python breakaway.py videos --limit 5` saves the first 5 to `output\videos`;
     `python breakaway.py videos` gets all of them (about 220 GB). It shows the size and asks y/n first.
   Re-running any command only downloads what's missing. Run `python breakaway.py view` again after
   downloading videos so the viewer plays them from your disk.

## Commands

```
python breakaway.py fetch   [--refresh] [--ids 12,40] [--discover [--limit N]] [--concurrency 6]
python breakaway.py covers  [--concurrency 6]        # full-res covers -> output/covers_full/, sha256-checked
python breakaway.py build                            # OFFLINE: data/ -> output/highlights.xlsx
python breakaway.py package                          # output/covers/, covers.zip, Breakaway-Highlights.zip
python breakaway.py all                              # fetch + covers + build + package
python breakaway.py videos  [--out-dir DIR] [--limit N] [--series "Series 3"] [--ids 12,40] [--yes]
python breakaway.py verify  [--out-dir DIR]          # re-hash data/meta, covers and videos vs stored sha256
python breakaway.py add     <url | seriesId/tokenId> ...   # also reads data/extra_moments.txt
python breakaway.py view    [--out-dir DIR]          # offline viewer/index.html
python breakaway.py album   [--layout 1up|2x2|3x3] [--page letter|a4] [--set ..] [--series ..] [--player ..]
                            [--team ..] [--bleed] [--out FILE] [--max-px N] [--jpeg Q]   # printable PDF
```

* `--gateway https://my-gateway/ipfs/` (repeatable) adds IPFS gateways to try first; built-in fallbacks are
  ipfs.io, dweb.link, w3s.link, gateway.pinata.cloud and 4everland.io. `--ipfs-only` skips
  mediagateway.sweet.io / nft.nhlbreakaway.com entirely (use this if NHL Breakaway goes offline).

* Re-runs only fetch what's new or missing. `--refresh` re-pulls all metadata and set listings;
  `fetch --refresh --ids 12,40` re-pulls just those highlights.
* Where the card list comes from: `data/highlights.json` in this repo, plus anything added with `add` or
  `data/extra_moments.txt`. `fetch --discover` also adds moments that NHL Breakaway's own public set
  listings (`apigw.sweet.io`) show but the card list doesn't have yet (`--limit N` to add only a few).
  No other site is contacted.
* New card-list rows are linked to tokens by matching set + player + series against NHL Breakaway's set
  listings. If edition #1 of a moment returns 404, the next few serials are tried and the one that answers
  is kept. Anything still unmatched is printed so you can add it by URL.
* `--concurrency` (1-8, default 6) caps parallel requests to NHL Breakaway / its CDN. Requests retry with
  exponential backoff on 429/5xx/timeouts and slow down automatically when errors climb. 401/403/404 are
  never worked around.

### Videos (opt-in)

Videos are **off by default** and never downloaded by `all`. `python breakaway.py videos --out-dir videos`
estimates the total size with a few HEAD requests, then asks `y/n` (skip the question with `--yes`).
Downloads resume (`.part` files) and skip files that already exist. Try `--limit 5` first.

## Make the flip-book

`python breakaway.py album` builds a print-ready PDF (needs `reportlab`, included in requirements.txt): a cover
page, a table of contents by series and set, then one section per set in release order (title page with
series, rarity mix and card count, then the cards). Each card shows the cover art, player, team, date, play,
rarity, edition size and its `#` row number (same as the spreadsheet and cover file names). Missing covers are
downloaded first. Output: `output/album.pdf` unless you pass `--out`.

```
python breakaway.py album                                   # everything, 2 cards per row/column (2x2), Letter
python breakaway.py album --layout 3x3 --page a4            # 9 per page on A4
python breakaway.py album --layout 1up --player "Connor McDavid"
python breakaway.py album --team "Toronto Maple Leafs" --out leafs.pdf
python breakaway.py album --set "Ice Nation" --series "Series 1"
python breakaway.py album --series "Series 2" --bleed       # 3 mm bleed + crop marks for a print shop
python breakaway.py album --max-px 600 --jpeg 80            # much smaller file for screens
```

Full album (1,811 cards, 82 set sections): about 1,896 pages (1up), 570 pages (2x2) or 321 pages (3x3).
At full resolution it's roughly 2.3 GB, so making one PDF per series (`--series "Series 1"` etc.) is easier
on your computer and the print shop. Filters match part of a name and aren't case sensitive.

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

## Disclaimer

Unofficial fan preservation project. Not affiliated with or endorsed by the NHL, NHLPA, NHLAA, Sweet (SocialSweet Inc.) or any team. All trademarks, names, logos, videos and images belong to their respective owners. This repository contains no media; anyone who downloads media with the tool does so only for personal archival use. Takedown requests are honored: please open a GitHub issue.

## License

Code: MIT (see [LICENSE](LICENSE)). Data: the metadata in `data/` is a preservation copy of public NHL
Breakaway / Sweet metadata; it and all highlight media, names and marks remain the property of their
rights holders (NHL, NHLPA, NHLAA, SocialSweet Inc.). No media is stored in this repo.

## The spreadsheet

* **Highlights**: one row per highlight with an embedded cover thumbnail, player, team, date, play,
  game details, set, series, rarity, edition size, description, price snapshot, links (cover, video, Breakaway,
  metadata JSON), cover IPFS CID + sha256, `raw_meta_path`, `offchain_path`, and data source.
* **All Metadata**: every field of every stored metadata file, flattened (`meta.*` = nft. metadata,
  `offchain.*` = Breakaway set listing).
* **IPFS**: every IPFS CID and sha256 per highlight (images and video).
* **By Set**: counts.

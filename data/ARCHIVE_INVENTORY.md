# NHL Breakaway Fan Archive: What We Have and What's Missing

*Inventory as of October 29, 2026, 3:30 PM ET.*

This is a community preservation archive of NHL Breakaway, the digital hockey-highlights collectibles platform. It lists everything that was saved, where to find it, and what could not be saved. A technical reference on how the site worked is in [REBUILD.md](REBUILD.md).

## What this archive is not

- It holds **media and public records only**: videos, images, descriptions, stats and public pages.
- It **does not hold, transfer or affect ownership of any token**. The collectibles are tokens on the Polygon blockchain. They stay in each collector's own wallet, and only the owner can move them. Nothing here changes that.
- It **does not speak for** Sweet, the NHL, the NHLPA or the platform. It is an independent fan effort.
- Collector names, usernames, wallets and profile pictures were intentionally left out.

---

## 1. What's preserved

| What | Count | Size | Status |
|---|---|---|---|
| Moment (highlight) details: player, team, date, play, set, series, rarity, edition size | 1,973 moments | ~20 MB | Done |
| Highlight videos (the platform's server copies) | 1,953 of 1,953 video files, covering 1,971 moments | 247.6 GB | Done |
| Card covers | 1,973 of 1,973 | 1.72 GB | Done |
| Widescreen (16x9) covers | 1,953 images (1,952 match the platform's published checksum) | 1.83 GB | Done |
| Card images | 1,087 of 1,087 files, covering 1,971 moments | 0.86 GB | Done |
| Thumbnails (350 px) | 7,793 | 1.06 GB | Done |
| Pack art (front, back, square) | 186 | 335 MB | Done |
| Pack-opening videos | 63 (every pack) | 1.01 GB | Done |
| Set, series, challenge and icon art | 441 | 1.78 GB | Done |
| Supply stats per moment (edition size, collected, in packs, listed, burned or removed, crafted, frozen) | 1,969 moments | <1 MB | Done |
| Drops (all 63 pack drops with price, quantity, odds text) | 63 | <1 MB | Done |
| Blockchain contracts (Polygon), with collection info and royalties | 156 (93 moment sets + 63 packs) | <1 MB | Done |
| Transaction history (sales and transfers, with public transaction links; no names) | 1,972 of 1,972 moments checked, 1,605 with events: 480,685 events | 20 MB compressed | Done |
| Website pages: main site, help center (English and French), blog | 218 pages | 12 MB | Done |
| Site code and assets: page templates, scripts, styles, images, sample page data for 387 routes, 12 public API samples with field descriptions | 279 page-data files, 419 asset files | ~710 MB | Done |
| Wayback Machine snapshots of the public pages | 218 | — | Done |

**Supply snapshot** (from the platform's public stats, across 1,972 moments):

| | Count |
|---|---|
| Edition slots | 1,139,885 |
| Collected | 569,753 |
| Still in unopened packs | 93,175 |
| Listed for sale | 15,316 |
| Removed from circulation | 304,831 |
| Used for crafting | 29,478 |
| Frozen | 23,585 |
| Other | 142,648 |

## 2. Where everything lives

**This repository (`data/`):**

| Path | Contents |
|---|---|
| `highlights.json`, `meta/` (one file per moment), `manifest.json` | moment details |
| `archive_urls.json`, `links.json` | each moment's video, cover and card image on the Internet Archive |
| `api_snapshot/moment_supply.json` | supply stats |
| `api_snapshot/drops.json` | drops |
| `api_snapshot/moment_uuids.json`, `api_snapshot/series_contracts.json` | moment and set IDs |
| `chain/contracts.json`, `chain/pack_contracts.json`, `chain/README.md` | contracts |
| `site_kit/` | page templates list, sample page data, API samples and field descriptions |
| `wayback_snapshots.json` | list of Wayback snapshots |
| `transaction_history.csv.xz` | every sale and transfer: moment, set, token id, edition, type, time, price, currency, Polygon transaction hash (no names or wallets) |
| `REBUILD.md` | technical reference |

**Internet Archive: moment items** (videos, covers, card images):

| Series | Items |
|---|---|
| Series 1 | [series1-01](https://archive.org/details/nhl-breakaway-moments-series1-01) · [02](https://archive.org/details/nhl-breakaway-moments-series1-02) · [03](https://archive.org/details/nhl-breakaway-moments-series1-03) · [04](https://archive.org/details/nhl-breakaway-moments-series1-04) · [05](https://archive.org/details/nhl-breakaway-moments-series1-05) · [06](https://archive.org/details/nhl-breakaway-moments-series1-06) · [07](https://archive.org/details/nhl-breakaway-moments-series1-07) · [08](https://archive.org/details/nhl-breakaway-moments-series1-08) · [09](https://archive.org/details/nhl-breakaway-moments-series1-09) |
| Series 2 | [series2-01](https://archive.org/details/nhl-breakaway-moments-series2-01) · [02](https://archive.org/details/nhl-breakaway-moments-series2-02) · [03](https://archive.org/details/nhl-breakaway-moments-series2-03) · [04](https://archive.org/details/nhl-breakaway-moments-series2-04) · [05](https://archive.org/details/nhl-breakaway-moments-series2-05) · [06](https://archive.org/details/nhl-breakaway-moments-series2-06) · [07](https://archive.org/details/nhl-breakaway-moments-series2-07) |
| Series 3 | [series3-01](https://archive.org/details/nhl-breakaway-moments-series3-01) · [02](https://archive.org/details/nhl-breakaway-moments-series3-02) · [03](https://archive.org/details/nhl-breakaway-moments-series3-03) · [04](https://archive.org/details/nhl-breakaway-moments-series3-04) · [05](https://archive.org/details/nhl-breakaway-moments-series3-05) |

**Internet Archive: companion items:**

- [nhl-breakaway-covers-16x9](https://archive.org/details/nhl-breakaway-covers-16x9): widescreen covers, one zip per series, plus `manifest-16x9.csv`.
- [nhl-breakaway-extras](https://archive.org/details/nhl-breakaway-extras):

  | Path | Contents |
  |---|---|
  | `packs/pack-art.zip` | pack art |
  | `packs/pack-opening-videos.zip` | pack-opening videos |
  | `art/set-series-challenge-and-icon-art.zip` | set, series, challenge and icon art |
  | `thumbnails/series-1…3-thumbnails.zip` | thumbnails per series |
  | `site/site-assets-and-pages.zip` | website pages |
  | `site/site-rebuild-kit.zip` | site code and assets |
  | `data/public-api-and-chain-data.zip` | public API and chain data |
  | `data/transaction-history.zip` | transaction history (one JSON file per moment) |
  | `manifest-extras.csv` | manifest of the extras |

**Wayback Machine:** the full list of 218 snapshots is in `wayback_snapshots.json`. One example is https://web.archive.org/web/20261029125823/https://nhlbreakaway.com/drops

## 3. Token IDs

- **What's saved:** every contract address, every moment's ID, and the token-ID formula: `token ID = (moment index × 2^48) + (edition − 1)`. With these, the token ID of any edition of any moment can be worked out, and anyone can check that token on Polygon. See `chain/README.md` and `api_snapshot/moment_uuids.json`.
- **What's not saved:** a complete list of every token ID that was actually minted. The contracts don't publish a total, and scanning the whole blockchain history isn't practical with free public servers.
- **What the transaction history adds:** it does record the token for every sale or transfer it lists (token address and edition number, plus a public transaction link). It covers 270,947 distinct tokens that traded, from 1,605 moments. Editions that never traded won't appear there.

## 4. What's missing, and why

| Missing | Why |
|---|---|
| **Original IPFS files** (each token's metadata file and the original-quality media) | Every token points to a file on IPFS, a shared file network. Public IPFS gateways refused or blocked downloads during capture, so the originals couldn't be re-fetched. The platform's own served copies were saved instead. Most of those videos are not byte-identical to the IPFS originals. Each file's IPFS address is recorded in the repo (`cids.txt`, `ipfs_status.json`), so the originals can still be fetched later if a gateway serves them. |
| **Videos for moments #439 and #600** | No video exists for these two moments on the platform. |
| **Card images for moments #600 and #1727** | No card image exists for these two moments. |
| **Set `j1ZJ8O1K`** | No contract or moment IDs could be resolved for it, so it has no contract, stats or history entries. |
| **3 moments in set `zqlMMQ1N`** | Their stats returned "not found". |
| **3 pack-opening poster images** (Modano's Seminal Moments, Next-Gen Class Debut LE, Stadiums & Skylines Debut LE) | They returned "not found" on the platform. |
| **Exact minted count** | Contracts don't report a total, so counts above come from the platform's public stats. |
| **Signed-in features**: trades, wallets, checkout, profiles, quest progress, prediction history | These need an account. Only public pages were captured, and personal data was intentionally excluded. How they worked can be seen in the saved site code. |
| **Fonts** (Lateral, Ruder Plakat, Söhne, Canela, Founders Grotesk Mono) | They are commercial licensed fonts, so they weren't archived. |
| **Live features** (marketplace, pack buying, pack opening) | They can't be archived. The pack-opening videos and drop pages are what remains. |


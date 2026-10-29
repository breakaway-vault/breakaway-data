# NHL Breakaway — Rebuild Kit

A community preservation record of the NHL Breakaway digital-collectibles site (nhlbreakaway.com), captured from public, unauthenticated pages and APIs in October 2026. It documents how the site worked and where every preserved piece lives, so someone can stand up a read-only replica viewer.

---

## 1. How the site worked

**Stack.** A Next.js (pages router) front end served from `nhlbreakaway.com`. It talked to a REST API gateway at `https://apigw.sweet.io`, and accounts were handled by an external sign-in (Auth0 at `account.sweet.io`). Media came from these hosts:

| Host | What it served |
|---|---|
| `nft.nhlbreakaway.com` | token and series media, contract docs |
| `mediagateway.sweet.io` | per-token rendered posters |
| `collectible.sweet.io` | challenge-reward and icon art |
| `nhl-static.assets.sweet.io` / `static.assets.sweet.io` | site chrome |

The help center ran on Intercom (`help.nhlbreakaway.com`) and the blog on Ghost (`blog.nhlbreakaway.com`). The site ran on Polygon, the blockchain that holds the tokens.

**Routes.** These come from the Next.js build manifest. The original file is `site_kit/bm.js`, and the per-route results are in `site_kit/routes_captured.json`.

| Route | Purpose |
|---|---|
| `/`, `/home` | landing page and signed-in home |
| `/drops`, `/drop/[series_id]` | pack drops (pack series) and a single drop's page with odds and price |
| `/pack`, `/pack/[slug]` | pack marketplace and a single pack |
| `/pack-open/[series_id]/[token_id]`, `/pack-open-replay/...` | pack-opening animation (uses the pack-opening videos) |
| `/series/[series_id]` | a moment set (series contract) with its moments |
| `/series/[series_id]/highlight/[moment_uuid]` | one moment (highlight): video, stats, editions |
| `/series/[series_id]/[token_id]` | one edition (a single token) |
| `/marketplace` | secondary-market listings |
| `/trade`, `/trade/create`, `/trade/offer/[trade_id]` | peer-to-peer trades (signed-in only) |
| `/play`, `/play/sets`, `/play/quests`, `/play/[seriesId]/sets/[set_id]`, `/play/[seriesId]/quests/(collection\|signature)/[challenge_id]` | set completion, quests and challenges with reward art |
| `/play/predict` (`/history`, `/leaderboard`) | prediction game |
| `/team/[slug]` | per-team collection view |
| `/user/[username]`, `/profile`, `/collection` | collector profiles and wallet (not archived, for privacy) |
| `/rarity` | rarity tier explainer |
| `/terms`, `/privacy`, `/cookie-policy`, `/redeem/[code]`, `/onboarding`, `/registration` | legal pages and account flows |
| `/fr/...` | French-language versions of the pages above |

## 2. Data model

```
Campaign 826 (NHL)
 ├─ Series (moment set) ── 1 Polygon ERC-721 contract each (93 contracts), symbol BRKWY
 │    └─ Moment (highlight) ── moment_uuid; edition_size N; rarity tier
 │         └─ Edition = token (token_id), edition number 1..N
 └─ Pack series (drop) ── 1 ERC-721 contract each (63 contracts)
      └─ Pack token ── opening it burns the pack and delivers moment tokens per the published odds
```

- **Series ID.** An 8-character code (e.g. `GqEK4QbD`). The series URI is `https://nft.nhlbreakaway.com/series/{series_id}`.
- **Moment UUID.** 32 hex characters: a 16-hex series prefix, then the 4-hex moment index, then 12 zeros.
- **Token ID.** `(moment_index << 48) + (edition - 1)` as a uint256. The token URI is `{series URI}/{token_id}`.
- **Packs.** They use the same scheme. The pack index is `pack_uuid[16:20]`.
- **Rarity tiers and maximum editions across 1,973 moments:**

  | Tier | Max editions |
  |---|---|
  | Core | 588,349 |
  | Fandom | 364,023 |
  | Limited | 112,500 |
  | Rare | 55,500 |
  | Epic | 9,200 |
  | Heroic | 7,680 |
  | Legendary | 170 |
  | Mythic | 15 |

- **Supply status from the public stats in October 2026** (1,972 moments):

  | Status | Count |
  |---|---|
  | Edition slots | 1,139,885 |
  | Collected | 569,753 |
  | Still in unopened packs | 93,175 |
  | Listed for sale | 15,316 |
  | Removed from circulation | 304,831 |
  | Used for crafting | 29,478 |
  | Frozen | 23,585 |
  | Other | 142,648 |

**On-chain.** Each contract is a standard Polygon ERC-721 with ERC-2981 royalties of 600 bps (6%). They are not enumerable and have no `totalSupply`.
- `tokenURI` is `ipfs://<CID>`, so each token's metadata JSON is on IPFS.
- `contractURI` is `https://nft.nhlbreakaway.com/doc/<hash>/contract`, on the platform's own server. Every contractURI response is copied in `chain/contracts.json`.
- Series contracts are owned by `0x610123c1f5e34974c63343c84973cd5603b08e7c` and pack contracts by `0x067de4a68be941d44d0da50750256c8efd059096`.

## 3. Public API (apigw.sweet.io)

Requests need a browser-like `User-Agent`. All IDs are URL-encoded series or token URIs. Sample responses are in `site_kit/api_samples/` and inferred schemas in `site_kit/schemas/`. In every saved response, personal fields (usernames, profile images, wallet and user IDs) are replaced with `[removed]`.

| Endpoint | Returns |
|---|---|
| `GET /collectibles/public/token/{tokenURI}` | token metadata (title, player, team, media, rarity, edition) |
| `GET /collectibles/public/tokenstatus/{tokenURI}` | contract and explorer link, pack-opened and burned flags |
| `GET /distribution/series/stats/{seriesURI}/{moment_uuid}` | edition_size, collected, listed, in_packs, used_for_crafting, frozen, removed_from_circulation, others |
| `GET /distribution/history/{seriesURI}?limit&skip&uuid=` | sales and transfer history (tx links) |
| `GET /distribution/listing/stats/{URI}`, `/distribution/listing/{URI}`, `/distribution/inventory/{packURI}`, `/distribution/trait/stats/{URI}` | market and inventory stats |
| `GET /user/826/teams?show_historical=true` | team list |

Endpoints that need a signed-in account were not called. They cover wallet, trades, transfer, listing creation, user profile and messages, and are listed in `site_kit/` (found in the site's JavaScript).

## 4. Media URL patterns and renditions

| Asset | URL pattern |
|---|---|
| Moment front, widescreen | `https://nft.nhlbreakaway.com/series/{sid}/{moment_index_hex}/images/front-16x9.png` (also `https://mediagateway.sweet.io/media/token/{sid}/{token_id}/poster-image-16x9.png`) |
| Moment thumbnail | `.../{moment_index_hex}/images/front-350x.png` (plus other `front-*` sizes) |
| Moment video and card cover | preserved in the moment items (below) |
| Pack art | `https://nft.nhlbreakaway.com/series/{pack_sid}/image-front.png` (front, back, square variants) |
| Pack-opening video | `https://nft.nhlbreakaway.com/series/{pack_sid}/pack_opening/video-ext-square.mp4` (+ `opening-video-square-poster.png`) |
| Challenge and reward art | `https://collectible.sweet.io/challenge_reward/image/{uuid}.png` |

**Fonts.** These were not archived because they are commercial licensed fonts. The families are listed in `site_kit/fonts_skipped.json`; a replica should substitute open fonts.

## 5. Where everything lives

**In this repository (`data/`):**
- `chain/contracts.json`: all 156 contracts with collection metadata and royalties.
- `chain/pack_contracts.json`: pack contracts mapped to drops, prices and quantities.
- `chain/README.md`: the token-ID rules.
- `api_snapshot/moment_supply.json`: supply stats per moment.
- `api_snapshot/moment_uuids.json`: moment → series, UUID and sample token.
- `api_snapshot/series_contracts.json`: series → contract.
- `api_snapshot/drops.json`: all 63 drops with odds text and prices.
- `site_kit/`: route manifest, page data samples (`next_data/`), API samples and schemas, and the skipped-font list.
- `highlights.json`, `meta/`, `archive_urls.json`, `links.json`: moment details and Internet Archive links (see ARCHIVE_INVENTORY.md).

**Internet Archive:**
- `nhl-breakaway-moments-series1-01` … `series3-05`: moment videos and card covers.
- [nhl-breakaway-covers-16x9](https://archive.org/details/nhl-breakaway-covers-16x9): widescreen cover art for every moment, in one zip per series, with a checksum manifest.
- [nhl-breakaway-extras](https://archive.org/details/nhl-breakaway-extras):

  | Path | Contents |
  |---|---|
  | `packs/pack-art.zip` | pack art |
  | `packs/pack-opening-videos.zip` | pack-opening videos |
  | `art/set-series-challenge-and-icon-art.zip` | set, series, challenge and icon art |
  | `thumbnails/series-N-thumbnails.zip` | thumbnails per series |
  | `site/site-assets-and-pages.zip` | site, help-center and blog HTML and JS |
  | `site/site-rebuild-kit.zip` | full Next.js static build, CSS, route page data, API samples |
  | `data/public-api-and-chain-data.zip` | public API and chain data |
  | `data/transaction-history.zip` | history, when complete |
  | `manifest-extras.csv` | manifest of the extras |

**Wayback Machine.** The public site, about 65 help-center articles and collections (English and French) and about 137 blog posts and the RSS feed were captured (218 snapshots; full list in `wayback_snapshots.json`), for example `https://web.archive.org/web/2026/https://nhlbreakaway.com/drops`.

## 6. Standing up a replica viewer (read-only)

1. **Data.** Load `api_snapshot/moment_uuids.json`, `moment_supply.json` and `drops.json`, plus `chain/*.json`. Join moments to series by `series_id`, and to media through the archive map or the URL patterns above, rewritten to Internet Archive download URLs.
2. **Static site.** Any static generator works. Mirror the routes in section 1 that need no account: `/drops`, `/drop/[id]`, `/series/[id]`, `/series/[id]/highlight/[uuid]`, `/rarity`, `/team/[slug]`. Use the page-data samples in `site_kit/next_data/` as the exact shape the original pages received, and `schemas/` for the field types.
3. **Original front end (optional).** `site/site-rebuild-kit.zip` holds the compiled Next.js chunks and CSS. Serving `_next/static/` with the captured page HTML reproduces the original look offline. Point the API base at a small mock server that replays `api_samples/` or serves the snapshot JSON.
4. **On-chain verification.** Any Polygon RPC can call `tokenURI(token_id)` and `ownerOf(token_id)` on the contracts in `chain/contracts.json`, using the token-ID formula above.

## 7. Known gaps

- **Original IPFS files.** The per-token metadata and the original media pinned on IPFS were not re-fetched. The CIDs are in the contracts data, and the platform's own copies of the media are preserved instead.
- **Signed-in features** (trades, wallet, checkout, profiles, prediction history) are documented only from the front-end code. No authenticated data was captured, and collector identities are intentionally excluded.
- **Incomplete series.** One series (`j1ZJ8O1K`) has no resolvable contract or moment IDs, and 3 moments in `zqlMMQ1N` return no stats.
- **Exact minted count.** The contracts expose no supply figure, so the counts above come from the platform's public stats.
- **Fonts** are omitted (licensed) and must be substituted.
- **Three pack-opening poster images** returned 404 at capture time.

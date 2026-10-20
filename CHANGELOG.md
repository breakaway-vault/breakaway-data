# Changelog

## Unreleased

* Full IPFS availability scan of all 14,739 CIDs, plus `check-ipfs --recheck` (retry failures on up to 4 gateways; verdict `uncached` vs `gone`).
* New `check-live`: is each moment still in NHL Breakaway's current set listings, and does the CDN still serve its cover and video (`data/live_status.json`).
* New per-moment fields `ipfs_health`, `ipfs_missing` and `listed_now`; new `status` value `delisted`.
* "My collection": `--mine [path]` for covers, videos, build, view, album and pin, reading a private, gitignored `my_cards.txt`/`.csv` (Breakaway links with edition numbers, series/token, card ids, The Fifth Line links). Viewer "My cards" toggle, menu option 10.
* Tagline: "Made for the community, by the community."
* New `data/at_risk.md` listing moments whose originals are missing on IPFS; `--at-risk` filter for `covers`, `videos`, `pin` and `album`; `health` command.

## v1.0.0 (2026-10-19)

First public release.

* **Archive:** 1,973 NHL Breakaway highlights: 1,811 from the original card list plus 162 found in NHL Breakaway's own set listings. Raw metadata stored byte-for-byte, a manifest with sha256 and 14,739 IPFS CIDs, and off-chain set data.
* **Standalone apps** for Windows, macOS and Linux (no Python needed), built by GitHub Actions on every `v*` tag, plus an interactive numbered menu when run with no arguments.
* **IPFS-first downloads:** covers and videos are fetched from IPFS gateways and checked against the metadata sha256. The NHL Breakaway CDN is only a fallback; its re-encoded copies are logged as `reencoded`. `--repair`, `--ipfs-only`, `--offline`.
* **New commands:** `check-ipfs` (sample availability report in `data/ipfs_status.json`) and `pin` (CID lists; pin with your own Kubo node or a pinning service using your own token).
* **`status` field:** `released` (listing or price seen) or `unverified`.
* Viewer and album show IPFS CIDs as each moment's permanent identity, and everything works offline from downloaded files.
* `breakaway.config.json` settings file, issue templates, short CONTRIBUTING, and a no-warranty notice.

# Changelog

## v1.1.1 (2026-10-20)

* Downloads show a live progress line: done / total, percent, ok / skipped / failed, MB downloaded and rough time left (covers, videos, verify, pinning and the IPFS check). It updates in place in a terminal window and prints a plain line every few seconds in logs, then ends with a summary.
* Ctrl+C now really stops a download, also in the Windows app: it says where it stopped ("run again to resume") and goes back to the menu.
* Downloads are saved as `<name>.part` and only renamed when complete and checked. Leftover `.part` files from a closed window are cleaned up, and a file only counts as "already saved" if its size (or sha256) checks out, so a half-written file is downloaded again.
* Viewer covers load faster: native lazy loading, and a cover that errors or stalls for a few seconds falls back to NHL Breakaway's image server and then the other IPFS gateways (a few tries at most). Your downloaded covers are still used first.
* The version (v1.1.1) is shown at the top of the menu, in the viewer footer and with `--version`.
* Viewer, "My cards" on: the count shows your whole collection plus what's on screen, e.g. "My cards: 750 moments, 1,609 editions (showing 340)".
* Big collections: each viewer tile shows a small "×12" badge (or "owned") and one short line of edition numbers, lowest first ("yours #26, #94, #322 +9 more"); the full list is in the card's details. New "Most owned" sort.
* Album with `--mine`: one line per card ("Owned ×12: #26, #94, #322 +9 more") plus "My serials" pages at the end listing every edition number. The spreadsheet still lists them all.
* Viewer detail card: "Download video" and "Download cover" buttons. They fetch the IPFS original (checked against its sha256 and marked "Verified original" when it matches), fall back to the NHL Breakaway copy (marked "may be re-encoded"), or open the file in a new tab as a last resort. Your own downloaded files are used when present.
* Viewer detail card layout: title, video (cover as poster), description, your editions, download buttons, links, then "Technical details" (CIDs, sha256, all metadata) folded away.
* Fixed: links in the viewer's "Every IPFS file" table included the sha256 text, so gateways answered "invalid path". Every IPFS link is now exactly `<gateway>/ipfs/<CID>`, with the sha256 shown separately; `scripts/test_links.py` (run by CI) checks every generated IPFS link.

## v1.1.0 (2026-10-20)

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

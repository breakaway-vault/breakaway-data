# Changelog

## Website and data (2026-10-29)

* New: fan copies of the moment videos and cover art are on the [Internet Archive](README.md#internet-archive-copies), and `data/archive_urls.json` maps each moment to its Archive item and files. The videos are NHL Breakaway's re-encoded server copies, not the byte-exact IPFS originals; the covers are the originals.
* Website: moment pages play the Internet Archive copy first, then NHL Breakaway's servers, then IPFS, and link the Archive item and video file. Covers can fall back to the Archive copy too.
* Fixed (website): every moment was tagged "At risk". Only moments that are unlisted or have files missing on IPFS (202 right now) get the tag, and the note says why in plain words.
* The app (v1.1.5) is unchanged.

## v1.1.5 (2026-10-20)

* Covers and videos now come from NHL Breakaway's own servers first while they're up (faster and more reliable), with the IPFS gateways as the backup when a file fails, is refused, times out or comes back wrong. This applies to the app (every menu option and command that downloads) and to the viewer's covers and Download buttons. The video player already played NHL Breakaway's copy before IPFS.
* What we found: NHL Breakaway's covers are byte-for-byte the originals (40 of 40 matched the sha256 in the metadata), so they are still verified. Its videos are re-encoded copies (6 of 6 differed from the originals by about 1%), so a video from there is accepted when it is a complete MP4 and logged as `reencoded`. Already saved, the Downloads import and `verify` treat these copies as saved instead of downloading them again; a cut-off video is still caught.
* NHL Breakaway's video server refuses downloads made from inside a web page, so the viewer's "Download video" button gets the original from IPFS instead. Playing videos in the viewer isn't affected.
* New setting to switch back: `--prefer ipfs`, or `"prefer": "ipfs"` in `breakaway.config.json` (default `"breakaway"`). `--ipfs-only` still never contacts NHL Breakaway.
* README: IPFS is described as the backup that keeps working if NHL Breakaway's servers go away, which is what pinning (menu 8) helps with.

## v1.1.4 (2026-10-20)

* Fixed: the viewer kept "My cards" after an upgrade only if your list was called `my_cards.txt` or `my_cards.csv` next to the app. It now remembers the list you used (a path inside the archive folder is stored relative, so no personal folder names end up in the viewer).
* Fixed: "Open the viewer" could open the wrong page or nothing when the archive folder's name has a space, `#` or accented letters. The same goes for the viewer's links to your downloaded covers and videos.
* Fixed (Windows): an output or video folder on a different drive from the app (e.g. app on `Z:`, videos on `D:`) made downloads and the viewer stop with an error.
* The pin list summary no longer ends with a stray comma when no files match.

## v1.1.3 (2026-10-20)

* Viewer: the detail card now checks whether you already have the cover and video (in the folder you picked, or next to the viewer) and shows "Already saved ✓" instead of downloading again, with a small "Download again" link. A saved copy with the wrong size or fingerprint is flagged as incomplete and can be replaced. After a download the button switches to "Already saved" straight away.
* Viewer: removed the long IPFS CID line under every card in the grid. The CIDs are still in "Technical details" on each card.
* Album: removed the IPFS CID line from each card (it stays in the spreadsheet and the metadata).
* The viewer is made by the app, not shipped in the zip, so after an upgrade an old `viewer/index.html` could stay behind. The app now rebuilds it when it starts if it was made by another version (keeping "My cards" if you used it).
* Fixed: a crash when a name with characters outside the Windows console's code page (e.g. "Dvořák") was printed to a redirected or older console.
* Copies in Downloads that are already in the archive are no longer re-hashed or reported on every start.

## v1.1.2 (2026-10-20)

* Fixed: the viewer's "Download video" and "Download cover" buttons always opened a new tab instead of saving. The page looked for its status text in the wrong place, which stopped every download attempt before it started. They now really download, check the sha256 and save.
* The buttons save under the app's own file names (e.g. `481.png`, `0751_Mark_Stone_Signature_Cores.mp4`). In Chrome and Edge you can pick your `Breakaway-Archive/output` folder once and files go straight into `covers_full/` or `videos/`; otherwise they go to Downloads.
* The app picks up covers and videos saved to your Downloads folder (also `name (1).mp4` duplicates): when you start it and before `covers` / `videos`, files whose sha256 matches an original are moved into the archive ("Imported N files from Downloads"). Other files are never touched.
* Button downloads no longer give up after a few seconds on a slow source: they show progress and only move on when a source sends nothing for 15 s (30 s once started). If every source fails, the new tab gets a gateway link that downloads under the right name, and the reason is logged in the browser console.
* If the browser has no built-in SHA-256 (crypto.subtle), the viewer uses its own, so "Verified original" still works.

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

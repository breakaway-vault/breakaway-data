# Changelog

## v1.0.0 (2026-10-19)

First public release.

* **Archive:** 1,973 NHL Breakaway highlights: 1,811 from the original card list plus 162 found in NHL Breakaway's own set listings. Raw metadata stored byte-for-byte, a manifest with sha256 and 14,739 IPFS CIDs, and off-chain set data.
* **Standalone apps** for Windows, macOS and Linux (no Python needed), built by GitHub Actions on every `v*` tag, plus an interactive numbered menu when run with no arguments.
* **IPFS-first downloads:** covers and videos are fetched from IPFS gateways and checked against the metadata sha256. The NHL Breakaway CDN is only a fallback; its re-encoded copies are logged as `reencoded`. `--repair`, `--ipfs-only`, `--offline`.
* **New commands:** `check-ipfs` (sample availability report in `data/ipfs_status.json`) and `pin` (CID lists; pin with your own Kubo node or a pinning service using your own token).
* **`status` field:** `released` (listing or price seen) or `unverified`.
* Viewer and album show IPFS CIDs as each moment's permanent identity, and everything works offline from downloaded files.
* `breakaway.config.json` settings file, issue templates, short CONTRIBUTING, and a no-warranty notice.

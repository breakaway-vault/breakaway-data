# Contributing to breakaway-data

Thanks for helping preserve NHL Breakaway highlights! Anyone can open a pull request; the maintainer merges.

## Missing a moment? Add it

**Easiest (no Python needed)**
1. Fork this repo on GitHub.
2. Edit `data/extra_moments.txt` and add the highlight's NHL Breakaway link on its own line, e.g.
   `https://nhlbreakaway.com/series/j1ZJjx1K/13725845764318429187`
   (any edition's link works; `nft.nhlbreakaway.com/...` and `seriesId/tokenId` are fine too).
3. Open a pull request. The maintainer will run `python breakaway.py add` to fetch and merge the metadata.

**Full (with Python)**
1. Fork and clone, then `pip install -r requirements.txt`.
2. `python breakaway.py add https://nhlbreakaway.com/series/<seriesId>/<tokenId>`
   (or add the links to `data/extra_moments.txt` and run `python breakaway.py add`).
   This saves the raw metadata to `data/meta/`, its off-chain set listing to `data/offchain/sets/`, and
   updates `data/highlights.json`, `data/links.json`, `data/manifest.json` and `data/cids.txt`. Duplicates
   are skipped automatically.
3. Run `python scripts/validate.py` and commit the changed `data/` files. Open a pull request.

## Rules
* Raw responses must stay byte-for-byte as served; don't reformat files in `data/meta/` or `data/offchain/`.
* Don't commit media (covers, videos), `output/`, `cache/`, or anything personal (wallets, emails, cookies, tokens).
* Be polite to NHL Breakaway's servers: keep the default throttling; never work around logins or rate limits.

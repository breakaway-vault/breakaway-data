# Community website

The static site published to GitHub Pages by `.github/workflows/pages.yml`.

* **Museum** (`index.html`) lists every moment in `data/highlights.json`, with search, filters, sorting and a detail view that has a click-to-play video.
* **My collection** (`collection.html`) reads a `my_cards.csv` in the browser, matching it the same way as `breakaway.py`'s "Show only my cards". The file is never uploaded. A share link stores the collection in the URL after `#`, so it never reaches a server. Collections can also be saved in the visitor's browser (localStorage, nothing uploaded), and exported back to `my_cards.csv`. **Submit to the Collector Hall** opens the GitHub form so you can drag that CSV into the issue.
* **Collector Hall** (`hall.html`) lists the public collections in `collections/`, compiled into `site/data/hall.json` by the build. Each collector's page is `collection.html#h=<handle>`. Fans submit through the issue form; see [CONTRIBUTING.md](../CONTRIBUTING.md#collector-hall).
* **Help** (`help.html`) is the plain-language how-to for fans (museum, My collection, Hall, desktop app, troubleshooting, privacy, contact).

The site hosts no media. Videos play from the fans' Internet Archive copies first (`data/archive_urls.json`), then NHL Breakaway's servers, then the public IPFS gateways. Covers load from NHL Breakaway's servers, then the Archive, then IPFS.

`site/data/` is generated (and not committed). Build it before previewing, or after changing `data/`:

    python scripts/build_site.py

To preview it locally:

    cd site && python -m http.server 8000    # then open http://localhost:8000

Unofficial fan preservation project, not affiliated with the NHL, the NHLPA or Sweet. Takedown requests are honoured.

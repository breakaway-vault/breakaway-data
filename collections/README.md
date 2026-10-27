# Collector Hall entries

Each entry is two files:

- `<handle>.csv` is the collection in `my_cards.csv` format (read with the same matching as breakaway.py's "Show only my cards").
- `<handle>.json` holds the handle, an optional short blurb and favourite team, and the GitHub user id (a number) of the account that submitted it, so only that account can update it.

Entries arrive as pull requests opened from the "Collector Hall submission" issue form, and only go live when a maintainer merges them. `example-collector` and `maple-leafs-complete` are made up to show the page and are not real collections. See [CONTRIBUTING.md](../CONTRIBUTING.md#collector-hall) for how to add, update or remove an entry. Check every entry with `python scripts/hall.py check`.

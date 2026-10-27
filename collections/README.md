# Collector Hall entries

Each entry is two files:

- `<slug>.csv` is the collection in `my_cards.csv` format (read with the same matching as breakaway.py's "Show only my cards").
- `<slug>.json` holds `handle` (the slug), `display_name` (the collector name exactly as the fan typed it, e.g. `Rink Rat 97`; spaces and capitals are fine), an optional short blurb and favourite team, and the GitHub user id (a number) of the account that submitted it, so only that account can update it.

The slug is made from the name automatically: lowercase, spaces and periods become `_`, repeats collapse, `_`/`-` are trimmed from the ends, and the result must match `^[a-z0-9][a-z0-9_-]{1,28}[a-z0-9]$` (`Rink Rat 97` -> `rink_rat_97`, `puck_hoarder_97` stays the same). The site shows `@display_name` (or the slug for older entries) and links to `collection.html#h=<slug>`. `python scripts/hall.py find "<name, slug or link>"` shows which files an entry uses.

Entries arrive as pull requests opened from the "Collector Hall submission" issue form, and only go live when a maintainer merges them. `example-collector` and `maple-leafs-complete` are made up to show the page and are not real collections. See [CONTRIBUTING.md](../CONTRIBUTING.md#collector-hall) for how to add, update or remove an entry. Check every entry with `python scripts/hall.py check`.

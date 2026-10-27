# Contributing

Thanks for helping preserve NHL Breakaway highlights.

## Add a missing moment

1. Fork this repo on GitHub.
2. Either add the highlight's NHL Breakaway link on its own line in `data/extra_moments.txt`
   (you can do this in the GitHub web editor), or run `python breakaway.py add <link>` and commit the changed `data/` files.
3. Open a pull request. CI runs `scripts/validate.py` on it automatically.

No GitHub account? Open a **Missing moment** issue with the link instead.

## Collector Hall

The [Collector Hall](https://breakaway-vault.github.io/breakaway-data/hall.html) shows collections that fans chose to make public. Each one is a pair of files in [`collections/`](collections/).

**Add or update your collection.** On the site's **My collection** page, load your `my_cards.csv` and press **Submit to the Collector Hall**. That opens the [Collector Hall form](https://github.com/breakaway-vault/breakaway-data/issues/new?template=collection.yml). Type your collector name (your NHL Breakaway name is perfect; spaces and capitals are fine, like `Rink Rat 97`), **drop your `my_cards.csv` into the cards box**, and send it. We check your cards right away and reply on the same page. If something needs fixing, the reply says what; edit your post (the **...** menu, then **Edit**) and we check again. We take a quick look before it goes up.

- Everything you post and your collection are public. Don't use your real name, and take out anything private (wallet addresses, emails) first. We only keep card numbers and edition numbers.
- A collector name is 3 to 30 letters, numbers, spaces, `_`, `-` or `.`, and belongs to the GitHub account that first used it. Sending the form again from the same account updates your collection; a new name renames it.
- `example-collector` and `maple-leafs-complete` are made up to show the page. They are not real collections.

**Take a collection down.** Use the [removal form](https://github.com/breakaway-vault/breakaway-data/issues/new?template=collection-removal.yml) with your collector name or page link. No reason is needed. If someone posted your cards or your name without asking, say so and we'll take it down.

**For maintainers.** The name typed in the form is stored as `display_name`; the file name and `#h=` link use a slug made from it (lowercase, spaces and periods to `_`, repeats collapsed, `_`/`-` trimmed from the ends, then `^[a-z0-9][a-z0-9_-]{1,28}[a-z0-9]$`), e.g. `Rink Rat 97` -> `collections/rink_rat_97.csv`. Entries without `display_name` show the slug. A slug belongs to the GitHub user id in its `.json`. For a removal request, `python scripts/hall.py find "Rink Rat 97"` (a name, slug or page link) prints the two files to delete in a pull request.
 The workflow needs Settings > Actions > General > Workflow permissions > "Allow GitHub Actions to create and approve pull requests", and the `collector hall` label (the form adds it). Pull requests it opens don't trigger other workflows, so run `python scripts/hall.py check` (or close and reopen the PR) before merging. Merging to `main` republishes the site.

## Ground rules

* Files in `data/meta/` and `data/offchain/` are raw responses, byte-for-byte as served: don't reformat them.
* Don't commit media (covers, videos), `output/`, or anything personal (wallets, emails, tokens).
* Keep the default throttling. Never work around logins or rate limits.

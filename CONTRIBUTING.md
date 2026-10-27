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

**Add or update your entry.** On the site's **My collection** page, load your `my_cards.csv` and press **Submit to the Collector Hall**. That opens the [submission form](https://github.com/breakaway-vault/breakaway-data/issues/new?template=collection.yml). **Drag your `my_cards.csv` into the Cards box** (or paste its contents), pick a handle, and submit. A workflow reads the attached file or the pasted text, checks the list with the same matching as `breakaway.py`, replies on the issue, and opens a pull request. **Nothing appears until a maintainer merges it.**

- Everything in the issue and the entry is public. Use a handle, not your real name, and remove anything private (wallet addresses, emails) before you submit. Only card numbers and edition numbers are kept in the entry.
- A handle is 3 to 30 lowercase letters, numbers, underscores and dashes (must start and end with a letter or number), and belongs to the GitHub account that first used it. NHL Breakaway usernames with underscores are fine. Submitting again from the same account updates your entry, and a new handle renames it.
- `example-collector` and `maple-leafs-complete` are made up to show the page. They are not real collections.

**Remove an entry.** Open a [removal request](https://github.com/breakaway-vault/breakaway-data/issues/new?template=collection-removal.yml), or a pull request that deletes `collections/<handle>.csv` and `.json`. No reason is needed. If someone posted your cards or your name without asking, say so and it will be taken down.

**For maintainers.** The workflow needs Settings > Actions > General > Workflow permissions > "Allow GitHub Actions to create and approve pull requests", and the `collector hall` label (the form adds it). Pull requests it opens don't trigger other workflows, so run `python scripts/hall.py check` (or close and reopen the PR) before merging. Merging to `main` republishes the site.

## Ground rules

* Files in `data/meta/` and `data/offchain/` are raw responses, byte-for-byte as served: don't reformat them.
* Don't commit media (covers, videos), `output/`, or anything personal (wallets, emails, tokens).
* Keep the default throttling. Never work around logins or rate limits.

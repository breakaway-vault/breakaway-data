# Contributing

Thanks for helping preserve NHL Breakaway highlights.

## Add a missing moment

1. Fork this repo on GitHub.
2. Either add the highlight's NHL Breakaway link on its own line in `data/extra_moments.txt`
   (you can do this in the GitHub web editor), or run `python breakaway.py add <link>` and commit the changed `data/` files.
3. Open a pull request. CI runs `scripts/validate.py` on it automatically.

No GitHub account? Open a **Missing moment** issue with the link instead.

## Ground rules

* Files in `data/meta/` and `data/offchain/` are raw responses, byte-for-byte as served: don't reformat them.
* Don't commit media (covers, videos), `output/`, or anything personal (wallets, emails, tokens).
* Keep the default throttling. Never work around logins or rate limits.

#!/usr/bin/env python3
"""Writes the issue reply for a Collector Hall submission from hall_submit.py's result file (plain fan language)."""
import json, sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
name = r.get("display_name") or r.get("handle") or ""
if r.get("ok"):
    out = [f"Got it! Your collection looks good: **{r['moments']:,} moments** ({r['editions']:,} edition numbers). "
           f"We'll give it a quick look and it'll appear in the Collector Hall soon as **`@{name}`**.",
           "", f"Once it's up, your page will be {r['url']}"]
else:
    out = ["Almost there! Please fix this:", ""] + [f"- {e}" for e in r.get("errors", [])] + \
          ["", "Then edit this post (the **...** menu at the top, then **Edit**) and we'll check again."]
if r.get("notes"): out += [""] + [f"> {n}" for n in r["notes"]]
print("\n".join(out))

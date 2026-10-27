#!/usr/bin/env python3
"""Writes the issue reply for a Collector Hall submission from hall_submit.py's result file."""
import json, sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
if r.get("ok"):
    out = [f"Thanks! Your list checked out: **{r['moments']:,} moments** and **{r['editions']:,} edition numbers** for `@{r['handle']}`.",
           "", "A maintainer will review it. It appears in the Collector Hall once the pull request is merged."]
else:
    out = ["This submission couldn't be added yet:", ""] + [f"- {e}" for e in r.get("errors", [])] + \
          ["", "Edit the issue (the **...** menu at the top of it, then **Edit**) to fix it, and this check runs again."]
if r.get("notes"): out += [""] + [f"> {n}" for n in r["notes"]]
print("\n".join(out))

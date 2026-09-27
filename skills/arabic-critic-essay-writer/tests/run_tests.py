#!/usr/bin/env python3
"""Checks that the style tooling works. Run from the skill root: python tests/run_tests.py"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import style_stats as ss  # noqa: E402

failures = []


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        failures.append(label)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


markers = json.loads(read("references/markers.json"))
try:
    for d in markers["dosage"]:
        [re.compile(ss.norm_pat(p)) for p in d["patterns"]]
    [re.compile(ss.norm_pat(v["pattern"])) for v in markers["never"]]
    check(True, "markers.json patterns compile")
except re.error as e:
    check(False, f"markers.json patterns compile ({e})")

bad = ss.check_data(markers, read("tests/bad_draft.txt"))
names = {v["name"].split(" (")[0] for v in bad["never"]}
check({"exclamation mark", "ellipsis", "marketing superlatives"} <= names, "check: never-list catches a bad draft")
good = ss.check_data(markers, read("tests/sample_draft.txt"))
check(not good["never"], "check: a clean draft has no never-list hits")
check(any(d["status"] == "too many" for d in good["dosage"]), "check: signature overdose is reported")
example = ss.check_data(markers, read("tests/example_essay.txt"))
check(not example["problems"], "check: the published example essay passes dosage and never-list")

prof = json.loads(read("references/profile.json"))
res = ss.compare_data(prof, ss.analyze_text(read("tests/sample_draft.txt")))
check(0 <= res["score"] <= 100 and len(res["top_fixes"]) <= 3, "compare: score and top fixes produced")
check(not ss.overlap_data(read("tests/sample_draft.txt"), [read("references/anchors.md")], 6)["shared_sequences"],
      "overlap: sample draft copies nothing from the anchors")

print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'}")
sys.exit(1 if failures else 0)

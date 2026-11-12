#!/usr/bin/env python3
"""Checks a test run against the pass rules and estimates the full run.

  python3 test_report.py            reads data/test.db and logs/test.log, writes reports/test/test_report.md

Pass rules:
1. no paper skipped (every paper chosen for reading has a note)
2. at least 70% read in full or matched to the Open Source Asset Pricing dataset
3. at least 70% of method cards state a trigger, a holding period and a return
4. the summary check finds no claim that contradicts its notes
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def stated(value):
    value = (value or "").strip().lower()
    return bool(value) and not value.startswith("not reported")


def main():
    db = sqlite3.connect(f"file:{HERE / 'data' / 'test.db'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    papers = db.execute("""SELECT p.*, GROUP_CONCAT(t.theme, '; ') AS themes FROM paper_themes t
                           JOIN papers p ON p.pid = t.pid WHERE t.picked = 1 GROUP BY p.pid""").fetchall()
    settings = json.loads((HERE / "research.json").read_text(encoding="utf-8"))
    total = len(papers)
    skipped = [p for p in papers if not p["notes"]]
    cards, full_or_dataset, by_source = [], 0, {}
    for paper in papers:
        notes = json.loads(paper["notes"]) if paper["notes"] else {}
        paper_cards = notes.get("method_cards") or []
        cards += paper_cards
        dataset = any(card.get("source_note") for card in paper_cards)
        full = (paper["text_source"] or "").startswith("full text")
        full_or_dataset += full or dataset
        label = paper["text_source"] if not dataset or full else (paper["text_source"] + " + dataset")
        by_source[label] = by_source.get(label, 0) + 1
    has_number = lambda value: stated(value) and bool(re.search(r"\d", value or "")) and "not reported" not in (value or "").lower()
    complete = [c for c in cards if stated(c.get("trigger")) and has_number(c.get("holding_days"))
                and has_number(c.get("reported_return"))]
    meta = {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM meta")}
    check = meta.get("summary_check") or ""
    rounds = re.split(r"\n## Round \d+", check)
    last = rounds[-1] if len(rounds) > 1 else ""
    contradicted = last.count("**contradicted**")
    unsupported = last.count("**not supported**")

    # time: from the log of this test
    log = (HERE / "logs" / "test.log").read_text(encoding="utf-8", errors="replace").splitlines()
    stamps = [datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S") for line in log if re.match(r"\d{4}-\d\d-\d\d \d\d:", line)]
    starts = [i for i, line in enumerate(log) if "Model:" in line]
    first = stamps[0] if stamps else None
    if starts:
        first = datetime.strptime(log[starts[-1]][:19], "%Y-%m-%d %H:%M:%S")
    wall_minutes = (stamps[-1] - first).total_seconds() / 60 if stamps and first else 0
    reads = [p["read_seconds"] or 0 for p in papers if p["notes"]]
    read_minutes = sum(reads) / max(len(reads), 1) / 60
    screens = db.execute("SELECT AVG(screen_seconds) AS s, COUNT(*) AS n FROM paper_themes WHERE screened_at IS NOT NULL").fetchone()
    screen_seconds = screens["s"] or 0
    # full run: run 1's budgets per theme, seven themes
    b = settings["budgets"]
    themes = len(settings["themes"])
    full_reads = themes * (b["read_per_theme"] + b["snowball_read_per_theme"])
    full_screens = themes * (b["screen_per_theme"] + b["snowball_screen_per_theme"])
    fetch_minutes = max(wall_minutes / max(total, 1) - read_minutes - screen_seconds * (screens["n"] or 0) / 60 / max(total, 1), 0)
    estimate_hours = (full_reads * (read_minutes + fetch_minutes) + full_screens * screen_seconds / 60
                      + themes * 3 + 15) / 60

    rules = [
        ("No paper skipped", not skipped, f"{len(skipped)} of {total} have no note"),
        ("At least 70% read in full or matched to the dataset", total and full_or_dataset / total >= 0.7,
         f"{full_or_dataset} of {total} ({full_or_dataset / max(total, 1):.0%})"),
        ("At least 70% of cards have trigger, holding period and return", cards and len(complete) / len(cards) >= 0.7,
         f"{len(complete)} of {len(cards)} ({len(complete) / max(len(cards), 1):.0%})"),
        ("Summary check: no claim contradicts its notes", bool(check) and contradicted == 0,
         f"{contradicted} contradicted and {unsupported} not supported after the last round" if check else "check did not run"),
    ]
    lines = ["# Test run report", "", f"Papers chosen for reading: {total}, method cards: {len(cards)}.", "",
             "| Rule | Result | Detail |", "|---|---|---|"]
    lines += [f"| {name} | {'pass' if ok else 'FAIL'} | {detail} |" for name, ok, detail in rules]
    lines += ["", "## Full text rate per source", "", "| Read from | Papers | Share |", "|---|---|---|"]
    lines += [f"| {label} | {count} | {count / max(total, 1):.0%} |"
              for label, count in sorted(by_source.items(), key=lambda item: -item[1])]
    full_total = sum(count for label, count in by_source.items() if label.startswith("full text"))
    lines += ["", f"Full text from any source: {full_total} of {total} ({full_total / max(total, 1):.0%})."]
    core_rows = db.execute("SELECT COUNT(*) AS n, SUM(LENGTH(text) > 0) AS found FROM core_cache").fetchone() \
        if db.execute("SELECT name FROM sqlite_master WHERE name = 'core_cache'").fetchone() else None
    if core_rows:
        lines.append(f"CORE in the background: asked about {core_rows['n']} papers, full text for {core_rows['found'] or 0}.")
    if skipped:
        lines += ["", "## Papers without a note", ""]
        lines += [f"* P{p['pid']} {p['title']} ({p['year']}): {p['read_error']}" for p in skipped]
    lines += ["", "## Time", "",
              f"* Whole test: {wall_minutes:.0f} minutes for {total} papers ({wall_minutes / max(total, 1):.1f} minutes per paper, all steps).",
              f"* Model reading: {read_minutes:.1f} minutes per paper on average.",
              f"* Finding full text: about {fetch_minutes:.1f} minutes per paper.",
              f"* Screening: {screen_seconds:.0f} seconds per paper.",
              f"* Full run estimate: {full_reads} reads and about {full_screens:,} screenings, so about "
              f"{estimate_hours:.0f} hours ({estimate_hours / 24:.1f} days)."]
    out = HERE / "reports" / "test" / "test_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()

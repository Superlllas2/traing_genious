# Run 2 library: what each file holds

Frozen on 28 October 2026. Run 2 covers news and event trading over days to weeks: 4,903 papers screened, 380 chosen, 378 read (261 from full text), 1,180 method cards.

## Start here
* `run2_final_check.md`: how the run went and every later correction. It has the totals, the pass rules per theme, the 26 anchor papers, what each update changed, and how the library was frozen.
* `method_cards.csv`: the main input. One row per method card (1,180), with these columns:
  * paper id and method family
  * source type (full text, dataset, secondary or abstract) and asset class
  * version ("working paper" for Hou 2007 and Lazy Prices)
  * the card fields: trigger, direction, entry, holding days, reported return, after costs, stocks, market and years, still works, data needed, storyline fit, retail usable
  * `checked`: marks cards checked by hand against the paper
* `01_...md` to `07_...md`: one chapter per theme. Each has a bottom line, a table of method families (best evidence first), the best methods, where the evidence is weak, numbers worth remembering, what it means for traders and for the app, papers to read, and the list of every paper read for the theme.

## The chapters
1. `01_events_that_make_prices_drift.md`: drift after earnings, analyst, buyback and other events (71 papers)
2. `02_news_spreading_to_linked_companies.md`: news moving to customers, suppliers, peers and industries (70 papers)
3. `03_text_and_attention_signals.md`: news tone, filings, search volume, LLM signals (72 papers)
4. `04_already_priced_in_or_not.md`: when the market underreacts or overreacts (70 papers)
5. `05_does_it_still_work.md`: decay after publication, replication, trading costs (70 papers)
6. `06_from_signal_to_trade.md`: costs, holding periods, stops, sizing, diversification (53 papers)
7. `07_skill_or_luck.md`: telling real edges from luck and overfitting (70 papers)

## Other reports
* `summary.md`: the model's draft summary, which turns the chapters into app requirements. Treat it as a draft: the two flags at the end (findings 2 and 8) came from a check by hand.
* `summary_check.md`: the automatic check of the summary (0 flags this time).
* `papers.csv`: one row per paper read. It gives themes, relevance, title, authors, year, venue, citations, where it was read from, strength, key findings, the line for the app, and a link.
* `claude_pack.md` (2 MB): everything in one file for a claude.ai project: every note, all chapters and the summary.
* `progress_01` to `progress_07`: the pass rules per theme, written as each theme finished on 25 and 26 October. The counts were before the working paper update.
* `phase1_report.md`: what phase 1 (search, screen, choose, fetch) produced on 20 October.

## Getting more full texts
* `wanted.csv`: every chosen paper still without a full text, ranked: anchors first, then by importance.
* `zotero_import.ris`: the top 100 of that list plus the Elsevier papers the fetch script was refused, ready to import into Zotero.
* `zotero_anchors.ris`: the anchor papers that lacked a full text on 25 October. All 26 anchors have a full text now.
* `papers_to_fetch.html`: the 21 October list of papers to fetch, as a clickable page.
* `saxion_fetch/` and `saxion_fetch.zip`: `fetch_entitled.py`, its README and its wanted list. The script downloads papers through the Wiley and Elsevier text mining APIs on Saxion's network.

## History
* `run2_test_review.md` and `run2_test3_review.md`: reviews of the test runs on 18 and 19 October. They are left as written, so they still say "not stated".
* `test/`: files from the test runs.

## Outside reports/
* `data/research.db`: the database. It holds every paper, note, card, chapter and cached text.
* Backups taken before each change:
  * `data/research_backup_before_phase2.db`
  * `data/research_backup_before_anchors.db`
  * `data/research_backup_before_working_papers.db`
  * `data/research_backup_before_hou_fix.db`
  * `data/research_backup_before_freeze.db`
* `pdfs/`: the PDFs you added (Saxion, Zotero, your own folder, OCR scans, and `working_papers/` with Hou 2007 and Lazy Prices).
* `research.json`: the settings: themes, budgets, the 26 anchors, model settings.
* `FROZEN`: while this file exists, run, rewrite, report, paper, import-pdfs and zotero-list refuse to change the library.
* `library_final_2026-10-28/`: a read only copy of reports/, the database and research.json. `MANIFEST.sha256` holds a checksum for each file.

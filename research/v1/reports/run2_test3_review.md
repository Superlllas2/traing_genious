# Run 2 test with new sources: review

Test of 19 October 2026: all 7 themes, 2 papers each, 14 papers, 2.2 hours. Machine sources only, no publisher websites and no SSRN. CORE ran in the background. Wiley and Elsevier text mining were off: no keys yet, and the Spark is not on a subscriber's network. Files: `reports/test/` (chapters, `summary.md`, `summary_check.md`, `method_cards.csv`, `zotero_import.ris`, `wanted.csv`, `test_report.md`).

## Pass rules

| Rule | Result | Detail |
|---|---|---|
| No paper skipped | fail | 1 of 14: P299 (Barber and Odean 2000) |
| At least 70% read in full or matched to the dataset | **pass** | 12 of 14 (86%) |
| At least 70% of cards have trigger, holding period and return | fail, just | 16 of 24 (67%) |
| Summary check finds no contradiction | fail | 8 left after 2 rounds, most of them wording |

## Full text rate per source

| Source | Full texts | Share of 14 |
|---|---|---|
| OpenAlex repository copies | 5 | 36% |
| Unpaywall repository copies | 2 | 14% |
| arXiv | 0 | 0% |
| CORE (background, 7 papers asked) | 0 | 0% |
| Wiley and Elsevier text mining | not active | |
| **Any full text** | **7** | **50%** (17% in the test before) |

Without full text:
* 3 papers matched the Open Source Asset Pricing dataset (P5 and P35 for theme 1 and 2 signals, P108 Menzly and Ozbas).
* 6 got secondary notes from citing papers.
* 1 failed.

Anchor papers read in full: Ke, Kelly and Xiu; Hou, Xue and Zhang; Hirshleifer, Lim and Teoh; Moreira and Muir; Barras, Scaillet and Wermers.
Anchors from secondary sources only: Bernard and Thomas, Chan 2003, DellaVigna and Pollet, Cohen and Frazzini, Menzly and Ozbas.

## Why each rule failed, and the fix

1. **P299 skipped.** Two things went wrong at once:
   * Semantic Scholar answered "too many requests" every time, so the paper got no citing sentences.
   * The model then used its whole 16,000 token budget thinking, twice (18 minutes), and wrote no answer. It also hit the cap once on P160 before succeeding.

   Fix: raise `read_max_tokens` to 32,000 (it still fits in the 65k context) and wait longer between Semantic Scholar retries. A free Semantic Scholar key (semanticscholar.org/product/api) removes the shared limit.
2. **Cards at 67%.**
   * Full text cards: 12 of 15 complete (80%).
   * Dataset cards: 3 of 3.
   * Secondary cards: 1 of 6. Citing papers rarely quote the return or the holding period.

   More full text fixes most of this: run `fetch_entitled.py` at Saxion, then Zotero for the rest.
3. **The summary check is too strict, and its fixes make new problems.**
   * About half of the 8 "contradictions" are wording, for example "after 24 months" against "around 24 months", or "significantly larger" against "far stronger".
   * Some are real. "Earnings surprises cause a 60 day drift" is not in the notes. "Momentum is the most reliable predictor" overstates P263.
   * The rewrite step changes whole sentences and adds new claims, which round 2 then flags.

   Fix:
   * Have the checker flag only a different number, direction or condition.
   * Have a second question confirm each flag.
   * Replace only the flagged sentence instead of rewriting the summary.
4. **Two more problems found along the way:**
   * arXiv and Semantic Scholar answered "too many requests" (HTTP 429), and the code treated that as a block for the rest of the run. Fix: wait and try again on 429; only 401 and 403 count as a block.
   * CiteSeerX timed out 7 times, at 60 seconds each. Fix: skip a site for the rest of the run after its first timeout.
   * Secondary cards wrote "still works: mixed, cited in recent papers". Being cited is not evidence that a pattern still works. Fix: one line in the reading prompt.

## Time

* 9.4 minutes per paper, all steps: reading 5.8 minutes, finding text 3.3 minutes, screening 3 seconds.
* Full text reads take 3.5 to 13 minutes. Secondary reads take 2.5 to 13 minutes.
* **Full run estimate: about 79 hours (3.3 days)** for 490 reads and about 4,900 screenings. The timeout fixes should save about 1 to 2 minutes per paper, which brings it to about 2.5 to 3 days.

## Next steps
1. Apply the fixes above (small code changes) and run a short test again.
2. Get a Semantic Scholar key, a Wiley TDM token and an Elsevier API key.
3. Start the full run. When it is done, run `fetch_entitled.py` on Saxion's network with `reports/wanted.csv`, then Zotero for the rest, then `import-pdfs`. Only the affected chapters are rewritten.

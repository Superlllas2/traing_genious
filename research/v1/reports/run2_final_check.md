# Run 2: final check

Run 2 (methods: trading on news and events over days to weeks) finished on 26 October 2026 at 17:27. Phase 1 (search, screen, choose, fetch) ran on 20 October; phase 2 (reading, chapters, summary) ran from 25 October 14:44 to 26 October 17:27.

## Totals
* 4,903 papers screened. 380 chosen for reading (7 themes, run 1's budget per theme; theme 6 ran out of candidates at 53). 378 read.
* How they were read:
  * 261 from full text (69%), including the two working papers added on 27 October
  * 79 from the abstract plus sentences in citing papers
  * 7 from citing papers only
  * 31 from the abstract only
* 1,180 method cards, 1,167 of them on stocks. 730 of the stock cards (63%) state a trigger, a holding period and a return with numbers.
  * Since 27 October, a return that says "not reported" or "not recorded" no longer counts, even when the text holds other numbers such as regression coefficients. This moved 11 cards in 5 papers out of "complete".
* Where the full texts came from:
  * 144 from your PDFs: Saxion text mining 76, Zotero 11, your own folder 57 including 6 OCR'd scans
  * the rest from repository copies (OpenAlex, Unpaywall), CORE and arXiv

## Pass rules per theme

| Theme | No paper skipped | Full text or dataset 70% | Complete cards 70% |
|---|---|---|---|
| 1 Events that make prices drift | pass | pass (75%) | fail (64%) |
| 2 News spreading to linked companies | fail (1: P39, no text anywhere) | fail (59%) | fail (65%) |
| 3 Text and attention signals | pass | pass (71%) | fail (62%) |
| 4 Already priced in or not | pass | pass (81%) | pass (72%) |
| 5 Does it still work | fail (1: P3630, a repeated copy of Replicating Anomalies; the real copy P3629 was read in full) | pass (83%) | fail (64%) |
| 6 From signal to trade | pass | pass (77%) | fail (63%) |
| 7 Skill or luck | pass | pass (76%) | fail (58%) |

The card rule fails mainly because papers read from abstracts and citing sentences rarely state a return and a holding period. Their cards keep "not reported" on purpose; they are not pressed for numbers.

## Anchor papers (task 8)
All 26 anchors were found and read, all 26 from the full text. Each anchor is matched to its one best paper: same surnames and team size, then the closest year (OpenAlex sometimes lists the working paper year, up to 4 years early), then a full text.

| Anchor | Paper | Read from | Complete cards |
|---|---|---|---|
| Bernard and Thomas 1989 | P5 | full text (your PDF) | 4 of 4 |
| Chan 2003 | P88 | full text (your PDF) | 2 of 2 |
| Womack 1996 | P280 | full text (your PDF, OCR) | 6 of 6 |
| Ikenberry, Lakonishok and Vermaelen 1995 | P481 | full text (your PDF) | 4 of 4 |
| Cohen, Malloy and Pomorski 2012 | P7238 | full text (Unpaywall) | 4 of 4 |
| Cohen and Frazzini 2008 | P83 | full text (your PDF) | 2 of 2 |
| Menzly and Ozbas 2010 | P1184 | full text (your PDF) | 6 of 8 |
| Hou 2007 | P117 | full text (your PDF, working paper version) | 0 of 10 (the paper reports regression coefficients, not a strategy return) |
| Ali and Hirshleifer 2020 | P6243 | full text (OpenAlex) | 2 of 8 |
| Cohen and Lou 2012 | P1568 | full text (OpenAlex) | 6 of 9 |
| Tetlock, Saar Tsechansky and Macskassy 2008 | P6039 | full text (your PDF) | 1 of 5 |
| Cohen, Malloy and Nguyen 2020 (lazy prices) | P6261 | full text (your PDF, working paper version) | 4 of 6 |
| Ke, Kelly and Xiu 2019 | P2129 | full text (Unpaywall) | 8 of 8 |
| Lopez Lira and Tang 2023 | P147 | full text (arXiv) | 8 of 8 |
| DellaVigna and Pollet 2009 | P81 | full text (your PDF) | 3 of 3 |
| Hirshleifer, Lim and Teoh 2009 | P82 | full text (OpenAlex) | 2 of 2 |
| Engelberg, McLean and Pontiff 2018 | P3472 | full text (your PDF) | 4 of 6 |
| McLean and Pontiff 2016 | P3531 | full text (your PDF) | 1 of 1 |
| Hou, Xue and Zhang 2020 | P3629 | full text (your PDF) | 4 of 8 |
| Novy Marx and Velikov 2016 | P3544 | full text (OpenAlex) | 8 of 8 |
| Martineau 2022 | P15 | full text (OpenAlex) | 3 of 3 |
| Moreira and Muir 2017 | P4152 | full text (OpenAlex) | 7 of 7 |
| Harvey, Liu and Zhu 2016 | P80 | full text (arXiv) | 2 of 2 |
| Barras, Scaillet and Wermers 2010 | P5047 | full text (OpenAlex) | no cards (tests fund skill, not a trading rule) |
| Bailey and Lopez de Prado 2014 | P5341 | full text (your PDF) | no cards (a statistics method) |
| Seru, Shumway and Stoffman 2010 | P5470 | full text (your PDF) | no cards (learning, not a trading rule) |

## Working paper update (27 October)
* Hou 2007 (P117) and Lazy Prices (P6261) were reread from the working paper PDFs you added (pdfs/working_papers/). Their cards are tagged "working paper" in the `version` column of method_cards.csv.
* Every number on their cards was checked against the paper by hand (the `checked` column). Tables are cited by title, not number, because the table numbers in the text do not always match the table labels.
* Chapters 1 to 6 were rewritten; chapter 7 does not cite either paper and is unchanged. No other paper's notes changed.
* The summary was not rewritten, so it still reflects the old cards.
* Known gaps in the rewritten chapters:
  * Chapter 2 (news spreading to linked companies) does not discuss Hou's own findings in its text; its table shows only the dataset card (IndRetBig). The chapter ranks cards with a return first, and Hou's cards have none.
  * The model grouped Hou's cards under momentum and volatility families in chapters 4 and 6; they belong in an intra industry lead lag family.
* Time estimator fixed: it now counts only time the run was actually working (31.8 hours for run 2, not the 148 hours between start and end), and its estimate of what is left includes the papers still to read.

## The summary: treat it as a draft
* Rewritten on 28 October from the rewritten chapters.
* The checker used to list claims even when its own reasoning said the notes back them, and the code then deleted or narrowed correct sentences. This happened 36 times out of 44 in one round. Such flags are now dropped, along with repeats and claims in "What the research does not answer yet". The draft before the check is now stored too (summary_draft).
* This time the check flagged nothing. A check by hand found two problems, listed under "Flags for review" at the end of summary.md:
  * Finding 2: the 6.40% (P3512) holds only for February to April.
  * Finding 8: most of the 8% fund spread (P3681) is explained by common factors, not skill.
* The summary cites neither Lazy Prices nor Hou. The model picks its 10 findings from the chapters, and neither paper made the cut.
* So build the final review from method_cards.csv and the chapters, not from summary.md.

## Files for the claude.ai project
* `method_cards.csv`: every card with its paper id, method family, source type (full text, secondary or dataset) and asset class. This is the main input.
* `01_...md` to `07_...md`: one chapter per theme, each with a method family table (best evidence first).
* `claude_pack.md` (2.1 MB): every note, all chapters and the summary.
* `papers.csv`: one row per paper.
* `summary.md` and `summary_check.md`: the draft summary and its check.
* `progress_01` to `progress_07`: the pass rules per theme.

## Second update (28 October)
* Hou's 10 cards now carry one family, "Intra industry lead lag", in all 5 of his themes (chapters 1, 2, 4, 5 and 6). Before, only theme 1 had stored a label ("Price Momentum and Reversal"); the other chapters labelled his cards on the fly, under momentum, volatility and earnings surprise families.
* New chapter rule: each chapter gets the list of its papers whose cards report no strategy return, and must cite each one with the numbers it gives (coefficients, t stats), saying plainly that it reports no strategy return. 67 papers are like this (at the time, Hou's cards said "not reported" and the other 66 "not stated"; since the final update all say "not reported").
* Chapters 1 to 6 were rewritten. Chapter 7 is unchanged: its one paper of this kind was already cited.

| Chapter | Words | Papers cited in text | No return papers cited |
|---|---|---|---|
| 1 Events that make prices drift | 1,030 to 1,205 | 29 to 51 of 71 | 7 to 17 of 17 |
| 2 News spreading to linked companies | 1,234 to 1,268 | 18 to 36 of 70 | 2 to 17 of 17 |
| 3 Text and attention signals | 1,056 to 1,132 | 20 to 31 of 72 | 3 to 19 of 19 |
| 4 Already priced in or not | 1,148 to 1,142 | 18 to 26 of 70 | 1 to 10 of 10 |
| 5 Does it still work | 1,129 to 1,183 | 14 to 27 of 70 | 0 to 5 of 6 |
| 6 From signal to trade | 1,243 to 1,010 | 20 to 23 of 53 | 1 to 6 of 6 |

* Lazy Prices note corrected by hand: the paper says the changers (the short side) have lower shorting fees than the middle quintiles, and that limits to arbitrage are not a significant contributor. The note had said "shorting costs high, may eat profits".
* Chapter 3 corrected by hand in 4 places where the model had mixed up the Lazy Prices numbers: it had tied 34 bps to Risk Factors changes and 188 bps to negative words.
* The counting bug (a "not recorded" return counted as complete) touched 11 cards in 5 papers (P117, P483, P1184, P5815, P6682), all from the Open Source Asset Pricing dataset. Those cards are added after the reread decision, and chapters never use the complete flag, so no reading or chapter text changed. Only the percentages did.
* All 26 anchors' matched papers carry the anchor paper's own title (research.json holds only short labels, so I compared against the published titles). Eight have a different year in OpenAlex, from working paper or online first dates: Ali and Hirshleifer (2019), Cohen and Lou (2011), Lopez Lira and Tang (2026), McLean and Pontiff (2012), Hou, Xue and Zhang (2018), Novy Marx and Velikov (2014), Harvey, Liu and Zhu (2015), Seru, Shumway and Stoffman (2009).
* Against a snapshot taken before this update, only P117's and P6261's notes changed.

## Final update and freeze (28 October)
* Hou's finding that the lead lag is mostly a bad news effect (0.2841 after negative weeks against 0.1283 after positive weeks; small stocks, weekly horizon) was added by hand to chapters 1, 2, 4, 5 and 6, next to his 0.2304 coefficient.
* Chapter 5 now cites its last uncited paper with no strategy return, P31 (text based earnings drift; abstract and citing papers only).
* Chapter 6 compared with the version before the 28 October rewrite. Lost in the rewrite:
  * trading costs and execution, all restored by hand from the notes:
    * round trip cost of 0.57% for the largest stocks against 3.81% for the smallest (P5990)
    * the warning against strategies that turn over more than 50% of the portfolio monthly, in the trader and app sections (P3544)
    * reported returns before costs: long run reversal (P5772), momentum (P5783)
    * retail flow signals need order flow data retail traders lack (P5972)
    * the stop loss disagreement: fixed stops near optimal in one model (P4702), degrading returns on Australian stocks (P4696)
    * selling winners too early and holding losers (P4363)
  * not restored, because they are not about costs or execution:
    * momentum 0.853% a month in low coverage stocks (P5783)
    * stock splits, 1 to 3 year horizon (P5949)
    * insider purchases 4.5% over a year (P6936)
    * the data end years of P5 (1986) and P5777 (1990)
    * P4691 and P4260 in "Read these yourself"
  * also not restored: the old sentence that insider filings "may be delayed" (P6936), which the notes do not say.
* "not stated" is now "not reported" everywhere: 3,143 places in the notes, 393 in the chapters, all reports and the code (so new cards say "not reported" too). The old test reviews (run2_test_review.md, run2_test3_review.md) are left as they were written.
* Against a snapshot taken before this update, every note differs only by that wording change.
* The library is frozen: the FROZEN file makes run, rewrite, report, paper, import-pdfs and zotero-list refuse to run (test runs still work). A read only copy of everything is in library_final_2026-10-28/, with a SHA-256 checksum for each file in MANIFEST.sha256.

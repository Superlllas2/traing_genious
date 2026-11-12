# Run 2 test run: review

Test run on 18 October 2026, in `trading_researcher_run2`, theme 1 only ("Events that make prices drift"), first 3 queries, 5 papers read. The files are in `reports/test/`: the chapter, `method_cards.csv`, `papers.csv` and `claude_pack.md`.

## What works
* Every note has the new `method_cards` field. The model writes "not stated" for anything the abstract does not give, and does not make numbers up.
* The chapter puts the method card table right after the bottom line, best evidence first, and the text walks down the table.
* The task 1 fix holds: the chapter took 72 seconds, with no "ran out of tokens" warnings.
* Task 6 works:
  * P5 (Bernard and Thomas 1989, where the only "abstract" is 99 characters of keywords) and P40 (no abstract at all) were marked "no text" instead of getting filler notes.
  * The next best papers took their reading slots.
* Two anchor papers turned up even in this small test: Womack 1996 (P90, read) and Bernard and Thomas 1989 (P5, skipped as no text).

## Problems to know before the full run
1. **No full text in the test.** All 5 notes come from abstracts. Every publisher link was blocked (HTTP 403 from doi.org, Wiley and ScienceDirect). Abstracts rarely give the holding period, the costs or the years, so most card fields say "not stated". Run 1 got full text for 50 of 273 papers (18%). Expect about the same in run 2 unless the reader also looks for free copies (SSRN, NBER, arXiv, author pages).
2. **Anchor papers without a free copy get skipped.** Chan 2003 (P40) has no abstract in OpenAlex and its full text is blocked, so it is now "no text". That is better than a filler note, but these papers will show up as missed in the check after the run.
3. **Nearly empty cards clutter the table.** P1 got a card where everything except the name is "not stated". A small filter could drop cards that state none of: trigger, holding period, return.
4. **Small model slips:**
   * On P90's buy card, the "retail usable" reason talks about short selling, which only applies to the sell card.
   * The chapter still uses hyphens ("multi month", "short lived" written with hyphens). The program only swaps long dashes.

5. **The test summary misreads one paper.** Finding 4 says P71's profits disappear after costs. P71's note says the opposite: the 2 day profit holds after costs, if you trade fast.

## The three notes, in short
* **P90, Womack 1996 (analyst recommendations), strong, abstract.** Two cards:
  * After a new **sell** recommendation, the price keeps falling, about 9.1% over 6 months (about 126 trading days).
  * After a new **buy** recommendation, it rises a modest 2.4%, and the move is short lived.
  * Years and costs are not stated in the abstract.
* **P71, Green 2006 (early access to recommendations), moderate, abstract.**
  * Trading on upgrades and downgrades earns about 1.0% to 1.5% over 2 days after costs.
  * The best of it comes within 2 hours of the release before the market opens. That is too fast for a retail trader.
* **P1, Mendenhall 2004 (earnings drift and arbitrage risk), moderate, abstract.**
  * The drift after earnings news is larger when it is risky for professionals to trade against it. "Arbitrage risk" here means how hard the stock is to hedge.
  * Its card has no usable details. This is the case problem 3 is about.

## Decision for Ilia
The full run has 7 themes, run 1's budget per theme, and an estimated 1.5 days or more of run time. It is ready to start with `./start_spark.sh` in the run 2 folder. Problems 1 and 3 can be fixed first, which costs a small code change and another short test.

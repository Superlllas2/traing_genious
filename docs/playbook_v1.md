# Trading assistant playbook v1

28 October 2026 · Ilia Nevrov

> Note, 12 November 2026: the app now targets European markets first. The evidence in this playbook is mostly from US data, so each signal needs a check on European data. That is the first theme of research round 3.

## In one minute

Six methods in your library pass the rules for a long only retail trader: two entry signals and four exit or avoid alerts. The strongest science is about behavior and costs, so guardrails are half the product.

- Most published edges shrink by about half after publication and are small after costs (P3531, P3521). Classic earnings drift is gone for US stocks above microcap size since 2006 (P15), although the local model's chapters rank it first.
- Entry signals: opportunistic insider buying, with evidence up to 2021, and analyst upgrades backed by an earnings estimate raise.
- Exit or avoid alerts: big wording changes in annual reports, late earnings dates, credit downgrades or going concern opinions, and bad news at linked companies.
- The most durable findings are about investor behavior: overtrading, holding losers, chasing attention. These warnings help every user, whatever they trade.
- Only insider buying is tested after 2015. Your own timestamped alert log has to close that gap.

All core signals play out over days to months, so alerts within a few hours are fast enough.

## Selection rules

A method made the cut only if it passed most of these seven rules; turnover and recent evidence removed the most methods.

| Rule | Why | Source |
| --- | --- | --- |
| Priced over hours to weeks, not seconds | Headline news is priced on the day; daily news sentiment signals fade by day 3 to 6 | P3472, P2464 |
| Turnover under 50% a month, lower preferred | Above that, costs wipe out most anomaly profits | P3544 |
| Works in mid and large caps | A round trip cost 0.57% for the largest stocks and 3.81% for the smallest (1991 to 1993) | P5990 |
| Data you can get | News, filings and prices; not order flow or stock loan data | P5972, P5854 |
| Recent evidence | Returns fall by about half after publication, most clearly in the US | P3531, P6668 |
| Mostly long side | Borrow fees turn the average anomaly from 0.14% to minus 0.01% a month | P3532 |
| Fits storylines | An event that predicts a next event you can watch for | App design |

## Core signals

Two signals open positions and four tell you to exit or stay away; insider buying has the strongest and most recent evidence.

| | Moderate evidence | Strong evidence |
| --- | --- | --- |
| **Data after 2012** | B. Estimate backed upgrade (data to 2010, drift to 2014). F. Linked company bad news (replication to 2016) | A. Insider buying (data to 2021). C. Report wording change (data to 2014) |
| **Data ends by 2012** | D. Late earnings date (return data to 1998) | E. Downgrade, going concern (data to 1997 and 2005) |

Trust the strong and recent cell first. All four paper trade candidates below would sit in the lower half, since their data ends by 2012.

### A. Opportunistic insider buying (entry)

| Field | Detail |
| --- | --- |
| Trigger | Open market purchase by a CEO, CFO or director who does not trade on a fixed calendar pattern (P7238 sorts insiders by their past three years). Stronger with several insiders, or buying in consecutive months. |
| Act | Buy within days of the filing; a US Form 4 is due within two business days. |
| Expect next | Drift up: about a third of the year's extra return in the first month, three quarters within six months (P634). A positive earnings report or guidance raise confirms. |
| Proves it wrong | Insiders sell within months, a negative earnings surprise, or no outperformance vs the sector after six months. |
| Hold | 1 to 6 months |
| Evidence | About 0.4% a month above benchmarks, value weighted (P634, 1975 to 1996). Plus 4.5% over a year; top executives 5.0%; four straight months of buying 7.5% (P6936, 1975 to 1994). Opportunistic buyers beat routine ones (P7238, 1989 to 2007). Still present 2004 to 2021, stronger when retail attention is low: 1.12% vs 0.91% the next month (P5477). |
| Ignore | Insider sales carry no signal on average (P634); only large sales relative to the insider's stake look negative (P643, abstract only). |
| Costs | One round trip per position. Equal weighted results lean on small stocks, so trust the value weighted figures. |
| Data | Free from SEC EDGAR; needs three years of each insider's trades to separate routine from opportunistic. |
| Strength | Strong, with the most recent evidence in the library |

### B. Analyst upgrade backed by an estimate raise (entry)

| Field | Detail |
| --- | --- |
| Trigger | An upgrade where the analyst also raises earnings estimates for the next one or two years. |
| Act | Buy at the next day's open. The two day jump in P334 needs client access before the public release, so it is not yours to catch. |
| Expect next | A day one jump of about 3.64%, then about 1.62% more over the month, vs 0.61% for upgrades without an estimate raise (P354, 1994 to 2010). An earnings beat at the next report confirms. |
| Proves it wrong | Estimates are cut again, or there is no drift after a month. |
| Hold | About 1 month |
| Evidence | Persisted through 2010 (P354). Drift after recommendation changes was still present to 2014 and larger in bad times (P5883). When the report text contradicts the rating, prices follow the text (P1490, S&P 500, 1996 to 2008). |
| Costs | Not reported. The sample excludes stocks under $5 and the smallest fifth of firms. |
| Data | Mostly paid: recommendation and estimate feeds. |
| Strength | Moderate |

### C. Big wording change in an annual report (exit or avoid)

| Field | Detail |
| --- | --- |
| Trigger | A new annual or quarterly report (10K, 10Q) whose wording changed a lot vs the same report a year earlier, above all in Risk Factors. Add a negative tone score from a finance word list, not a general one (P6294). |
| Act | For holdings, review or trim. For new ideas, prefer firms whose reports barely changed. |
| Expect next | Slow underperformance. There is no reaction on filing day; the return builds over 6 months and lasts to 18 months without reversing (P6261). |
| Proves it wrong | No underperformance vs the sector within 6 months. |
| Hold | Watch for 3 to 6 months; the signal lasts up to 18 |
| Evidence | 0.34% to 0.58% a month, value weighted, non changers minus changers, before costs (P6261, US 1995 to 2014). Risk Factors changes alone reach up to 1.88% a month, equally weighted. |
| Costs | Low turnover. Shorting the changers was not unusually expensive (P6261). |
| Data | Free from SEC EDGAR; your local model can score the change. |
| Strength | Strong, but untested after 2014; expect about half after publication (P3531) |

### D. Late earnings date (exit or avoid)

| Field | Detail |
| --- | --- |
| Trigger | A company misses its own announced report date, or schedules its report later than usual. |
| Act | Do not buy before the report; consider trimming. |
| Expect next | Worse news. Each day late meant earnings about one cent per share worse; prices drifted down about 1.0% by the fourth day late (P5951, 1995 to 1998). Late schedulers report worse news, and stock prices ignore it until the report (P2916). |
| Proves it wrong | The report meets or beats consensus. |
| Hold | Until the report |
| Evidence | Old return data; later papers (2020 to 2024) still confirm the pattern. |
| Data | Company sites list dates for free; historical calendars are often paid. |
| Strength | Moderate |

### E. Credit downgrade or going concern opinion (exit or avoid)

| Field | Detail |
| --- | --- |
| Trigger | A bond rating downgrade, or an auditor's first going concern opinion. |
| Act | Exit or avoid. Do not short: after costs it did not pay (P3780). |
| Expect next | Downgraded stocks trailed by 10% to 14% over the next year, worst for small, low rated firms; upgrades showed nothing (P5978, 1970 to 1997, 26 of 28 years). After a first going concern opinion, stocks fell a further 14% over 12 months (P3780, 1993 to 2005). |
| Proves it wrong | Refinancing, an upgrade, or the stock beating its sector in the following months. |
| Hold | Avoid for 6 to 12 months |
| Evidence | Consistent across years, but the data is old. |
| Data | Rating actions appear in the news; audit opinions sit in the annual report, free. |
| Strength | Strong but old |

### F. Bad news at a linked company (exit or avoid)

| Field | Detail |
| --- | --- |
| Trigger | Bad news at a major customer, a supplier of hard to replace inputs, or the industry leader: a disaster, a bankruptcy filing or a big earnings miss. |
| Act | Alert on holdings linked to that company; review or trim. |
| Expect next | A partial reaction at once, then drift. Suppliers priced about 60% of customer news at once and the rest over about 6 months, mostly for bad news (P83, 1981 to 2004). After disasters hit suppliers of specific inputs, customers fell 2.37% across the 51 trading days around the event, most of it by ten days after (P326, 1978 to 2013). Small firms follow their industry leaders' bad news at a weekly horizon (P117). |
| Proves it wrong | The linked firm's next report shows no impact, or there is no drift after a month. |
| Hold | Alert window of 1 to 3 months |
| Evidence | Weaker for large stocks and recent years (P1179). A replication to 2016 finds 0.78% a month, half the original (P3629). Shared analyst coverage explains much of it (P6243). |
| Data | Major customers are listed in annual reports (free, needs parsing); industry codes are free. |
| Strength | Moderate; best as a warning, not a trade |

## Candidates to paper trade first

These four look promising but rest on one study or on data that ends by 2012; log them as paper trades before trusting them.

| Method | Trigger and hold | Evidence | Why not core yet |
| --- | --- | --- | --- |
| Management guidance surprise | Guidance above consensus: buy after two days, hold about 15 days. Below consensus: prices overshoot down, so buy after two days and hold 30 days | Good news: 1.50% over 15 days, more than the 1.03% spread. Bad news: 2.89% over 30 days before a 1.66% spread (P3105, 1995 to 2004, larger firms) | One study; data ends 2004 |
| Buyback completion | Buy when a buyback is reported complete or a new one is authorized; hold up to 12 months | 0.67% a month over the 12 months after completion; nothing between authorization and completion (P488, 1979 to 2010) | Fades after 24 months without new events; needs the buyback tables in 10Q reports |
| Dividend initiation | Buy after a first dividend; hold about a year | 7.5% above the market over a year; the rule paid in 22 of 25 years (P97, about 1969 to 1993) | Old data, no recent test |
| Russell index addition | Stocks just below the rank 1000 cutoff at the end of May; hold through June | About 5.6% in June vs near misses, then no drift (P888, 1996 to 2012) | Small caps, paid ranking data, one month a year |

## Not for v1

These failed on recency, turnover, access or the short side; several still feed the guardrails.

| Method | Why not | Source |
| --- | --- | --- |
| Classic earnings surprise drift, including the Friday and busy day versions | Gone for US stocks above microcap size since 2006; microcap drift lasts five days at most. Earlier, costs ate 70% to 100% of it | P15, P2, P9, P81, P82 |
| Daily news sentiment trading with language models | One day holds and daily turnover; value weighted versions lose money at 5 bps costs; the signal is gone by day 3 to 6. Use the model to read, not to trade daily | P147, P2464, P2050 |
| The two day jump after analyst upgrades | Needs access before the public release | P334 |
| Price momentum and factor portfolios | Price based, high turnover, prone to crashes; momentum costs 2.2% to 8.3% a year | P3766, P6211 |
| Peer momentum through shared analysts | Turnover of 313% a month against a break even cost of 42.5 bps | P6243 |
| Search volume spikes as a buy signal | Two weeks of gains, then a reversal; kept as a hype warning | P254 |
| Short only signals: shorting demand, short sale volume, curated conference calls | Retail shorting is costly and borrow fees erase anomaly profits; kept as avoid flags | P3532, P5854, P105, P2996 |
| A fixed 10% to 15% stop loss | Mixed: one student thesis without costs supports it, a trend study on Australian stocks found stops hurt | P4691, P4696, P4694 |
| Mutual fund momentum as proof of skill | Most of the 8% spread is common factors and costs | P3681 |

## Guardrails

Thirteen warnings apply to every user and every trade; they rest on the most replicated findings in the library, from US, Finnish and Taiwanese data.

| Guardrail | What the app does | Evidence |
| --- | --- | --- |
| Cost check | Estimates the spread from daily high, low and close, and compares the cost with the expected edge before each trade | The estimator matched exchange data with 0.74 correlation (P6810); a round trip cost 0.57% for the largest stocks vs 3.81% for the smallest (P5990, 1991 to 1993) |
| Order type nudge | Suggests limit orders or the closing auction instead of market orders | Individual losses came almost entirely from aggressive orders (P4260, Taiwan 1995 to 1999); closing auctions cut impact except for Nasdaq microcaps (P3770) |
| Turnover meter | Warns above 50% a month and shows the yearly cost drag | P3544. The most active households earned 11.4% a year vs 17.9% for the market (P413, 1991 to 1996) |
| Quick switch warning | Flags buying a new stock within three weeks of selling another | The new stock trailed the one sold by 5.82% over the next year (P4259, 1987 to 1993) |
| Holding losers warning | Flags selling a winner while holding a loser | People sold 20.1% of their gains but 12.6% of their losses; the winners sold beat the losers kept by 3.41% over the next year (P4363) |
| Hype warning | Flags buying after news spikes, extreme one day jumps or number heavy positive headlines | Attention driven buys trailed (P5774); lottery like stocks trailed by 1.18% a month (P129, 1962 to 2005); salient positive headlines gave back 5.4% over 60 days (P3218, 1998 to 2008) |
| Before earnings warning | Flags buying last year's top winners in the week before their report | They gained 1.58% in the 5 days before, then lost 1.86% in the 5 days after (P2891, 1971 to 2005) |
| Stale news check | Labels news that repeats last week's story | Reactions to stale news partly reversed within a week (P6305, 1984 to 2004) |
| Diversification meter | Shows the single stock risk left at the current number of holdings | 24 stocks removed 90% of it in calm years; 56 to 73 were needed in 2008 to 2011 (P4859) |
| Volatility sizing | Suggests smaller positions after a volatile month; never full Kelly sizing | A volatility managed market portfolio added 4.86% a year (P4152, 1926 to 2015); full Kelly brings deep drawdowns (P4542, P4544) |
| After a winning streak | Nudges against trading more after gains | Top funds that traded more after a good year trailed by 1.6% to 1.9% a year (P5483) |
| Decay label | Shows each signal's publication year and halves its expected return | Returns fell 58% after publication (P3531) and 51% in a 2026 update (P3521) |
| Track record | Logs every alert with a timestamp and shows how long until results mean anything | A Sharpe ratio of 2.0 with fat left tails needed about 5 years to prove skill (P7058); 10 variants tested on random data already show 1.57 (P5612) |

## Ten findings that matter most

This list replaces the local model's top ten, which led with earnings drift and mutual fund momentum; both fail against other notes in the library.

1. Published patterns lose about half after publication, but mainly in the US: 38 other markets showed no reliable decline (P3531, P3521, P6668). European stocks deserve a look.
2. Classic earnings drift is gone for US stocks above microcap size since 2006 (P15). Do not build the app around it.
3. Costs decide: turnover above 50% a month fails (P3544), and small stocks cost several times more to trade than large ones (P5990).
4. Retail losses come mostly from behavior: overtrading (P413), quick switching (P4259), holding losers (P4363), aggressive orders (P4260) and attention buying (P5774).
5. Signals now pay out fast: from 2005 to 2019, 86% of a four month anomaly return came in the first month and half in the first two weeks after the information date (P3512). Alerts must go out within days.
6. Opportunistic insider buying predicts returns, and still did from 2004 to 2021, more so when attention is low (P7238, P634, P5477).
7. Big wording changes in annual reports predict slow underperformance over 6 to 18 months, with no reaction on filing day (P6261). This is ideal work for a local model.
8. Analyst upgrades matter when an estimate raise backs them (P354); the well known two day jump is out of retail reach (P334).
9. Bad news spreads slowly to linked companies, especially small followers (P83, P117, P326). This is the storyline idea in its best tested form.
10. When many storylines are tested, apparent winners are often luck; the app needs deflated metrics and a long logged record (P5341, P5612, P7058, P6688).

## Corrections to the chapters and summary

These claims are wrong, overstated or misattributed when checked against the notes; the first four change what the app should do.

| Where | Claim | What the notes say | Impact |
| --- | --- | --- | --- |
| Summary finding 1; chapters 1, 3, 4, 6 | Earnings surprise drift, 4.2% over 60 days, is a reliable signal and stays positive after costs in small stocks | P5 covers 1974 to 1986, before costs. P15: no drift for US stocks above microcap size since 2006, five days at most for microcaps. P2: in illiquid stocks the long short loses 0.65% a month after full costs | High |
| Chapter 5 lead | Earnings drift survives costs in recent years | P15 contradicts it; the cited P3277 sample ends in 2005 | High |
| Summary finding 3; app rules | Filter out trades costing over 10 bps (P3544) | P3544 sets no such limit; it finds strategies under 50% monthly turnover survive. 10 bps is the cost assumed in daily news sentiment tests (P2129, P2452) | High |
| Summary finding 5; chapter 1 | Analyst upgrades earn 1.02% in two days after costs | P334 measured client trades in the first hours after a release before the open; the note marks it unusable for retail | High |
| Summary finding 8; chapter 7 lead | Mutual fund momentum is the best evidence of skill | P3681: common factors explain 4.6 of the 8 points, expenses 0.7, trading costs 1; only the worst funds keep underperforming | Medium |
| Chapter 1 | Earnings backed upgrades earn 3.11% a month | That is the long short figure, upgrades minus downgrades; the upgrade side drifts 1.62% over a month (P354) | Medium |
| Chapter 3 lead | After costs, earnings surprises earn 4% over 60 days | P5 reports no costs | Medium |
| Chapter 3 | Language model news sentiment is the most robust method | Value weighted versions lose money at 5 bps (P147); the 355% gain (P2452) is one two year window; the signal is gone by day 3 to 6 (P2464) | Medium |
| Chapter 2; summary app rules | Friday announcements earn 3.84% a month (P81) | Implausibly large for a calendar effect, and 3.84 also appears in P3472 as basis points a day. Check the paper | Medium |
| Chapter 2 | Lawsuit peers lose 4.21% after filings that later settle (P1831) | Settlement is known years later, so this is not tradable; the 0.33% drop before filing needs the filing date in advance | Medium |
| Chapter 4 | Bad news guidance earns 2.89% over 30 days, net of a 1.66% spread (P3105) | 2.89% is before the spread, so about 1.2% after it | Medium |
| Chapter 6 lead | Size factors have the strongest evidence after costs | Size earned minus 0.26% a month net after 2005 (P3511) and was not reliable from 1982 to 2002 (P615) | Medium |
| Chapter 6 | Set stop losses at 10% to 15% | One student thesis on 54 Swedish stocks without costs (P4691); stops hurt a trend system in P4696 | Medium |
| Chapter 4 | A 2% drift over 60 days equals 18% a year (P8) | 2% is each side; the long short earns about 4% a quarter, and that is the 18% a year | Low |
| Chapter 4 | Momentum is stronger in low coverage stocks: 0.824% vs 0.853% a month (P5783) | Those two numbers point the other way, and the note disagrees with itself: 0.824 minus 0.711 is 0.11, not the 0.42 it states. Check the paper | Low |
| Chapter 5 lead | Robust strategies net 0.37% to 0.92% a month after costs | The 0.92% (P3514) is before costs; its break even cost is 1.1% a round trip | Low |
| Chapter 7 | P5041 finds fewer than 16% of funds have true alpha | That is P7065 (Fama and French, US 1984 to 2006); P5041 studies UK funds | Low |
| Summary app rules | Warn above 50% monthly turnover (P3766); hold 24 to 50 stocks (P4859) | The 50% limit comes from P3544. P4859 gives 24 to 99 stocks depending on the measure and the period | Low |
| Note P2810 | Search spikes earn 4.38% a month in Australia (t 11.92) | Implausibly large; check before using | Low |

## Open questions and next research

The biggest gap is recency: only insider buying is tested after 2015, so the next research run should hunt for recent replications.

- Recent tests, after 2015, of annual report wording changes, estimate backed upgrades, late earnings dates, credit downgrades, guidance surprises and buyback completions.
- Europe: decay looks US specific (P6668), but no core signal is tested on European or Dutch stocks here. Director dealing disclosures under the EU market abuse rules are the obvious first test.
- Today's retail costs: the library's cost figures come from the late 1980s and early 1990s (P5990, P413, P4259). Zero commission brokers and tighter spreads change the math, so measure your own broker's fills.
- Long only returns: most papers report long short; the entry signals need long only numbers.
- Storyline confirmation: no paper tests whether waiting for a confirming next event improves returns. The closest are buyback completion (P488), the first reporter in an industry (P5985) and peer reactions reversing at a firm's own report (P1755).
- Speed today: how fast insider filings, 8K filings and rating actions are priced since 2015.
- Do warnings change behavior? Nothing in the library tests nudges inside trading apps.
- Reading accuracy: this run showed the local model mixing up numbers, so measure its error rate on event extraction before alerts rely on it.

## What to build first

Start with free data and the guardrails: five of the six core signals and every guardrail need only SEC filings, earnings dates, daily prices and the user's own trades.

1. Pull SEC EDGAR filings with timestamps: Form 4, 10K, 10Q and 8K.
2. Build the guardrails on daily prices and the user's trade history.
3. Start the alert log on day one: signal, time, price, expected next event and its deadline.
4. Paper trade the four candidates alongside.
5. Add paid analyst data for signal B only once the free signals show a record.

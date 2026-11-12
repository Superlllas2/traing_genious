# What the research says the app needs

## The 10 findings that matter most

1. Post earnings announcement drift yields 4.2% abnormal return over 60 days. This matters because it provides a reliable event driven signal for the app to track over weeks rather than minutes [P5].
2. Information rebalancing captures 6.40% annualized return in the first month after news. This matters because the app must trigger signals immediately on news release dates to capture the edge [P3512].
3. Transaction costs of 50 basis points per round trip can eliminate profits. This matters because the app must filter out trades where estimated costs exceed 10 basis points to ensure viability [P3544].
4. Small stocks show stronger drift but have higher trading costs. This matters because the app needs to balance signal strength against liquidity constraints for retail users [P5].
5. Analyst upgrades generate 1.02% return over two days. This matters because the app can use analyst recommendation changes as a short term confirmation signal [P334].
6. Customer momentum yields 1.45% monthly abnormal returns. This matters because the app should map customer supplier networks to predict supplier drift based on customer news [P83].
7. Search volume spikes predict momentum for two weeks then reversal. This matters because the app must warn users to exit search volume positions after two weeks to avoid reversal [P254].
8. Mutual fund winners outperform losers by 8% annually. This matters because the app can use fund performance as a proxy for skill in selecting stocks [P3681].
9. Anomaly returns drop 58% after publication. This matters because the app must warn users that historical returns are upper bounds and often decay [P3531].
10. Opportunistic insider buys predict drift with 82 basis points monthly alpha. This matters because the app should classify insider trades to filter noise from routine activity [P7238].

## What the app should do

* Link earnings surprises to 60 day hold storylines to capture drift [P5].
* Trigger alerts immediately on news release dates to capture information rebalancing [P3512].
* Filter out trades where estimated costs exceed 10 basis points to protect net returns [P3544].
* Map customer supplier networks for one month signals to identify connected peer momentum [P83].
* Warn users to exit search volume positions after two weeks to avoid reversal [P254].
* Classify insider trades as opportunistic or routine to filter noise [P7238].
* Block short signals on high cost stocks because borrow fees often negate profits [P3532].
* Highlight Friday earnings for higher drift potential due to investor distraction [P81].
* Suggest holding 24 to 50 stocks for diversification to reduce risk [P4859].
* Warn against high turnover strategies that exceed 50% monthly as costs destroy wealth [P3766].

## Traps the app must protect the user from

* Publication bias where signals decay after discovery [P3531].
* High transaction costs eroding small cap profits [P3544].
* Overreaction to salient news leading to reversal [P3000].
* Mistaking luck for skill in short track records [P5341].
* Herding behavior where following the crowd underperforms [P5067].
* Shorting constraints and fees negating profits [P5854].
* High turnover trading destroying wealth [P5472].
* Assuming pre 2000 data applies to modern markets [P3629].
* Social media sentiment predicting volatility rather than direction [P6299].
* Pre announcement price moves becoming less reliable [P2884].

## What the research does not answer yet

* Exact post 2020 returns for many strategies.
* Specific return numbers for many supply chain signals.
* How AI sentiment compares to human analyst sentiment in real time.
* Optimal stop loss percentage for all market conditions.
* Impact of new regulations on short selling costs.
* Long term performance of LLM news sentiment strategies.
* Effectiveness of strategies in European markets specifically.
* Real time cost estimation accuracy for retail traders.
* Correlation between retail attention and institutional flow.
* Durability of anomaly signals in high inflation environments.

## The 10 papers to read first

* P5: Post Earnings Announcement Drift. Why: Foundational paper on earnings surprise drift showing 4.2% return over 60 days.
* P3512: Information Rebalancing Strategy. Why: Shows how timing news release dates captures 6.40% annualized return in recent years.
* P3544: Fundamental Anomalies. Why: Details how transaction costs of 50 basis points reduce realized spreads and which signals survive.
* P3531: Anomaly Decay. Why: Documents 58% drop in returns after publication.
* P83: Customer Momentum. Why: Explains how news diffuses through supply chains to affect supplier stocks.
* P254: Search Volume Spikes. Why: Predicts short term momentum and reversal.
* P3681: Mutual Fund Momentum. Why: Shows 8% spread between winners and losers after costs.
* P7238: Insider Trading. Why: Opportunistic insider buy returns.
* P334: Analyst Upgrades. Why: Analyst upgrade returns over two days.
* P3277: PEAD Robustness. Why: Confirms 10.21% abnormal return over 120 days robust to costs.

## Flags for review

The automatic check flagged nothing this time; these came from a check by hand against the notes on 28 October.

* Finding 2 (P3512): the 6.40% annualized return holds during the high activity period, February to April, not "in the first month after news". Notes: "6.40% during the high activity period (February April), compared to 3.74% for the FF92 strategy".
* Finding 8 (P3681): the 8% a year spread is mostly not skill. Notes: common factors (market, size, book to market, momentum) explain 4.6 points of the 8, expenses 0.7 and transaction costs 1; US 1963 to 1993; shorting the worst funds is difficult in practice.

*Written by qwen3.5:122b on 2026-10-28 12:52, from 378 papers (261 read in full). Chapters: 01_events_that_make_prices_drift.md, 02_news_spreading_to_linked_companies.md, 03_text_and_attention_signals.md, 04_already_priced_in_or_not.md, 05_does_it_still_work.md, 06_from_signal_to_trade.md, 07_skill_or_luck.md.*

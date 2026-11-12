# Decisions

Last updated: 12 November 2026

## Decided

* **Product shape.** A feed with a light thinking layer on every item, two tabs (Recommended and All news), threads of linked news, and a Run thinking button that runs the layers as tests.
* **Depth in version zero.** Quick only (Facts, Pattern, Price and volume).
* **Markets.** Europe first, not the US. Start with the Netherlands plus three big markets (proposed: Germany, France, United Kingdom).
* **No watchlist limit.** Read all news. Track a company when its news looks important enough.
* **Company size is always stored.** Research shows signals are stronger in small stocks but trading them costs far more (round trip about 3.81% for the smallest against 0.57% for the largest, P5990). Every item carries a size label and small stocks get a cost warning.
* **First interface.** Telegram. Start with a private channel, open it to others later by hand.
* **Proof.** Nothing is concluded before it is tested. Ilia forward tests through the log. The log starts on day one and is never edited.
* **Success measure.** After three months, did Recommended items come before unusual price moves more often than All news items did?

## Open

* News sources and price data source for the four markets.
* Which model runs the light layer, and its measured error rate on a labelled test set.
* How the app reads the frozen research library on the Spark.
* Research round 3 themes and order (Europe evidence first).

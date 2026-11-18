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

* **One repository.** Everything needed for development lives in this repository, including the research text files under `research/`. The research database and the PDFs stay on the Spark.

## Open

* Data sources: proposed in [data_sources.md](data_sources.md). Waiting for the open checks run from the Spark, and Ilia's OK on the EODHD subscription.
* Which model runs the light layer, and its measured error rate on a labelled test set.
* Research round 3 themes and order (Europe evidence first).

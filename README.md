# Trading Genious

A news feed that thinks. It reads market news and filings all day, marks the items worth following, links them into threads, and on request runs a layered check of an idea. The user makes the trading decision. The app never trades.

## Documents

Everything is kept in this repository as plain markdown, so anyone with access to the repository can read it.

* [Product concept](docs/product_concept.md): what the software is and how it works
* [Playbook v1](docs/playbook_v1.md): the signals, guardrails and evidence from the research library
* [Data sources](docs/data_sources.md): where filings, news and prices come from for the four markets
* [Decisions](docs/decisions.md): what is decided and what is still open

## What lives where

* `docs/`: product concept, playbook, decisions.
* `research/`: text results of the research runs, one folder per frozen version. See [research/README.md](research/README.md).
* `scripts/`: helper scripts.
* App code (intake, light layer, threads, thinking runs, log, Telegram client) and the research pipeline code will be added here.
* Not in git: the research database and the PDFs. They stay on the Spark.

## Status

Planning. No app code yet.

# Trading Genious

A news feed that thinks. It reads market news and filings all day, marks the items worth following, links them into threads, and on request runs a layered check of an idea. The user makes the trading decision. The app never trades.

## Documents

Everything is kept in this repository as plain markdown, so anyone with access to the repository can read it.

* [Product concept](docs/product_concept.md): what the software is and how it works
* [Playbook v1](docs/playbook_v1.md): the signals, guardrails and evidence from the research library
* [Decisions](docs/decisions.md): what is decided and what is still open

## What lives where

* This repository: the app code (intake, light layer, threads, thinking runs, log, Telegram client).
* The research library (method cards, paper notes, database, PDFs) stays in its own folder on the Spark. It is frozen and read only. The app reads from it and nothing from it is copied here, except small exports the app needs.

## Status

Planning. No app code yet.

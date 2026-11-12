# Trading Genious

A news feed that thinks. It reads market news and filings all day, marks the items worth following, links them into threads, and on request runs a layered check of an idea. The user makes the trading decision. The app never trades.

## Documents

* Product concept v1: https://claude.ai/artifact/YH8Gy1o7wggrp7Lzf472r3
* Trading assistant playbook v1 (signals, guardrails, evidence): https://claude.ai/artifact/9g8B26b2eoHKNntYTFzZKV
* Decisions so far: [docs/decisions.md](docs/decisions.md)

## What lives where

* This repository: the app code (intake, light layer, threads, thinking runs, log, Telegram client).
* The research library (method cards, paper notes, database, PDFs) stays in its own folder on the Spark. It is frozen and read only. The app reads from it and nothing from it is copied here, except small exports the app needs.

## Status

Planning. No app code yet.

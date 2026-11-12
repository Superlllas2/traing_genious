# Research pipeline

This is the code that built the research library in `research/v1`. It runs on the Spark with a large local model (through Ollama). It finds research papers about trading and markets, reads them, and writes chapters, method cards and a summary of what the research means for the Trading Genious app.

This folder holds only code and settings. The database, the PDFs, the reports and the logs stay on the Spark (see "Where the data lives" below).

## What it does

1. **Searches** OpenAlex, a free catalog of research papers, with the searches for each theme in `research.json`, plus a "most cited first" pass so the classic papers are included.
2. **Screens** each abstract. The model gives it a relevance score from 0 to 10 for its theme.
3. **Chooses and fetches** the best papers. It uses a free full text when one exists (arXiv, open access PDFs, web pages, CORE). Everything else goes on a wanted list (`reports/wanted.csv`).
4. **Gets more full texts** from outside the pipeline. `fetch_entitled.py` downloads the papers Saxion's library has access to, and Zotero finds the rest. Both outputs go into `pdfs/`.
5. **Reads** each chosen paper. For each one it notes the data, the method, the key numbers, how strong the evidence is, and what the paper means for traders and for the app. It also writes method cards (trigger, holding period, return). Where it can, it checks the numbers against the Open Source Asset Pricing dataset (`osap.py`) and against Semantic Scholar's citing sentences (`s2_collect.py`).
6. **Writes** one chapter per theme, a summary, a summary check, `papers.csv`, `method_cards.csv`, and `claude_pack.md`, which puts everything in one file for Claude.

A run can be stopped and started again at any time without losing work. When Telegram is set up, it sends progress messages.

## Setup (once)

```
cd research_pipeline
bash install_spark.sh            # makes .venv, installs pypdf, checks Ollama and the model
cp config.example.json config.json
chmod 600 config.json            # then fill in your own keys (or run: researcher.py setup)
```

`config.json` holds your private keys: the Telegram bot, OpenAlex, the Unpaywall email, CORE, Wiley, Elsevier and Semantic Scholar. Every key is optional. Without one, that source is skipped or runs more slowly. Never commit `config.json`. The repository's `.gitignore` keeps it out.

`research.json` holds what to research: who it is for, the language, the model, the budgets, the themes with their searches, and the anchor papers. You can edit it freely. How the model screens, reads and writes is set in `prompts.py`.

The pipeline needs Python 3 and the standard library, plus `pypdf` for reading PDFs (`requirements.txt`).

## Commands

Run each command from this folder with `.venv/bin/python researcher.py <command>`, or with `python3 researcher.py <command>`.

| Command | What it does |
|---|---|
| `run` | Start the research, or continue where it stopped. `--phase 1` searches, screens, chooses and fetches, writes `reports/wanted.csv` and stops. `--phase 2` reads theme by theme (PDFs in `pdfs/` first) and writes a report after each theme. `./start_spark.sh` runs it in the background and `./stop_spark.sh` stops it. |
| `rewrite` | Write the chapters and the summary again from the notes it already has (for example, after you edit `prompts.py`). |
| `report` | Rebuild the report files from what has been read so far. |
| `paper ID` | Read one paper now and print its notes. The ID can be a DOI, an OpenAlex id or an arXiv link. The paper is stored in `data/single_papers.db`. |
| `import-pdfs [FOLDER]` | Attach PDFs exported from Zotero (default folder: `pdfs/`), read those papers again and rewrite only the chapters they belong to. Stop the run before you use it. |
| `zotero-list [--top 100]` | After the `fetch_entitled.py` output has been copied into `pdfs/`: match those files, then write `reports/zotero_import.ris` with only the most important papers that still have no full text. |
| `status` | Show progress per theme and an estimate of the time left. |
| `setup` | Ask for the Telegram bot and the API keys, and save them to `config.json`. |
| `check` | Test the model, OpenAlex, PDF reading and Telegram. |

Options for `run`, `status`, `report` and `rewrite`: `--test` (a small trial with separate files: `data/test.db`, `reports/test/`, `logs/test.log`), `--model NAME`, `--no-think`, `--quiet`.

Other scripts:

* `fetch_entitled.py wanted.csv`: run it on Saxion's network (on campus or on the VPN). It downloads entitled papers through the Wiley and Elsevier text mining APIs. Give the keys with `WILEY_TDM_TOKEN` and `ELSEVIER_API_KEY` in the environment, or with `--wiley-token` and `--elsevier-key`. Copy its output folder (`entitled/`) into `pdfs/`.
* `s2_collect.py`: slowly collects Semantic Scholar citing sentences before phase 2. It stops by itself when a run starts.
* `test_report.py`: checks a `--test` run against its pass rules and writes `reports/test/test_report.md`.
* `try_on_mac.command`: a small trial run on a Mac with a small model.

## Where the data lives

Everything is found relative to this folder, next to `researcher.py`:

| Path | What |
|---|---|
| `data/research.db` | The research database (SQLite): every paper, score, note and cache |
| `data/osap/` | The Open Source Asset Pricing files (download them from openassetpricing.com, Data) |
| `pdfs/` | Full texts: `entitled/` from `fetch_entitled.py`, plus the Zotero export |
| `reports/` | Everything it writes |
| `logs/` | Run logs and the process id |
| `config.json` | Your private keys |
| `FROZEN` | If this file exists, every command that would change the library refuses to run, except with `--test` |

None of these paths are in git. To run the pipeline on the existing library, copy `data/` and `pdfs/` from the Spark (`~/trading_researcher_run2`) into this folder. Do this on a copy only. The original library on the Spark is frozen and must not change. `research/v1` in this repository is the text result of that frozen library.

## Good to know

* A local model can get numbers wrong. Check a number in the paper before you rely on it.
* Papers behind a paywall that it could not fetch are read from their abstract. Every report says which papers were read in full.
* This is research about how traders and markets behave. It is not trading advice.

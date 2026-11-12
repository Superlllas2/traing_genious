#!/usr/bin/env python3
"""
Trading research reader: lets a local model read trading research for hours or days,
and writes one synthesis of what the research says your market insight app needs.

  python3 researcher.py setup      connect Telegram and an OpenAlex key (both optional)
  python3 researcher.py check      test the model, OpenAlex, PDF reading and Telegram
  python3 researcher.py run        start the research, or continue where it stopped
  python3 researcher.py run --phase 1   search, screen, choose and fetch; writes reports/wanted.csv and stops
  python3 researcher.py run --phase 2   read theme by theme (PDFs in pdfs/ first), a report after each theme
  python3 researcher.py status     show progress
  python3 researcher.py report     rebuild the report files from what was read so far
  python3 researcher.py rewrite    write the chapters and the summary again (after editing prompts.py)
  python3 researcher.py paper ID   read one paper now (DOI, OpenAlex id or arXiv link)
  python3 researcher.py zotero-list [--top 100]
                                   after copying fetch_entitled.py's folder into pdfs/: write zotero_import.ris
                                   with only the most important papers still missing
  python3 researcher.py import-pdfs [FOLDER]
                                   attach PDFs exported from Zotero (default folder: pdfs/), reread those
                                   papers and rewrite only the chapters they belong to

Options for run, status, report and rewrite:
  --test          a small trial run: one theme, a handful of papers, separate files
  --model NAME    use another model than the one in research.json
  --no-think      switch the model's thinking off (for small models)
  --quiet         no Telegram messages

What to research lives in research.json (themes, search queries, budgets, model).
How the model screens, reads and writes lives in prompts.py.
Standard library only; PDF reading needs one extra package: pip install pypdf
"""

import argparse
from pathlib import Path
import getpass
import signal
import subprocess
import sys
import time

from common import (DATA_DIR, LOGS_DIR, REPORTS_DIR, HTTPError, Unreachable, get_json, load_secrets,
                    load_settings, log, save_secrets, setup_logging)
from llm import ModelDown, ModelError, ask_json
from notify import Notifier, telegram
from pipeline import Pipeline, duration
from sources import OPENALEX, OpenAlex
from store import Store

MODEL_HELP = """
Check that:
* Ollama is running (on Linux: sudo systemctl start ollama; on a Mac: open the Ollama app)
* the model is downloaded: ollama pull {model}
* "model" and "base_url" in research.json are right"""


def yes(answer, default=False):
    answer = answer.strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes", "j", "ja", "д", "да")


def prepare(args):
    settings = load_settings()
    if getattr(args, "model", None):
        settings["llm"]["model"] = args.model
    if getattr(args, "no_think", False):
        settings["llm"].update(think_screen=False, think_read=False, think_write=False)
    if getattr(args, "phase", None):
        settings["phase"] = args.phase
    test = getattr(args, "test", False)
    if test:
        # every theme, 2 papers each, with the same model settings as the full run
        settings["themes"] = [dict(theme, queries=theme["queries"][:2]) for theme in settings["themes"]]
        settings["budgets"].update(results_per_query=25, classic_queries_per_theme=1, screen_per_theme=12,
                                   read_per_theme=2, snowball_seeds_per_theme=0, snowball_refs_max=0,
                                   snowball_citing_seeds=0, snowball_screen_per_theme=0,
                                   snowball_read_per_theme=0, progress_every_hours=0)
    paths = {
        "db": DATA_DIR / ("test.db" if test else "research.db"),
        "reports": REPORTS_DIR / "test" if test else REPORTS_DIR,
        "log": LOGS_DIR / ("test.log" if test else "research.log"),
    }
    return settings, load_secrets(), paths


def single_instance(path):
    """Refuse to start twice on the same database."""
    try:
        import fcntl
    except ImportError:  # Windows: no lock, just be careful
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("The researcher is already running. Stop it first (./stop_spark.sh), or check: logs/run.out")
    return handle


def wait_for_model(llm, minutes=10):
    """Load the model before starting. A big model can take a few minutes; after a reboot Ollama may start late."""
    deadline = time.time() + minutes * 60
    while True:
        try:
            ask_json(llm, "You check that a model works.", 'Reply with this JSON: {"ok": true}',
                     {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
                     llm.get("think_screen"), 600)
            return True
        except ModelError as error:
            log.info("The model answered with an error (%s). Starting anyway.", error)
            return True
        except ModelDown as error:
            if time.time() > deadline:
                log.info("The model is not answering: %s%s", error, MODEL_HELP.format(model=llm["model"]))
                return False
            log.info("Waiting for the model: %s", error)
            time.sleep(30)


def cmd_run(args):
    settings, secrets, paths = prepare(args)
    setup_logging(paths["log"])
    lock = single_instance(paths["db"].with_suffix(".lock"))
    llm = settings["llm"]
    store = None
    try:
        log.info("Model: %s at %s", llm["model"], llm["base_url"])
        log.info("Themes: %s", ", ".join(theme["name"] for theme in settings["themes"]))
        log.info("Loading the model (the first time can take a few minutes)...")
        if not wait_for_model(llm):
            return 1
        store = Store(paths["db"])
        openalex = OpenAlex(store, secrets.get("openalex_api_key", ""))
        notifier = Notifier(secrets, quiet=args.quiet or args.test)
        Pipeline(settings, store, openalex, notifier, paths["reports"]).run()
    except KeyboardInterrupt:
        log.info("Stopped. Run it again any time: it continues where it left off.")
    finally:
        if store:
            store.close()
        if lock:
            lock.close()
    return 0


def cmd_status(args):
    settings, secrets, paths = prepare(args)
    store = Store(paths["db"]) if paths["db"].exists() else None
    if not store or not store.get("started_at"):
        print("The research has not started yet. Start it with ./start_spark.sh (or: python3 researcher.py run)")
        if store:
            store.close()
        return 0
    pipeline = Pipeline(settings, store, None, Notifier({}, quiet=True), paths["reports"])
    status = pipeline.status()
    totals = status["totals"]
    print(f"{'Theme':38} {'searches':>9} {'found':>7} {'screened':>13} {'read':>9}  chapter")
    for row in status["themes"]:
        print(f"{row['name'][:38]:38} {row['queries']:>9} {row['found']:>7,} "
              f"{row['screened']:>6,}/{row['screen_target']:<6,} {row['read']:>4}/{row['read_target']:<4} "
              f"  {'yes' if row['chapter'] else ('after reading' if not row['snowball'] else 'soon')}")
    print(f"\nPapers in the database: {totals['papers']:,}. Read: {totals['read']:,} "
          f"({totals['full_text']:,} from the full text).")
    if status["final_done"]:
        print(f"Finished. Reports: {paths['reports']}")
    elif status["started_at"]:
        print(f"Running time so far: {duration(float(store.get('active_seconds') or 0))} (time while it was working). "
              f"Done in about {duration(status['eta'])} (an estimate from the measured pace).")
    store.close()
    return 0


def cmd_report(args):
    settings, secrets, paths = prepare(args)
    store = Store(paths["db"])
    Pipeline(settings, store, None, Notifier({}, quiet=True), paths["reports"]).write_reports()
    store.close()
    print(f"Reports written to {paths['reports']}")
    return 0


def cmd_rewrite(args):
    settings, secrets, paths = prepare(args)
    store = Store(paths["db"])
    store.run("UPDATE themes SET chapter = NULL, chapter_at = NULL")
    store.put("final_done", None)
    store.close()
    print("Chapters and summary will be written again. Starting the run...")
    return cmd_run(args)


def cmd_paper(args):
    settings, secrets, paths = prepare(args)
    setup_logging()
    store = Store(DATA_DIR / "single_papers.db")
    openalex = OpenAlex(store, secrets.get("openalex_api_key", ""))
    try:
        work = openalex.lookup(args.identifier)
    except (HTTPError, Unreachable) as error:
        print(f"Could not find that paper in OpenAlex ({error}). Try its DOI, for example 10.1111/0022-1082.00226")
        return 1
    print(f"{work['title']} ({work['authors']}, {work['year']}), cited by {work['cited_by']:,}")
    print("Reading it now. With a big model this takes a minute or two...\n")
    pipeline = Pipeline(settings, store, openalex, Notifier({}, quiet=True), REPORTS_DIR)
    try:
        notes, source = pipeline.read_single(work)
    except (ModelDown, ModelError) as error:
        print(f"The model did not answer: {error}{MODEL_HELP.format(model=settings['llm']['model'])}")
        return 1
    if not notes:
        print(f"No usable notes ({source}).")
        return 1
    print(f"Read from: {source}\n")
    for key in ("question", "data", "method"):
        print(f"{key.capitalize()}: {notes[key]}")
    print("Findings:")
    for finding in notes["findings"]:
        print(f"  * {finding}")
    print(f"Strength: {notes['strength']} ({notes['strength_reason']})")
    print(f"Limits: {notes['limits']}")
    print(f"For traders: {notes['for_traders']}")
    print(f"For the app: {notes['for_app']}")
    for card in notes.get("method_cards") or []:
        print("Method card:")
        for field, value in card.items():
            print(f"  {field}: {value}")
    store.close()
    return 0


def cmd_import_pdfs(args):
    from zotero import import_pdfs, reread
    settings, secrets, paths = prepare(args)
    folder = Path(args.folder) if args.folder else Path(__file__).resolve().parent / "pdfs"
    if not folder.exists():
        print(f"No folder {folder}. Copy the Zotero export (the .bib file and its files folder) there first.")
        return 1
    if subprocess.run(["pgrep", "-f", "researcher.py run"], capture_output=True).stdout.strip():
        print("The research is running. Stop it first (./stop_spark.sh), run import-pdfs, and it carries on from there.")
        return 1
    store = Store(paths["db"])
    attached = import_pdfs(folder, store)
    picked = {row["pid"] for row in store.picked_papers()}
    to_read = [pid for pid, _ in attached if pid in picked]
    reread(store, to_read)
    store.close()
    print(f"Matched {len(attached)} PDFs to papers; {len(to_read)} of them were read before and will be read again.")
    for path in getattr(import_pdfs, "unmatched", []):
        print(f"  not matched to any paper: {path}")
    if not to_read:
        return 0
    print("Rereading them now and rewriting the chapters they belong to...")
    args.phase = 2   # theme by theme, as phase 2 reads; only the themes of these papers change
    return cmd_run(args)


def cmd_zotero_list(args):
    """After copying fetch_entitled.py's folder into pdfs/: match those files, then write zotero_import.ris with
    only the most important papers still missing (top 100 by default), so the Zotero part stays short."""
    from zotero import centrality, import_pdfs, refused_by_login_publishers, write_ris
    settings, secrets, paths = prepare(args)
    folder = Path(__file__).resolve().parent / "pdfs"
    store = Store(paths["db"])
    attached = import_pdfs(folder, store) if folder.exists() else []
    rows = store.picked_with_cache()
    still = [row for row in rows if not row["local_pdf"] and not (row["text_source"] or "").startswith("full text")]
    out = paths["reports"]
    out.mkdir(parents=True, exist_ok=True)
    elsevier = refused_by_login_publishers(folder) if folder.exists() else set()
    count = write_ris(rows, settings.get("anchors"), out / "zotero_import.ris", centrality(store), limit=args.top,
                      always=elsevier)
    store.close()
    print(f"Matched {len(attached)} files in pdfs/ to papers. {len(still)} chosen papers still have no full text.")
    print(f"Wrote {out / 'zotero_import.ris'} with {count} papers: the {min(args.top, len(still))} most important "
          f"(anchors first), plus the Elsevier papers the fetch script was refused that ranked lower.")
    print("Import it into Zotero, run Find Available PDF, save the rest by hand, export as BibTeX with files,")
    print("copy that folder into pdfs/, then: ./start_spark.sh --phase 2")
    return 0


def cmd_check(args):
    settings, secrets, paths = prepare(args)
    llm = settings["llm"]
    problems = 0

    print(f"1. Model: asking {llm['model']} at {llm['base_url']}.")
    print("   The first answer can take a few minutes while a big model loads...")
    start = time.time()
    try:
        obj = ask_json(llm, "You check that a model works.",
                       'Reply with JSON: {"ok": true, "note": "<five words about yourself>"}',
                       {"type": "object", "properties": {"ok": {"type": "boolean"}, "note": {"type": "string"}},
                        "required": ["ok"]}, llm.get("think_screen"), 800)
        if obj:
            print(f"   OK after {time.time() - start:.0f} seconds: {obj.get('note', obj)}")
        else:
            problems += 1
            print("   It answered, but not with valid JSON. Try another model in research.json.")
    except (ModelDown, ModelError) as error:
        problems += 1
        print(f"   No answer: {error}{MODEL_HELP.format(model=llm['model'])}")

    print("\n2. OpenAlex (the paper catalog): one test search...")
    store = Store(paths["db"])
    try:
        works = OpenAlex(store, secrets.get("openalex_api_key", "")).search("disposition effect individual investors",
                                                                            per_page=3)
        if works:
            print(f"   OK. Top result: {works[0]['title']} ({works[0]['year']}), cited by {works[0]['cited_by']:,}")
        key = "with your free key (about 1,000 searches a day)" if secrets.get("openalex_api_key") else \
            "without a key (about 100 searches a day; a free key gives 1,000)"
        print(f"   Running {key}.")
    except Exception as error:
        problems += 1
        print(f"   Failed: {error}")
    finally:
        store.close()

    print("\n3. PDF reading:")
    try:
        import pypdf  # noqa: F401
        print("   OK, pypdf is installed.")
    except ImportError:
        print("   pypdf is not installed, so PDFs are skipped and papers are read from web pages and abstracts.")
        print("   To fix: pip install pypdf (install_spark.sh does this for you).")

    print("\n4. Telegram:")
    tg = secrets.get("telegram") or {}
    if tg.get("token") and tg.get("chat_id"):
        try:
            me = telegram(tg["token"], "getMe")
            print(f"   OK, messages go through @{me['username']}.")
        except Exception as error:
            problems += 1
            print(f"   The saved bot does not work ({error}). Run setup again.")
    else:
        print("   Not set up (optional). Run: python3 researcher.py setup")

    print("\nAll good." if not problems else f"\n{problems} problem(s) above.")
    return 0 if not problems else 1


def find_chat(token, username):
    print(f"   In Telegram, open a private chat with @{username} and send it any message, for example /start.")
    print("   Waiting up to 5 minutes...")
    try:
        old = telegram(token, "getUpdates", offset=-1, timeout=0)
    except Exception as error:
        if "conflict" in str(error).lower():
            print("   Another program is reading this bot's messages right now (your persona team?).")
            print("   Stop it for a minute and run setup again, or use a new bot.")
        else:
            print(f"   Telegram error: {error}")
        return ask_chat_id()
    offset = old[-1]["update_id"] + 1 if old else None
    deadline = time.time() + 300
    while time.time() < deadline:
        params = {"timeout": 25, "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = offset
        try:
            updates = telegram(token, "getUpdates", **params)
        except Exception as error:
            print(f"   Telegram error: {error}")
            time.sleep(3)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message") or {}
            sender = message.get("from") or {}
            if not sender or sender.get("is_bot"):
                continue
            name = sender.get("first_name", "someone")
            if yes(input(f"   Got a message from {name} (user ID {sender['id']}). Is that you? [Y/n] "), default=True):
                return message["chat"]["id"]
    print("   No message arrived.")
    return ask_chat_id()


def ask_chat_id():
    typed = input("   Type your chat ID instead, or press Enter to skip: ").strip()
    try:
        return int(typed) if typed else None
    except ValueError:
        return None


def cmd_setup(args):
    secrets = load_secrets()
    print("Setup. Both steps are optional: press Enter to skip one.\n")

    print("1. Telegram updates: progress every few hours, and the report when it's done.")
    print("   Make a bot in @BotFather (send /newbot) and paste its token here. It stays hidden while you paste.")
    saved = secrets.get("telegram") or {}
    hint = "Enter keeps the saved one" if saved.get("token") else "Enter to skip"
    token = getpass.getpass(f"   Bot token ({hint}): ").strip() or saved.get("token", "")
    if token:
        try:
            me = telegram(token, "getMe")
            print(f"   Connected to @{me['username']}.")
            chat_id = saved.get("chat_id") if token == saved.get("token") else None
            if not chat_id or yes(input("   Your chat is already saved. Find it again? [y/N] ")):
                chat_id = find_chat(token, me["username"])
            if chat_id:
                secrets["telegram"] = {"token": token, "chat_id": chat_id}
                save_secrets(secrets)
                telegram(token, "sendMessage", chat_id=chat_id,
                         text="Connected. Research updates will arrive here.")
                print("   Saved. You should see a message from the bot now.")
        except Exception as error:
            print(f"   That did not work ({error}). Run setup again to retry.")

    print("\n2. OpenAlex key (free, recommended). Without a key: about 100 searches a day; with one: 1,000.")
    print("   Get one in a minute: make an account at openalex.org, then copy the key from openalex.org/settings/api")
    key = getpass.getpass("   OpenAlex key (hidden; Enter to skip): ").strip()
    if key:
        try:
            get_json(f"{OPENALEX}/works?per_page=1&select=id&api_key={key}", timeout=30)
            secrets["openalex_api_key"] = key
            save_secrets(secrets)
            print("   Key works and is saved.")
        except Exception as error:
            print(f"   That key did not work ({error}). Run setup again to retry.")

    print("\nSetup done. Next: python3 researcher.py check")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Reads trading research with a local model.",
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    commands = parser.add_subparsers(dest="command")
    for name in ("run", "status", "report", "rewrite", "check"):
        command = commands.add_parser(name)
        if name == "run":
            command.add_argument("--phase", type=int, choices=(1, 2),
                                 help="1: search, screen, choose and fetch, then stop and write wanted.csv; "
                                      "2: read theme by theme, PDFs in pdfs/ first")
        command.add_argument("--test", action="store_true", help="small trial run with separate files")
        command.add_argument("--model", help="use another model than the one in research.json")
        command.add_argument("--no-think", action="store_true", help="switch the model's thinking off")
        command.add_argument("--quiet", action="store_true", help="no Telegram messages")
    paper = commands.add_parser("paper")
    paper.add_argument("identifier", help="DOI, OpenAlex id (W123...) or arXiv link")
    paper.add_argument("--model")
    paper.add_argument("--no-think", action="store_true")
    zotero_list = commands.add_parser("zotero-list")
    zotero_list.add_argument("--top", type=int, default=100, help="how many papers to list (default 100)")
    zotero_list.add_argument("--test", action="store_true")
    importer = commands.add_parser("import-pdfs")
    importer.add_argument("folder", nargs="?", help="folder with the Zotero export (default: pdfs/)")
    for flag in ("--test", "--no-think", "--quiet"):
        importer.add_argument(flag, action="store_true")
    importer.add_argument("--model")
    commands.add_parser("setup")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    frozen = Path(__file__).resolve().parent / "FROZEN"
    if frozen.exists() and args.command in ("run", "rewrite", "report", "paper", "import-pdfs", "zotero-list") \
            and not getattr(args, "test", False):
        print(f"The library is frozen ({frozen}): '{args.command}' would change it. "
              "Delete the FROZEN file first if you really mean to change it.")
        return 1
    handlers = {"zotero-list": cmd_zotero_list, "import-pdfs": cmd_import_pdfs, "run": cmd_run, "status": cmd_status, "report": cmd_report, "rewrite": cmd_rewrite,
                "check": cmd_check, "paper": cmd_paper, "setup": cmd_setup}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)

#!/usr/bin/env python3
"""Slowly collect Semantic Scholar citing sentences for the papers on the wanted list, before phase 2.

  ./s2_collect.py            (or: nohup .venv/bin/python -u s2_collect.py >> logs/s2_collect.out 2>&1 &)

* Works through the papers without a full text, most important first (the wanted.csv order).
* Without a key: one request a minute. On "too many requests" it waits 10 minutes and asks again for the same
  paper. With a key: one request every 1.1 seconds; on "too many requests" it waits 5, 20 and 60 seconds first. Other errors (server trouble, timeouts): wait 10 minutes, up to three times, then the paper is left for
  phase 2 to try.
* If semantic_scholar_api_key appears in config.json, it switches to the key (one request a second) by itself.
* Results go into the same cache phase 2 reads (s2_cache in data/research.db). A paper with no citing sentences
  is cached too, so phase 2 does not ask again; a paper that failed is not cached.
* Stops when phase 2 (any researcher.py run) starts, and sends a Telegram message with how many papers got sentences.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import HTTPError, Unreachable, load_secrets, load_settings, log, setup_logging  # noqa: E402
from notify import Notifier  # noqa: E402
from sources import SemanticScholar  # noqa: E402
from store import Store  # noqa: E402
from zotero import centrality, wanted  # noqa: E402

SLOW_GAP = 60      # seconds between requests without a key
KEY_GAP = 3.0      # with a key: the limit is 1 a second, but at that pace Semantic Scholar refuses often
BUSY_WAIT = 600    # after "too many requests" without a key (or after the short waits), or a server error
KEY_BACKOFF = (5, 20, 60)   # with a key: short waits after "too many requests" before the 10 minutes


class Stop(Exception):
    """Phase 2 started, or someone pressed Ctrl+C."""


def phase2_running():
    found = subprocess.run(["pgrep", "-f", "researcher.py run"], capture_output=True, text=True).stdout.split()
    return any(pid != str(os.getpid()) for pid in found)


class SlowGetter:
    """Stands in for the fetcher's _get: paced, patient, and stops when phase 2 starts."""

    def __init__(self, s2):
        self.s2 = s2
        self.last = 0.0
        self.key = ""
        self.stopping = False
        self.requests = 0

    def refresh_key(self):
        key = load_secrets().get("semantic_scholar_api_key", "")
        if key != self.key:
            self.key = key
            self.s2.headers = {"x-api-key": key} if key else {}
            log.info("Semantic Scholar key %s: %s", "found" if key else "removed",
                     "one request a second from now on" if key else "back to one request a minute")

    def nap(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            if self.stopping or phase2_running():
                raise Stop()
            time.sleep(min(15, max(0.0, end - time.time())))

    def _get(self, url, headers=None, timeout=60):
        from common import http_request
        failures, busy = 0, 0
        while True:
            self.refresh_key()
            self.nap((KEY_GAP if self.key else SLOW_GAP) - (time.time() - self.last))
            self.last = time.time()
            self.requests += 1
            try:
                return http_request(url, headers=self.s2.headers, timeout=timeout)
            except HTTPError as error:
                if error.code == 429:
                    # With a key, Semantic Scholar still answers "too many requests" now and then (about 1 in 6 at
                    # one request every 3 seconds): short waits first, the 10 minutes only after three of them.
                    busy += 1
                    pause = KEY_BACKOFF[busy - 1] if self.key and busy <= len(KEY_BACKOFF) else BUSY_WAIT
                    log.info("    too many requests: waiting %s, then the same paper again",
                             f"{pause} seconds" if pause < 60 else f"{pause // 60} minutes")
                    self.nap(pause)
                    continue
                if error.code >= 500 and failures < 3:
                    failures += 1
                    log.info("    server error (HTTP %s): waiting 10 minutes (%d of 3)", error.code, failures)
                    self.nap(BUSY_WAIT)
                    continue
                raise
            except Unreachable as error:
                if failures < 3:
                    failures += 1
                    log.info("    no answer (%s): waiting 10 minutes (%d of 3)", str(error)[:80], failures)
                    self.nap(BUSY_WAIT)
                    continue
                raise


def main():
    setup_logging(HERE / "logs" / "s2_collect.log")
    if phase2_running():
        log.info("Phase 2 is already running: nothing to do.")
        return 0
    settings = load_settings()
    store = Store(HERE / "data" / "research.db")
    s2 = SemanticScholar(None)
    getter = SlowGetter(s2)
    s2.fetcher = getter
    signal.signal(signal.SIGTERM, lambda *_: setattr(getter, "stopping", True))
    rows = wanted(store.picked_with_cache(), settings.get("anchors"), centrality(store))
    todo = [row for row in rows if not store.cached_contexts(row["pid"])]
    log.info("Semantic Scholar collector: %d papers on the wanted list, %d not asked yet.", len(rows), len(todo))
    got, empty, failed, reason = 0, 0, 0, "it went through the whole list"
    started = time.time()
    try:
        for number, row in enumerate(todo, 1):
            paper = {"doi": row["doi"], "title": row["title"], "authors": row["authors"], "year": row["year"]}
            try:
                text, used, citing = s2.contexts(paper)
            except (HTTPError, Unreachable, ValueError, KeyError) as error:
                failed += 1
                log.info("[%d/%d] P%s: failed (%s), left for phase 2", number, len(todo), row["pid"], str(error)[:100])
                continue
            store.cache_contexts(row["pid"], text, used, citing)
            got += used > 0
            empty += used == 0
            log.info("[%d/%d] P%s: %d sentences from %d citing papers  %s", number, len(todo), row["pid"], used, citing,
                     row["title"][:70])
    except (Stop, KeyboardInterrupt):
        reason = "phase 2 started" if phase2_running() else "it was stopped"
    total = store.one("SELECT COUNT(*) AS n FROM s2_cache WHERE used > 0")["n"]
    hours = (time.time() - started) / 3600
    message = (f"Semantic Scholar collector stopped because {reason}, after {hours:.1f} hours and {getter.requests} "
               f"requests. This round: {got} papers got citing sentences, {empty} have none, {failed} failed. "
               f"In the cache phase 2 reads: {total} of the {len(rows)} wanted papers have sentences.")
    log.info(message)
    Notifier(load_secrets()).send(message)
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

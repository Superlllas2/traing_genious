"""The research run, step by step:

1. collect   search OpenAlex with every query of every theme
2. screen    the model rates each paper's abstract for relevance (0 to 10)
3. read      the best papers are read in full where a free copy exists, and the model takes notes
4. snowball  follow the references and citations of the best papers to find the classics
             (then screening and reading continue with those)
5. chapters  one chapter per theme, written from the notes
6. summary   "what the app needs", plus a pack for Claude to do the final analysis

Every step saves its result in the database right away, so the run can stop and continue at any time.
"""

import csv
import json
import math
import re
import time
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta, timezone

import prompts
from common import REPORTS_DIR, HTTPError, Unreachable, log, tidy
from llm import ModelDown, ModelError, ask_json, ask_text
from osap import SignalData
from zotero import centrality, write_ris, write_wanted
from sources import BudgetExceeded, CoreQueue, SemanticScholar, TextFetcher, select_for_card, usable

DEFAULT_BUDGETS = {
    "results_per_query": 100,
    "classic_queries_per_theme": 4,
    "min_year": 1980,
    "screen_per_theme": 500,
    "min_relevance": 6,
    "read_per_theme": 50,
    "snowball_seeds_per_theme": 12,
    "snowball_refs_max": 300,
    "snowball_citing_seeds": 6,
    "snowball_screen_per_theme": 200,
    "snowball_read_per_theme": 20,
    "card_text_chars": 30000,   # paper text per read: abstract, introduction, conclusion and the parts with card details
    "chapter_batch_chars": 45000,
    "progress_every_hours": 2,
}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def log10p(number):
    return math.log10(1 + max(0, number or 0))


def duration(seconds):
    if seconds < 3600:
        return f"{max(1, round(seconds / 60))} min"
    return f"{seconds / 3600:.1f} hours"


def seconds_to_utc_midnight():
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (midnight - now).total_seconds()


def link(paper):
    doi = paper["doi"] or ""
    if doi:
        return doi if doi.startswith("http") else "https://doi.org/" + doi
    return paper["landing_url"] or paper["oa_url"] or f"https://openalex.org/{paper['openalex_id']}"


def normalize_notes(obj):
    """Keep the notes tidy and predictable, whatever shape the model returned."""
    def text(key, limit=700):
        value = obj.get(key)
        if isinstance(value, list):
            value = "; ".join(str(item) for item in value)
        return tidy(str(value or ""))[:limit]

    findings = obj.get("findings") or []
    if isinstance(findings, str):
        findings = [findings]
    findings = [tidy(str(item))[:500] for item in findings if str(item).strip()][:6]
    if not findings:
        return None
    strength = str(obj.get("strength") or "").strip().lower()
    cards = []
    for card in obj.get("method_cards") or []:
        if isinstance(card, dict) and str(card.get("method") or "").strip():
            cards.append({field: tidy(str(card.get(field) or "not reported"))[:300]
                          for field in prompts.METHOD_CARD_FIELDS})
    return {
        "question": text("question"),
        "data": text("data"),
        "method": text("method"),
        "findings": findings,
        "strength": strength if strength in ("strong", "moderate", "weak") else "unclear",
        "strength_reason": text("strength_reason", 300),
        "limits": text("limits"),
        "for_traders": text("for_traders"),
        "for_app": text("for_app"),
        "method_cards": cards[:8],
    }


def format_note(paper, with_link=False, cards=True):
    """A paper's note as text. Chapters use cards=False: their cards arrive grouped in the family table."""
    notes = json.loads(paper["notes"])
    head = (f"[P{paper['pid']}] {paper['title']} ({paper['authors'] or 'unknown authors'}, "
            f"{paper['year'] or 'no year'}, {paper['venue'] or 'unknown venue'}, cited by {paper['cited_by']:,}, "
            f"read from: {paper['text_source']})")
    lines = [head]
    if with_link:
        lines.append(f"Link: {link(paper)}")
    lines += [f"Question: {notes.get('question', '')}",
              f"Data: {notes.get('data', '')}",
              f"Method: {notes.get('method', '')}",
              "Findings:"]
    lines += [f"  * {finding}" for finding in notes.get("findings") or []]
    lines += [f"Strength: {notes.get('strength')} ({notes.get('strength_reason', '')})",
              f"Limits: {notes.get('limits', '')}",
              f"For traders: {notes.get('for_traders', '')}",
              f"For the app: {notes.get('for_app', '')}"]
    if notes.get("more_methods"):
        lines.append("Also tests (no cards written): " + "; ".join(notes["more_methods"]))
    for card in (notes.get("method_cards") or []) if cards else []:
        lines.append("Method card: " + " | ".join(f"{field}: {card.get(field, '')}"
                                                  for field in prompts.METHOD_CARD_FIELDS)
                     + (f" | source: {card['source_note']}" if card.get("source_note") else ""))
    return "\n".join(lines)


def dataset_note(paper, signals, cards):
    """A note built only from the Open Source Asset Pricing dataset, for a paper we could not read."""
    findings = [f"{card['method']}: {card['reported_return']}; {card['market_years']}; holding {card['holding_days']} "
                f"trading days; still works: {card['still_works']}" for card in cards]
    return {
        "question": f"What return does the signal \"{signals[0]['LongDescription']}\" earn? (from the dataset)",
        "data": cards[0]["market_years"] + ", " + cards[0]["stocks"],
        "method": "Long short portfolios sorted on the signal, rebuilt by the Open Source Asset Pricing project",
        "findings": findings,
        "strength": "moderate",
        "strength_reason": "Numbers come from a public replication dataset, not from reading the paper.",
        "limits": "The paper itself was not read: no full text and no usable abstract. Costs are not included.",
        "for_traders": "not reported (dataset only)",
        "for_app": "not reported (dataset only)",
        "method_cards": cards,
    }


HEDGES = {"only", "some", "may", "might", "can", "around", "about", "roughly", "in", "this", "sample", "often",
          "sometimes", "partly", "possibly", "a", "the", "of", "and", "or", "to", "is", "are", "be", "for", "with"}


def words(text):
    return re.findall(r"[a-z]+", (text or "").lower())


def numbers(text):
    return re.findall(r"\d+(?:\.\d+)?", text or "")


def only_narrower(old, new):
    """True when the new sentence adds no number, no paper id and no content word that the old one lacked."""
    if not new or len(new) > len(old) * 1.15 + 20:
        return False
    if not set(numbers(new)) <= set(numbers(old)):
        return False
    if not set(re.findall(r"P\d+", new)) <= set(re.findall(r"P\d+", old)):
        return False
    return set(words(new)) <= set(words(old)) | HEDGES


def find_sentence(text, claim):
    """The sentence (or bullet line) of the text that the checker quoted, exactly or by word overlap."""
    claim = claim.strip().strip('"')
    if claim and claim in text:
        return claim
    target = set(words(claim))
    if not target:
        return None
    best, best_score = None, 0.0
    for line in text.split("\n"):
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            overlap = len(target & set(words(sentence))) / len(target)
            if overlap > best_score:
                best, best_score = sentence.strip(), overlap
    return best if best_score >= 0.7 else None


def delete_sentence(text, sentence):
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if sentence in line:
            rest = line.replace(sentence, "").strip()
            if re.fullmatch(r"(\*|-|\d+\.)?\s*(\*\*[^*]*\*\*)?\s*", rest):  # nothing left but a bullet or a bold label
                del lines[index]
            else:
                lines[index] = re.sub(r"\s{2,}", " ", line.replace(sentence, "")).rstrip()
            break
    return "\n".join(lines)


def card_complete(card):
    """A card a trader can use: a trigger, and a holding period and a return with numbers."""
    def has_number(value):
        value = (value or "").lower()
        # "not reported: ... coefficient 0.23" has digits but no return
        return bool(re.search(r"\d", value)) and not re.search(r"not (stated|reported|recorded)", value)
    trigger = (card.get("trigger") or "").lower()
    return bool(trigger) and not trigger.startswith("not reported") and has_number(card.get("holding_days")) \
        and has_number(card.get("reported_return"))


CONCEDES = re.compile(r"(this|which|notes?) supports? (the|this) claim|this matches|matches the (summary|claim)|no flag",
                      re.IGNORECASE)


def real_problems(problems, summary):
    """The checker's flags without repeats, without flags whose own reasons say the notes back the claim (the model
    sometimes reasons its way to "supported" and lists the claim anyway), and without claims in the open questions."""
    open_part = summary.split("## What the research does not answer yet", 1)[1].split("\n## ", 1)[0] \
        if "## What the research does not answer yet" in summary else ""
    kept, seen = [], set()
    for problem in problems:
        claim = (problem.get("claim") or "").strip()
        if not claim or claim in seen or CONCEDES.search(problem.get("notes_say") or "") \
                or (open_part and find_sentence(open_part, claim)):
            continue
        seen.add(claim)
        kept.append(problem)
    return kept


def no_return_papers(papers):
    """Papers with stock cards none of which states a strategy return (only coefficients, t stats, or nothing)."""
    pids = []
    for paper in papers:
        cards = [card for card in json.loads(paper["notes"]).get("method_cards") or [] if is_stock_card(card)]
        value = lambda card: (card.get("reported_return") or "").lower()
        if cards and not any(re.search(r"\d", value(card)) and not re.search(r"not (stated|reported|recorded)", value(card))
                             for card in cards):
            pids.append(paper["pid"])
    return pids


def card_source(paper, card):
    if (card.get("source_note") or "").startswith("secondary"):
        return "secondary"
    if card.get("source_note"):
        return "dataset"
    return "full text" if paper["text_source"].startswith("full text") else "abstract"


def insert_table(chapter, table):
    """Put the table where the model wrote METHOD_TABLE, else before the first subheading, else at the end."""
    lines = chapter.split("\n")
    for index, line in enumerate(lines):
        if line.strip().strip("*`") == "METHOD_TABLE":
            lines[index] = table
            return "\n".join(lines)
    position = chapter.find("\n### ")
    if position < 0:
        return chapter + "\n\n" + table
    return chapter[:position] + "\n\n" + table + "\n" + chapter[position:]


CARD_COLUMNS = [("Method", "method"), ("Trigger", "trigger"), ("Direction", "direction"), ("Entry", "entry"),
                ("Hold (days)", "holding_days"), ("Reported return", "reported_return"),
                ("After costs", "after_costs"), ("Stocks", "stocks"), ("Market and years", "market_years"),
                ("Still works", "still_works"), ("Data needed", "data_needed"),
                ("Storyline fit", "storyline_fit"), ("Retail usable", "retail_usable")]


def is_stock_card(card):
    """Cards on other assets (currencies, bonds, commodities...) stay in the note but not in the ranked tables."""
    asset = (card.get("asset_class") or "stocks").lower()
    return any(word in asset for word in ("stock", "equit", "share", "not reported")) or not asset.strip()


def method_cards(papers, other_assets=False):
    """Every method card on stocks of these papers, best evidence first: strength, full text, after costs,
    still works, then citations. other_assets=True keeps cards on other assets too (for the CSV)."""
    rows = []
    for paper in papers:
        notes = json.loads(paper["notes"])
        for card in notes.get("method_cards") or []:
            if not other_assets and not is_stock_card(card):
                continue
            rank = ({"strong": 0, "moderate": 1, "weak": 2}.get(notes.get("strength"), 3),
                    {"full text": 0, "dataset": 0, "secondary": 1}.get(card_source(paper, card), 2),
                    not card.get("after_costs", "").lower().startswith("yes"),
                    not card.get("still_works", "").lower().startswith("yes"),
                    -(paper["cited_by"] or 0))
            rows.append((rank, paper, notes, card))
    rows.sort(key=lambda row: row[0])
    return [(paper, notes, card) for _, paper, notes, card in rows]


def family_table(families):
    """One row per method family: its best supported card, the papers and how many cards back it."""
    if not families:
        return "No paper in this theme tested a method on stocks that a trader could follow."
    cell = lambda value: str(value).replace("|", "/").replace("\n", " ")[:140]
    lines = ["| Family | Best supported method | Trigger | Hold (days) | Reported return | After costs | Still works "
             "| Evidence | Best source | Papers | Cards |", "|" + "---|" * 11]
    for family in families:
        paper, notes, card = family["best"]
        papers = ", ".join(f"P{pid}" for pid in family["pids"][:12]) + (" ..." if len(family["pids"]) > 12 else "")
        lines.append("| " + " | ".join(cell(value) for value in (
            family["family"], card.get("method", ""), card.get("trigger", ""), card.get("holding_days", ""),
            card.get("reported_return", ""), card.get("after_costs", ""), card.get("still_works", ""),
            notes.get("strength", ""), f"P{paper['pid']}, {card_source(paper, card)}", papers, family["cards"])) + " |")
    return "\n".join(lines)


def method_table(papers):
    """The theme's method cards as a Markdown table, best evidence first."""
    cards = method_cards(papers)
    if not cards:
        return "No paper in this theme tested a method a trader could follow."
    cell = lambda value: str(value).replace("|", "/").replace("\n", " ")[:160]
    lines = ["| " + " | ".join(name for name, _ in CARD_COLUMNS) + " | Evidence | Source |",
             "|" + "---|" * (len(CARD_COLUMNS) + 2)]
    for paper, notes, card in cards:
        source = f"P{paper['pid']}, {card_source(paper, card)}"
        lines.append("| " + " | ".join(cell(card.get(field, "")) for _, field in CARD_COLUMNS)
                     + f" | {notes.get('strength', '')} | {source} |")
    return "\n".join(lines)


def paper_line(paper):
    return (f"* [P{paper['pid']}] {paper['title']}. {paper['authors'] or 'Unknown authors'} "
            f"({paper['year'] or 'no year'}). {paper['venue'] or 'Unknown venue'}. "
            f"Cited by {paper['cited_by']:,}. Read from: {paper['text_source']}. {link(paper)}")


def pack_batches(blocks, max_chars):
    """Group note blocks so each group fits in one model call."""
    batches, current, count = [], [], 0
    size = 0
    for block in blocks:
        if current and size + len(block) > max_chars:
            batches.append(("\n\n".join(current), count))
            current, count, size = [], 0, 0
        current.append(block)
        count += 1
        size += len(block) + 2
    if current:
        batches.append(("\n\n".join(current), count))
    return batches


class Pipeline:
    def __init__(self, settings, store, openalex, notifier, reports_dir=REPORTS_DIR, fetcher=None, sleep=time.sleep):
        self.settings = settings
        self.store = store
        self.oa = openalex
        self.notify = notifier
        self.reports_dir = reports_dir
        self.fetcher = fetcher or TextFetcher()
        self.signals = SignalData()
        db_file = self.store.all("PRAGMA database_list")[0]["file"]
        self.core = CoreQueue(self.fetcher, db_file) if db_file and hasattr(self.fetcher, "core_key") else None
        if self.core is not None:
            self.fetcher.core_cache = self.core
        self.s2 = SemanticScholar(self.fetcher, getattr(self.fetcher, "s2_key", "")) \
            if hasattr(self.fetcher, "_get") else None
        self.core_wait_since = None
        self.phase = settings.get("phase")
        self.anchors = settings.get("anchors") or []
        self.sleep = sleep
        self.llm = settings["llm"]
        self.b = {**DEFAULT_BUDGETS, **settings.get("budgets", {})}
        self.themes = settings["themes"]
        self.about = settings["about"]
        self.language = settings.get("language", "English")
        self.produced_final = False
        self.store.ensure_themes([theme["name"] for theme in self.themes])

    # The main loop

    def run(self):
        fresh = not self.store.get("started_at")
        if fresh:
            self.store.put("started_at", time.time())
            every = float(self.b.get("progress_every_hours") or 0)
            updates = f"I'll send an update every {every:g} hours, and the report when it's done." if every > 0 \
                else "I'll send the report when it's done."
            self.notify.send(f"Research started: {len(self.themes)} themes. {updates}")
        # Time counts only while a run is working: the days between phase 1 and phase 2 do not count.
        self.session_start = self.last_tick = time.time()
        self.clock_from = self.session_start - self.active_seconds()
        announced = fresh
        down_since, down_told, failures = None, False, 0
        while True:
            try:
                self.tick()
                worked = self.step()
                if worked and not announced:
                    announced = True
                    self.notify.send("Research continues where it left off.")
                if down_told:
                    self.notify.send("Working again after the pause.")
                down_since, down_told, failures = None, False, 0
            except BudgetExceeded as error:
                wait = seconds_to_utc_midnight() + 300
                resume = datetime.now() + timedelta(seconds=wait)
                self.notify.send(f"OpenAlex's free daily allowance is used up ({error}). "
                                 f"Pausing until about {resume:%H:%M}, then continuing by itself.")
                self.sleep(wait)
                continue
            except (ModelDown, Unreachable) as error:
                what = "The model is not answering" if isinstance(error, ModelDown) else "No connection"
                if down_since is None:
                    down_since = time.time()
                    log.info("%s: %s. Trying again in 5 minutes.", what, error)
                elif time.time() - down_since > 900 and not down_told:
                    down_told = True
                    self.notify.send(f"Paused. {what}: {error}. I'll keep trying every 5 minutes.")
                self.sleep(300)
                continue
            except Exception as error:  # anything unexpected: wait and retry, give up after about an hour
                failures += 1
                log.exception("Unexpected problem (%d in a row): %s", failures, error)
                if failures >= 6:
                    self.notify.send(f"Stopped after repeated errors: {error}. Details are in logs/research.log. "
                                     "Nothing is lost: start it again once it's fixed.")
                    raise
                if failures == 1:
                    self.notify.send(f"Problem: {error}. Trying again in 10 minutes.")
                self.sleep(600)
                continue
            if not worked:
                break
            self.maybe_progress()
        self.finish()

    def step(self):
        """Do one small piece of work. Returns False when everything is done."""
        if self.phase == 1:   # search, screen, choose and fetch everything; no reading
            return (self.collect_step() or self.screen_step() or self.pick_step() or self.snowball_step()
                    or self.fetch_step() or self.core_wait_step() or self.phase1_finish())
        if self.phase == 2:   # read theme by theme, your PDFs first, a progress report after each theme
            return (self.import_step() or self.core_step() or self.theme_step() or self.final_step())
        return (self.collect_step() or self.screen_step() or self.core_step() or self.read_step()
                or self.snowball_step() or self.core_wait_step() or self.chapter_step() or self.final_step())

    # Phase 1

    def pick_step(self):
        """Choose the papers to read, up to each theme's budget, without reading them."""
        options = []
        for theme in self.themes:
            budget, picked = self.read_budget(theme["name"]), self.store.picked_count(theme["name"])
            if picked < budget:
                row = self.best_unpicked(theme["name"])
                if row is not None:
                    options.append((picked / max(budget, 1), theme, row))
        if not options:
            return False
        _, theme, row = min(options, key=lambda option: option[0])
        self.store.mark_picked(row["pid"], theme["name"])
        log.info("[%s] chose P%s for reading: %s", theme["name"], row["pid"], row["title"][:90])
        return True

    def fetch_step(self):
        """Look for the full text of the next chosen paper; for papers without one, collect citing sentences
        and ask CORE in the background. Everything is cached for phase 2."""
        row = self.store.next_picked_unfetched()
        if row is None:
            return False
        try:
            text, source = self.fetcher.fetch(row)
        except Exception as error:  # an odd website must never stop the research
            log.info("  full text failed for P%s: %s", row["pid"], error)
            text, source = "", "abstract only"
        if not source.startswith("full text"):
            source, text = "no full text", ""
            self.citing_sentences(row)
            if self.core is not None:
                self.core.submit(row)
        self.store.cache_text(row["pid"], source, text)
        log.info("[%s] P%s: %s", row["theme"], row["pid"], source)
        return True

    def phase1_finish(self):
        if self.store.get("phase1_done"):
            return False
        for pid in self.core.take_arrived() if self.core is not None else []:
            text = self.core.get(pid)
            if text:
                self.store.cache_text(pid, "full text (CORE)", text)
        rows = self.store.picked_with_cache()
        out = self.reports_dir
        out.mkdir(parents=True, exist_ok=True)
        info = centrality(self.store)
        wanted = write_wanted(rows, self.anchors, out / "wanted.csv", info)
        write_ris(rows, self.anchors, out / "zotero_import.ris", info, limit=self.b.get("zotero_top", 100))
        by_source = Counter(row["text_source"] for row in rows)
        lines = [f"* {source}: {count}" for source, count in by_source.most_common()]
        (out / "phase1_report.md").write_text(
            "# Phase 1 done\n\n" + f"{len(rows)} papers chosen for reading. {wanted} still need a full text: "
            "they are in wanted.csv and zotero_import.ris, anchors first.\n\n## What the machine sources found\n\n"
            + "\n".join(lines) + "\n\nNext: run fetch_entitled.py at Saxion on wanted.csv (the whole list) and copy its "
            "folder to pdfs/. Then python3 researcher.py zotero-list writes zotero_import.ris with the top 100 papers "
            "still missing. After Zotero, copy its export to pdfs/ too, then: python3 researcher.py run --phase 2\n", encoding="utf-8")
        self.store.put("phase1_done", 1)
        full = sum(count for source, count in by_source.items() if source.startswith("full text"))
        self.notify.send(f"Phase 1 done: {len(rows)} papers chosen, {full} with a full text from the machine sources, "
                         f"{wanted} on the wanted list (reports/wanted.csv). Fetch PDFs, put them in pdfs/, "
                         "then start phase 2.")
        return False

    # Phase 2

    def import_step(self):
        if self.store.get("phase2_imported"):
            return False
        from zotero import import_pdfs
        folder = Path(__file__).resolve().parent / "pdfs"
        attached = import_pdfs(folder, self.store) if folder.exists() else []
        self.store.put("phase2_imported", 1)
        log.info("Phase 2: %d PDFs from pdfs/ matched to papers", len(attached))
        return False

    def theme_step(self):
        """One theme at a time: read its papers, choose replacements for papers with no text, write its chapter,
        then send a progress report with the pass rules."""
        for theme in self.themes:
            name = theme["name"]
            row = self.store.one("""SELECT p.*, t.theme FROM paper_themes t JOIN papers p ON p.pid = t.pid
                                    WHERE t.theme = ? AND t.picked = 1 AND p.read_at IS NULL
                                    ORDER BY t.relevance DESC LIMIT 1""", name)
            if row is not None:
                self.read(theme, row)
                return True
            if self.store.picked_count(name) < self.read_budget(name):
                candidate = self.best_unpicked(name)
                if candidate is not None:
                    self.store.mark_picked(candidate["pid"], name)
                    return True
            if self.store.chapter(name) is None:
                self.write_chapter(theme)
                self.theme_report(theme)
                return True
        return False

    def theme_report(self, theme):
        name = theme["name"]
        rows = self.store.all("""SELECT p.* FROM paper_themes t JOIN papers p ON p.pid = t.pid
                                 WHERE t.theme = ? AND t.picked = 1""", name)
        total = len(rows)
        noted = [row for row in rows if row["notes"]]
        cards, full_or_dataset, sources = [], 0, Counter()
        for row in noted:
            notes = json.loads(row["notes"])
            own = notes.get("method_cards") or []
            cards += [card for card in own if is_stock_card(card)]
            dataset = any((card.get("source_note") or "").startswith("Open") for card in own)
            full_or_dataset += row["text_source"].startswith("full text") or dataset
            sources[row["text_source"]] += 1
        complete = sum(map(card_complete, cards))
        minutes = sum(row["read_seconds"] or 0 for row in noted) / max(len(noted), 1) / 60
        index = [t["name"] for t in self.themes].index(name) + 1
        rules = [("No paper skipped", total - len(noted) == 0, f"{total - len(noted)} of {total} without a note"),
                 ("70% read in full or matched to the dataset", full_or_dataset >= 0.7 * total,
                  f"{full_or_dataset} of {total} ({full_or_dataset / max(total, 1):.0%})"),
                 ("70% of cards with trigger, holding period and return", complete >= 0.7 * max(len(cards), 1),
                  f"{complete} of {len(cards)} ({complete / max(len(cards), 1):.0%})")]
        text = (f"# Progress: theme {index} of {len(self.themes)}, {name}\n\n| Rule | Result | Detail |\n|---|---|---|\n"
                + "\n".join(f"| {rule} | {'pass' if ok else 'FAIL'} | {detail} |" for rule, ok, detail in rules)
                + "\n\nRead from: " + ", ".join(f"{source} {count}" for source, count in sources.most_common())
                + f"\n\nModel reading: {minutes:.1f} minutes per paper. The summary check comes after the last theme.\n")
        (self.reports_dir / f"progress_{index:02d}_{slug(name)}.md").write_text(text, encoding="utf-8")
        self.notify.send(f"Theme {index} of {len(self.themes)} done: {name}. "
                         + "; ".join(f"{rule}: {'pass' if ok else 'FAIL'} ({detail})" for rule, ok, detail in rules)
                         + f". {minutes:.1f} min per paper.")

    def core_step(self):
        """Full texts that CORE found in the background: read those papers again, with the full text."""
        if self.core is None:
            return False
        from zotero import reread
        arrived = [pid for pid in self.core.take_arrived()
                   if not (self.store.one("SELECT text_source FROM papers WHERE pid = ?", pid)["text_source"] or "")
                   .startswith("full text")]
        if arrived:
            log.info("CORE found full texts for %s: reading them again", ", ".join(f"P{pid}" for pid in arrived))
            reread(self.store, arrived)
        return False  # reading goes on in the same pass

    def core_wait_step(self, limit_minutes=30):
        """Before the chapters, give CORE's last lookups up to half an hour to come back."""
        if self.core is None or not self.core.busy():
            self.core_wait_since = None
            return False
        self.core_wait_since = self.core_wait_since or time.time()
        if time.time() - self.core_wait_since > limit_minutes * 60:
            return False
        log.info("Waiting for CORE's last %d lookup(s) before writing the chapters...", len(self.core.pending))
        self.sleep(30)
        return True

    def theme_by_name(self, name):
        for theme in self.themes:
            if theme["name"] == name:
                return theme
        return {"name": name, "question": "", "queries": []}

    # 1. Collect

    def collect_step(self):
        for theme in self.themes:
            for index, query in enumerate(theme["queries"]):
                if not self.store.query_done(theme["name"], query, "relevance"):
                    self.run_query(theme, query, "relevance")
                    return True
                if index < self.b["classic_queries_per_theme"] and \
                        not self.store.query_done(theme["name"], query, "classic"):
                    self.run_query(theme, query, "classic")
                    return True
        if not self.store.get("told_collected"):
            self.store.put("told_collected", 1)
            self.notify.send(f"Search done: {self.store.totals()['papers']:,} papers found. Screening them now.")
        return False

    def run_query(self, theme, query, kind):
        sort = "cited_by_count:desc" if kind == "classic" else None
        try:
            works = self.oa.search(query, per_page=self.b["results_per_query"], sort=sort, min_year=self.b["min_year"])
        except HTTPError as error:
            if error.code != 400:
                raise
            log.info("[%s] OpenAlex refused the search \"%s\" (%s). Skipped.", theme["name"], query, error.detail[:150])
            self.store.mark_query(theme["name"], query, kind, -1)
            return
        added = 0
        for rank, work in enumerate(works):
            if not usable(work, self.b["min_year"]):
                continue
            pid = self.store.add_paper(work)
            score = 1.0 / (1 + rank / 15) if kind == "relevance" else 0.6 / (1 + rank / 30)
            score += 0.25 * min(log10p(work["cited_by"]), 4) / 4 + (0.1 if work["abstract"] else 0)
            added += self.store.link(pid, theme["name"], "search", score)
        self.store.mark_query(theme["name"], query, kind, len(works))
        log.info("[%s] search \"%s\" (%s): %d results, %d new", theme["name"], query, kind, len(works), added)

    # 2. Screen

    def screen_step(self):
        options = []
        for theme in self.themes:
            for origin, budget in (("search", self.b["screen_per_theme"]),
                                   ("snowball", self.b["snowball_screen_per_theme"])):
                done = self.store.screened_count(theme["name"], origin)
                if done >= budget:
                    continue
                row = self.store.next_unscreened(theme["name"], origin)
                if row is not None:
                    options.append((done / max(budget, 1), theme, row))
        if not options:
            return False
        _, theme, row = min(options, key=lambda option: option[0])
        self.screen(theme, row)
        return True

    def screen(self, theme, row):
        system = prompts.SCREEN_SYSTEM.format(about=self.about, theme=theme["name"], question=theme["question"])
        abstract = row["abstract"] or "No abstract available. Judge from the title only, and be conservative."
        user = prompts.SCREEN_USER.format(title=row["title"], year=row["year"] or "unknown",
                                          venue=row["venue"] or "unknown", cited_by=row["cited_by"],
                                          abstract=abstract[:6000])
        start = time.time()
        try:
            obj = ask_json(self.llm, system, user, prompts.SCREEN_SCHEMA, self.llm.get("think_screen"),
                           self.llm.get("screen_max_tokens", 1500))
        except ModelError as error:
            log.info("  screening failed for P%s: %s", row["pid"], error)
            obj = None
        seconds = time.time() - start
        if not obj:
            self.store.save_screen(row["pid"], theme["name"], -1, "error", "", seconds)
            return
        try:
            relevance = max(0, min(10, int(round(float(obj.get("relevance", 0))))))
        except (TypeError, ValueError):
            relevance = 0
        kind = str(obj.get("kind") or "other")[:20]
        one_line = tidy(str(obj.get("one_line") or ""))[:300]
        self.store.save_screen(row["pid"], theme["name"], relevance, kind, one_line, seconds)
        log.info("[%s] screened P%s: %d/10  %s", theme["name"], row["pid"], relevance, row["title"][:90])

    # 3. Read

    def read_budget(self, name):
        budget = self.b["read_per_theme"]
        if self.store.snowball_done(name):
            budget += self.b["snowball_read_per_theme"]
        return budget

    def best_unpicked(self, name):
        rows = self.store.unpicked_candidates(name, self.b["min_relevance"])
        if not rows:
            return None

        def priority(row):
            score = row["relevance"] + 0.6 * min(log10p(row["cited_by"]), 4)
            if row["pdf_url"] or row["oa_url"] or (row["repo_urls"] or "[]") != "[]":
                score += 0.4   # a free full text is likely
            if row["kind"] == "review":
                score += 0.5   # reviews summarize many studies at once
            return score

        return max(rows, key=priority)

    def read_step(self):
        row = self.store.next_picked_unread()
        if row is not None:  # finish what was started before a restart
            self.read(self.theme_by_name(row["theme"]), row)
            return True
        options = []
        for theme in self.themes:
            budget = self.read_budget(theme["name"])
            picked = self.store.picked_count(theme["name"])
            if picked >= budget:
                continue
            row = self.best_unpicked(theme["name"])
            if row is not None:
                options.append((picked / max(budget, 1), theme, row))
        if not options:
            return False
        _, theme, row = min(options, key=lambda option: option[0])
        self.store.mark_picked(row["pid"], theme["name"])
        if row["read_at"] is None:
            self.read(theme, row)
        else:
            log.info("[%s] P%s was already read for another theme", theme["name"], row["pid"])
        return True

    def fetch_text(self, row):
        """Your PDF first; then what phase 1 found (or CORE later found); otherwise ask the sources now."""
        cached = self.store.cached_text(row["pid"]) if not (row["local_pdf"] if "local_pdf" in row.keys() else None) else None
        if cached is not None:
            if (cached["source"] or "").startswith("full text") and cached["text"]:
                return cached["text"], cached["source"]
            late = self.core.get(row["pid"]) if self.core is not None else None
            if late:
                return late, "full text (CORE)"
            return (row["abstract"] or ""), "abstract only"
        try:
            text, source = self.fetcher.fetch(row)
        except Exception as error:  # an odd website must never stop the research
            log.info("  full text failed for P%s: %s", row["pid"], error)
            text, source = "", "abstract only"
        if not text:
            text, source = (row["abstract"] or ""), "abstract only"
        return text, source

    def citing_sentences(self, row):
        """Sentences from citing papers (Semantic Scholar), from the phase 1 cache or asked now."""
        cached = self.store.cached_contexts(row["pid"])
        if cached is not None:
            return cached["text"] or "", cached["used"] or 0
        if self.s2 is None:
            return "", 0
        try:
            snippets, used, citing = self.s2.contexts(row)
            log.info("    Semantic Scholar: %d sentences from %d citing papers", used, citing)
        except (HTTPError, Unreachable, ValueError, KeyError) as failure:
            log.info("    Semantic Scholar: nothing (%s)", str(failure)[:100])
            return "", 0
        self.store.cache_contexts(row["pid"], snippets, used, citing)
        return snippets, used

    def list_methods(self, row, text, think=False, max_tokens=4000):
        """Step 1 of reading: the names of every distinct strategy or signal the paper tests."""
        user = prompts.READ_USER.format(title=row["title"], authors=row["authors"] or "unknown",
                                        year=row["year"] or "unknown", venue=row["venue"] or "unknown",
                                        cited_by=row["cited_by"], source="", text=text)
        obj = ask_json(self.llm, prompts.LIST_SYSTEM.format(about=self.about), user, prompts.LIST_SCHEMA, think, max_tokens)
        names = [tidy(str(name))[:120] for name in ((obj or {}).get("methods") or []) if str(name).strip()]
        more = [tidy(str(name))[:120] for name in ((obj or {}).get("more") or []) if str(name).strip()]
        return names[:8], (names[8:] + more)[:20]

    def take_notes(self, theme, row, text, source, think=None, max_tokens=None, methods=None):
        system = prompts.READ_SYSTEM.format(about=self.about, theme=theme["name"], question=theme.get("question", ""),
                                            language=self.language)
        user = prompts.READ_USER.format(title=row["title"], authors=row["authors"] or "unknown",
                                        year=row["year"] or "unknown", venue=row["venue"] or "unknown",
                                        cited_by=row["cited_by"], source=source, text=text)
        if methods is not None:
            user += prompts.METHOD_LIST.format(methods="\n".join(f"{i}. {name}" for i, name in enumerate(methods, 1))
                                               if methods else "none")
        obj = ask_json(self.llm, system, user, prompts.READ_SCHEMA,
                       self.llm.get("think_read") if think is None else think,
                       max_tokens or self.llm.get("read_max_tokens", 5000))
        return normalize_notes(obj) if obj else None

    def read(self, theme, row):
        text, source = self.fetch_text(row)
        signals = self.signals.match(row)[:4]
        dataset_cards = [self.signals.card(signal) for signal in signals]
        full = source.startswith("full text")
        snippets, used_snippets = "", 0
        if not full:
            if self.core is not None:
                self.core.submit(row)  # CORE looks in the background; if it finds the text, the paper is reread
            snippets, used_snippets = self.citing_sentences(row)
        has_abstract = len(text.strip()) >= self.b.get("min_text_chars", 300)
        if not full and (has_abstract or snippets):
            parts = []
            if has_abstract:
                parts.append("Abstract:\n" + text.strip())
            if snippets:
                parts.append(f"What {used_snippets} sentences in citing papers say about this paper "
                             "(second hand, from other authors):\n" + snippets)
            text = "\n\n".join(parts)
            source = "abstract and citing papers" if has_abstract and snippets else (
                "abstract only" if has_abstract else "citing papers only")
        if not full and not has_abstract and not snippets:
            # no full text, no real abstract, and no citing paper describes it
            if dataset_cards:
                notes = dataset_note(row, signals, dataset_cards)
                self.store.save_notes(row["pid"], notes, "dataset only", 0, 0, None)
                log.info("[%s] P%s: no text, card from %s (%s)", theme["name"], row["pid"], "Open Source Asset Pricing",
                         ", ".join(signal["Acronym"] for signal in signals))
            else:
                self.store.save_notes(row["pid"], None, "no text", len(text), 0,
                                      "no text: waiting for a PDF (see zotero_import.ris)")
                log.info("[%s] P%s waits for a PDF: no full text, abstract %d characters",
                         theme["name"], row["pid"], len(text.strip()))
            return
        if full:
            text, used, total = select_for_card(text, self.b.get("card_text_chars", 100000))
            log.info("    read %d of %d parts of the paper (%s characters)", used, total, f"{len(text):,}")
        start, error, methods, more = time.time(), None, None, []
        try:
            methods, more = self.list_methods(row, text)   # step 1: names of every strategy or signal tested
            log.info("    methods tested: %s%s", "; ".join(methods) or "none",
                     f" (and {len(more)} more without cards)" if more else "")
            notes = self.take_notes(theme, row, text, source, methods=methods)   # step 2: one card per name
        except ModelError as failure:
            notes, error = None, str(failure)
        if notes is None and not full:
            try:  # no usable answer from an abstract or citing sentences: once more, same settings
                notes = self.take_notes(theme, row, text, source, methods=methods or [])
            except ModelError as failure:
                error = str(failure)
        missing = notes is not None and methods is not None and len(notes["method_cards"]) < len(methods)
        # Rereading with thinking only for full texts: an abstract or citing sentences do not hold the numbers,
        # and pressing for them risks invented ones. There "not reported" stays.
        if full and (notes is None or missing or any(not card_complete(card) for card in notes["method_cards"])):
            # once more, thinking on and a larger budget
            log.info("    %s: reading again with thinking on", "no usable answer" if notes is None else
                     f"{len(notes['method_cards'])} cards for {len(methods)} methods" if missing else "a card lacks numbers")
            try:
                second = self.take_notes(theme, row, text, source, think=True, methods=methods,
                                         max_tokens=self.llm.get("reread_max_tokens", 32000))
            except ModelError as failure:
                second, error = None, str(failure)
            if second and (notes is None or (len(second["method_cards"]), sum(map(card_complete, second["method_cards"])))
                           >= (len(notes["method_cards"]), sum(map(card_complete, notes["method_cards"])))):
                notes = second
        seconds = time.time() - start
        if notes and more:
            notes["more_methods"] = more
        if notes and snippets:
            for card in notes["method_cards"]:
                card["source_note"] = (f"secondary: from the abstract and {used_snippets} sentences in citing papers "
                                       f"(Semantic Scholar), not the paper itself; replaced when its full text arrives"
                                       if has_abstract else
                                       f"secondary: from {used_snippets} sentences in citing papers (Semantic Scholar), "
                                       "not the paper itself; replaced when its full text arrives")
        if notes and dataset_cards:
            notes["method_cards"] = dataset_cards + notes["method_cards"]
            log.info("    added %d card(s) from Open Source Asset Pricing", len(dataset_cards))
        self.store.save_notes(row["pid"], notes, source, len(text), seconds,
                              None if notes else (error or "no usable answer"))
        status = "read" if notes else "could not read"
        log.info("[%s] %s P%s (%s, %.0f s): %s", theme["name"], status, row["pid"], source, seconds, row["title"][:90])

    # 4. Snowball

    def snowball_step(self):
        for theme in self.themes:
            if not self.store.snowball_done(theme["name"]):
                self.snowball(theme)
                return True
        return False

    def snowball(self, theme):
        name = theme["name"]
        seeds = self.store.top_read(name, self.b["snowball_seeds_per_theme"], picked_only=self.phase == 1)
        known = self.store.theme_openalex_ids(name)
        counts = Counter()
        for seed in seeds:
            for ref in json.loads(seed["refs"] or "[]"):
                if ref not in known:
                    counts[ref] += 1
        added = 0
        ref_ids = [ref for ref, _ in counts.most_common(self.b["snowball_refs_max"])]
        if ref_ids:
            for work in self.oa.by_ids(ref_ids):
                if not usable(work, self.b["min_year"]):
                    continue
                pid = self.store.add_paper(work)
                # papers that several of the best papers cite are usually the classics
                score = 0.8 + 0.4 * counts.get(work["openalex_id"], 1) + 0.25 * min(log10p(work["cited_by"]), 4) / 4
                added += self.store.link(pid, name, "snowball", score)
        for seed in seeds[:self.b["snowball_citing_seeds"]]:
            for work in self.oa.citing(seed["openalex_id"]):
                if work["openalex_id"] in known or not usable(work, self.b["min_year"]):
                    continue
                pid = self.store.add_paper(work)
                added += self.store.link(pid, name, "snowball", 0.5 + 0.25 * min(log10p(work["cited_by"]), 4) / 4)
        self.store.set_snowball_done(name)
        log.info("[%s] followed references and citations of %d papers: %d new candidates", name, len(seeds), added)

    # 5. Chapters

    def chapter_step(self):
        for theme in self.themes:
            if self.store.chapter(theme["name"]) is None:
                self.write_chapter(theme)
                return True
        return False

    def write_chapter(self, theme, keep_families=False):
        name = theme["name"]
        papers = self.store.read_papers(name)
        if not papers:
            self.store.save_chapter(name, f"## {name}\n\nNo papers were read for this theme.")
            return
        log.info("[%s] writing the chapter from %d papers...", name, len(papers))
        system = prompts.CHAPTER_SYSTEM.format(about=self.about, theme=name, question=theme.get("question", ""),
                                               count=len(papers), language=self.language)
        think, max_tokens = self.llm.get("think_write"), self.llm.get("write_max_tokens", 8000)
        # The notes go in without their cards; the cards arrive grouped into method families, one row per family.
        batches = pack_batches([format_note(paper, cards=False) for paper in papers], self.b["chapter_batch_chars"])
        families = self.method_families(name, papers, keep_families)
        table = family_table(families)
        order = prompts.CHAPTER_TABLE_ORDER.format(order=table)
        no_return = no_return_papers(papers)
        if no_return:
            order += prompts.NO_RETURN_LIST.format(pids=", ".join(f"P{pid}" for pid in no_return))
        try:
            if len(batches) == 1:
                chapter = self.write(system, prompts.CHAPTER_USER.format(count=len(papers), notes=batches[0][0]) + order,
                                     max_tokens)
            else:
                part_system = prompts.PARTIAL_SYSTEM.format(theme=name, question=theme.get("question", ""),
                                                            language=self.language)
                partials = []
                for number, (notes, count) in enumerate(batches, 1):
                    summary = self.write(part_system, prompts.CHAPTER_USER.format(count=count, notes=notes) + order,
                                         self.llm.get("partial_max_tokens", 16000))
                    partials.append(f"Group {number}:\n{summary}")
                chapter = self.write(system,
                                     prompts.CHAPTER_FROM_PARTS_USER.format(parts=len(batches), count=len(papers),
                                                                            partials="\n\n".join(partials)) + order,
                                     max_tokens)
        except ModelError as error:
            chapter = (f"## {name}\n\nThe model could not write this chapter ({error}). "
                       f"Run: python3 researcher.py rewrite")
        chapter = tidy(chapter) or f"## {name}\n\nThe model returned an empty chapter. Run: python3 researcher.py rewrite"
        chapter = insert_table(chapter, "### Method families, best evidence first\n\n" + table
                               + "\n\nEvery card, one per row, is in method_cards.csv.")
        self.store.save_chapter(name, chapter)
        self.write_reports()
        self.notify.send(f"Chapter ready: {name} ({len(papers)} papers).")

    def method_families(self, theme_name, papers, keep_families=False):
        """Group the theme's stock cards into families (the model names them), best evidence first. Each family
        keeps its best card (the first in evidence order), its papers and how many cards back it.
        keep_families: cards that already carry a family keep it; only the others are assigned, to an existing
        family where one fits (for rewriting one chapter without relabelling other papers' cards)."""
        cards = method_cards(papers)
        if not cards:
            return []
        def kept(paper, card):
            """The family this card already has in this theme: its label for this theme, or, for a paper read for
            this theme only, its one label. None for a card that needs a family here."""
            if not keep_families:
                return None
            label = (card.get("families") or {}).get(theme_name)
            if label:
                return label
            themes = self.store.one("SELECT COUNT(*) AS n FROM paper_themes WHERE pid = ? AND picked = 1", paper["pid"])["n"]
            return card.get("family") if themes == 1 else None
        labels = {i: kept(paper, card) for i, (paper, _, card) in enumerate(cards, 1)}
        existing = sorted({label for label in labels.values() if label})
        todo = [i for i in labels if not labels[i]]
        lines = [f"C{i}: {cards[i - 1][2].get('method', '')[:90]} | {cards[i - 1][2].get('trigger', '')[:90]} | "
                 f"{cards[i - 1][2].get('direction', '')[:30]}" for i in todo]
        obj = None
        if todo:
            system = (prompts.FAMILY_ASSIGN_SYSTEM.format(theme=theme_name, families="\n".join(f"* {name}" for name in existing))
                      if existing else prompts.FAMILY_SYSTEM.format(theme=theme_name))
            try:
                obj = ask_json(self.llm, system, prompts.FAMILY_USER.format(cards="\n".join(lines)), prompts.FAMILY_SCHEMA,
                               False, 16000)
            except ModelError as error:
                log.info("    grouping into families failed (%s): one family per card", error)
        assigned = {i: label for i, label in labels.items() if label}
        if keep_families:
            log.info("    %d cards keep their family; %d new cards assigned", len(assigned), len(todo))
        for family in (obj or {}).get("families") or []:
            for card_id in family.get("cards") or []:
                match = re.fullmatch(r"C(\d+)", str(card_id).strip())
                if match and 1 <= int(match.group(1)) <= len(cards) and int(match.group(1)) not in assigned:
                    assigned[int(match.group(1))] = tidy(str(family.get("family") or ""))[:80] or "other"
        groups = {}
        for index, (paper, notes, card) in enumerate(cards, 1):
            name = assigned.get(index) or card.get("method", "other")[:80]
            groups.setdefault(name, []).append((paper, notes, card))
        result = [{"family": name, "best": members[0], "cards": len(members),
                   "pids": sorted({paper["pid"] for paper, _, _ in members})} for name, members in groups.items()]
        self.save_families(papers, groups, theme_name, keep_families)
        order = {id(card): index for index, (_, _, card) in enumerate(cards)}
        result.sort(key=lambda family: order[id(family["best"][2])])
        log.info("    %d stock cards in %d method families", len(cards), len(result))
        return result

    def save_families(self, papers, groups, theme_name, keep_families=False):
        """Write each card's family into its paper's note: per theme (families[theme]) and as its one label
        (family, which method_cards.csv shows). Cards on other assets get "other assets (...)".
        keep_families: a card that already has a label keeps it; only cards without one get it, and only notes
        that change are written."""
        family_of = {}
        for name, members in groups.items():
            for paper, _, card in members:
                family_of[(paper["pid"], card.get("method"), card.get("trigger"))] = name
        for paper in papers:
            notes = json.loads(paper["notes"])
            if keep_families and all(card.get("family") for card in notes.get("method_cards") or []):
                continue  # a paper whose cards all have a label is left exactly as it is
            before = json.dumps(notes, ensure_ascii=False, sort_keys=True)
            for card in notes.get("method_cards") or []:
                name = family_of.get((paper["pid"], card.get("method"), card.get("trigger"))) or (
                    f"other assets ({card.get('asset_class') or 'not reported'})" if not is_stock_card(card) else "")
                card.setdefault("families", {})[theme_name] = name
                if not keep_families or not card.get("family"):
                    card["family"] = name
            if json.dumps(notes, ensure_ascii=False, sort_keys=True) != before:
                self.store.run("UPDATE papers SET notes = ? WHERE pid = ?", json.dumps(notes, ensure_ascii=False), paper["pid"])

    def write(self, system, user, max_tokens):
        """Writing with thinking on. If thinking uses up the budget and no text comes, ask once more without it."""
        text = ask_text(self.llm, system, user, self.llm.get("think_write"), max_tokens)
        if not text.strip() and self.llm.get("think_write"):
            log.info("    empty answer with thinking on: writing again with thinking off")
            text = ask_text(self.llm, system, user, False, max_tokens)
        return text

    # 6. Summary

    def final_step(self):
        if self.store.get("final_done"):
            return False
        log.info("Writing the summary: what the research says the app needs...")
        chapters = "\n\n".join(self.store.chapter(theme["name"]) or "" for theme in self.themes)
        system = prompts.FINAL_SYSTEM.format(about=self.about, language=self.language)
        try:
            summary = self.write(system, prompts.FINAL_USER.format(chapters=chapters), self.llm.get("final_max_tokens", 32000))
        except ModelError as error:
            summary = f"The model could not write the summary ({error}). Run: python3 researcher.py rewrite"
        summary = tidy(summary) or "The model returned an empty summary."
        self.store.put("summary_draft", summary)  # before the check, to compare what the check changed
        summary, report = self.check_summary(summary)
        self.store.put("final_summary", summary)
        self.store.put("summary_check", report)
        self.store.put("final_done", 1)
        self.store.put("finished_at", time.time())
        self.write_reports()
        self.produced_final = True
        return True

    def check_summary(self, summary, rounds=2):
        """The checker only flags. A flagged sentence may only be narrowed (words deleted, a hedge added; never a new
        number or claim, which the code verifies) or deleted. At most two rounds; what is left is listed at the end
        of the summary for review. Returns (summary, a Markdown report)."""
        report = ["# Summary check", "", "Each cited claim was compared with the notes of the papers it cites.", ""]
        problems = []
        for round_number in range(1, rounds + 1):
            pids = sorted({int(pid) for pid in re.findall(r"P(\d+)", summary)})
            papers = [self.store.one("SELECT * FROM papers WHERE pid = ? AND notes IS NOT NULL", pid) for pid in pids]
            notes = "\n\n".join(format_note(paper) for paper in papers if paper)
            if not notes:
                report.append("The summary cites no papers with notes: nothing to check.")
                return summary, "\n".join(report)
            log.info("Checking the summary against the notes of %d papers (round %d)...", len(pids), round_number)
            try:
                result = ask_json(self.llm, prompts.CHECK_SYSTEM, prompts.CHECK_USER.format(summary=summary, notes=notes),
                                  prompts.CHECK_SCHEMA, False, self.llm.get("read_max_tokens", 16000))
            except ModelError as error:
                report.append(f"Round {round_number}: the check could not run ({error}).")
                break
            raw = (result or {}).get("problems") or []
            problems = real_problems(raw, summary)
            report.append(f"## Round {round_number}: {len(problems)} flag(s)"
                          + (f" ({len(raw) - len(problems)} more dropped: repeats, flags whose own reasons say the notes "
                             "back the claim, or claims in the open questions)" if len(raw) > len(problems) else ""))
            report += [f"* **{problem.get('verdict')}** {', '.join(problem.get('papers') or [])}: "
                       f"\"{problem.get('claim')}\". Notes say: {problem.get('notes_say')}" for problem in problems]
            report.append("")
            if not problems or round_number == rounds:
                break
            for problem in problems:
                summary, action = self.narrow(summary, problem)
                report.append(f"* {action}")
            report.append("")
        if problems:
            summary += "\n\n## Flags for review\n\nThe automatic check could not settle these; check them against the notes.\n\n" + \
                "\n".join(f"* {problem.get('verdict')} ({', '.join(problem.get('papers') or [])}): "
                          f"\"{problem.get('claim')}\" Notes say: {problem.get('notes_say')}" for problem in problems)
        return summary, "\n".join(report)

    def narrow(self, summary, problem):
        """Narrow or delete one flagged sentence. Returns (summary, what was done)."""
        sentence = find_sentence(summary, problem.get("claim") or "")
        if not sentence:
            return summary, f"not found in the summary, left for review: \"{(problem.get('claim') or '')[:80]}\""
        try:
            narrowed = ask_text(self.llm, prompts.NARROW_SYSTEM, prompts.NARROW_USER.format(
                sentence=sentence, verdict=problem.get("verdict"), notes_say=problem.get("notes_say")), False, 2000)
        except ModelError:
            narrowed = "DELETE"
        narrowed = tidy(narrowed.strip().strip('"'))
        if narrowed.upper() != "DELETE" and only_narrower(sentence, narrowed):
            return summary.replace(sentence, narrowed, 1), f"narrowed: \"{sentence[:80]}\" to \"{narrowed[:80]}\""
        return delete_sentence(summary, sentence), f"deleted: \"{sentence[:80]}\""

    def active_seconds(self):
        """Seconds the research has actually been running, over all runs."""
        return float(self.store.get("active_seconds") or 0)

    def tick(self):
        """Add the time since the last tick to the running total (saved, so a stop loses at most a minute)."""
        now = time.time()
        if now - self.last_tick >= 60:
            self.store.put("active_seconds", self.active_seconds() + (now - self.last_tick))
            self.last_tick = now

    def finish(self):
        if hasattr(self, "last_tick"):
            self.store.put("active_seconds", self.active_seconds() + (time.time() - self.last_tick))
            self.last_tick = time.time()
        self.write_reports()
        if not self.produced_final:
            log.info("Nothing left to do. The reports are in %s", self.reports_dir)
            return
        totals = self.store.totals()
        took = self.active_seconds()
        self.notify.send(f"Research done after {duration(took)}. Screened {totals['screened']:,} papers and read "
                         f"{totals['read']:,} ({totals['full_text']:,} from the full text).\n\n"
                         f"Attached: the summary, and the pack to give Claude for the final analysis.")
        self.notify.send_file(self.reports_dir / "summary.md", "What the research says the app needs (local model draft)")
        self.notify.send_file(self.reports_dir / "claude_pack.md", "Give this file to Claude for the final analysis")
        log.info("Done. The reports are in %s", self.reports_dir)

    # Progress

    def status(self):
        rows, screen_left, read_left = [], 0, 0
        for theme in self.themes:
            name = theme["name"]
            n_queries = len(theme["queries"]) + min(self.b["classic_queries_per_theme"], len(theme["queries"]))
            done_queries = self.store.one("SELECT COUNT(*) AS n FROM queries WHERE theme = ? AND done_at IS NOT NULL",
                                          name)["n"]
            snowballed = self.store.snowball_done(name)
            found = self.store.candidate_count(name, "search")
            found_snowball = self.store.candidate_count(name, "snowball")
            collected = done_queries >= n_queries
            screen_target = min(self.b["screen_per_theme"], found) if collected else self.b["screen_per_theme"]
            screen_target += (min(self.b["snowball_screen_per_theme"], found_snowball) if snowballed
                              else self.b["snowball_screen_per_theme"])
            screened = self.store.screened_count(name)
            picked = self.store.picked_count(name)
            read_target = self.b["read_per_theme"] + self.b["snowball_read_per_theme"]
            if snowballed and screened >= screen_target and self.best_unpicked(name) is None:
                read_target = picked  # nothing relevant left to read for this theme
            rows.append({"name": name, "queries": f"{done_queries}/{n_queries}", "found": found + found_snowball,
                         "screened": screened, "screen_target": screen_target, "read": picked,
                         "read_target": read_target, "snowball": snowballed,
                         "chapter": self.store.chapter(name) is not None})
            screen_left += max(0, screen_target - screened)
            unread = self.store.one("""SELECT COUNT(*) AS n FROM paper_themes t JOIN papers p ON p.pid = t.pid
                                       WHERE t.theme = ? AND t.picked = 1 AND p.read_at IS NULL""", name)["n"]
            read_left += unread + max(0, read_target - picked)
        final_done = bool(self.store.get("final_done"))
        avg_screen = self.store.average("screen_seconds", "paper_themes") or 7
        chapters_left = sum(not row["chapter"] for row in rows)
        fetch_left = 0
        if self.phase == 1:  # phase 1 reads nothing: it chooses and fetches
            fetch_left, read_left = self.store.one("""SELECT COUNT(DISTINCT t.pid) AS n FROM paper_themes t
                WHERE t.picked = 1 AND t.pid NOT IN (SELECT pid FROM text_cache)""")["n"], 0
            chapters_left = 0
        eta = 0 if final_done else (screen_left * avg_screen + read_left * self.seconds_per_read()
                                    + fetch_left * self.seconds_per_fetch()
                                    + (chapters_left * 900 + 900 if self.phase != 1 else 300))
        return {"themes": rows, "totals": self.store.totals(), "eta": eta, "final_done": final_done,
                "screen_target": sum(r["screen_target"] for r in rows),
                "read_target": sum(r["read_target"] for r in rows),
                "started_at": float(self.store.get("started_at") or 0),
                "active_seconds": self.active_seconds()}

    def seconds_per_read(self):
        """Average time from one finished paper to the next, fetching and rereads included, over the last 100
        reads. Pauses over an hour (stops) are left out. The mean, not the median: most papers take under a minute,
        but rereads with thinking take up to half an hour, and they decide the total. 5 minutes until measured."""
        times = [row["read_at"] for row in self.store.all(
            "SELECT read_at FROM papers WHERE read_at IS NOT NULL ORDER BY read_at DESC LIMIT 101")]
        gaps = [a - b for a, b in zip(times, times[1:]) if 0 < a - b < 3600]
        return sum(gaps) / len(gaps) if len(gaps) >= 5 else 300

    def seconds_per_fetch(self):
        times = [row["fetched_at"] for row in self.store.all(
            "SELECT fetched_at FROM text_cache ORDER BY fetched_at DESC LIMIT 101")]
        gaps = [a - b for a, b in zip(times, times[1:]) if 0 < a - b < 3600]
        return sum(gaps) / len(gaps) if len(gaps) >= 5 else 60

    def progress_text(self):
        status = self.status()
        totals = status["totals"]
        best = self.store.one("""SELECT p.pid, p.title FROM paper_themes t JOIN papers p ON p.pid = t.pid
                                 WHERE p.notes IS NOT NULL ORDER BY t.relevance DESC, p.cited_by DESC LIMIT 1""")
        running = self.active_seconds() + (time.time() - getattr(self, "last_tick", time.time()))
        lines = [f"Research update, {duration(running)} of running time",
                 f"Found: {totals['papers']:,} papers",
                 f"Screened: {totals['screened']:,} of about {status['screen_target']:,}",
                 f"Read: {totals['read']:,} of about {status['read_target']:,} "
                 f"({totals['full_text']:,} from the full text)"]
        if best:
            lines.append(f"Strongest so far: {best['title']} [P{best['pid']}]")
        lines.append(f"Done in about {duration(status['eta'])}")
        return "\n".join(lines)

    def maybe_progress(self):
        every = float(self.b.get("progress_every_hours") or 0)
        if every <= 0:
            return
        last = float(self.store.get("last_progress_at") or self.store.get("started_at") or time.time())
        if time.time() - last < every * 3600:
            return
        self.store.put("last_progress_at", time.time())
        review = self.review_since(last)
        self.notify.send(self.progress_text() + (f"\n\nWhat the latest papers say:\n{review}" if review else ""))

    def review_since(self, since):
        """A few short thesis lines on what was learned since the last update, from notes or screening."""
        read = self.store.all("""SELECT p.*, MAX(t.relevance) AS relevance, GROUP_CONCAT(t.theme, '; ') AS themes
                                 FROM papers p JOIN paper_themes t ON t.pid = p.pid
                                 WHERE p.read_at > ? AND p.notes IS NOT NULL AND t.picked = 1
                                 GROUP BY p.pid ORDER BY relevance DESC LIMIT 20""", since)
        if read:
            material = "\n\n".join(format_note(paper) + f"\nTheme: {paper['themes']}" for paper in read)
            kind = f"notes on {len(read)} papers read in full or from their abstract"
        else:
            rows = self.store.all("""SELECT p.pid, p.title, t.theme, t.relevance, t.one_line FROM paper_themes t
                                     JOIN papers p ON p.pid = t.pid
                                     WHERE t.screened_at > ? AND t.relevance >= ?
                                     ORDER BY t.relevance DESC LIMIT 25""", since, self.b["min_relevance"])
            if not rows:
                return ""
            material = "\n".join(f"[P{r['pid']}] ({r['theme']}, relevance {r['relevance']:g}) {r['title']}: "
                                  f"{r['one_line']}" for r in rows)
            kind = f"one line summaries of the {len(rows)} most relevant papers screened so far (not read yet)"
        try:
            text = ask_text(self.llm, prompts.UPDATE_SYSTEM.format(about=self.about, language=self.language),
                            prompts.UPDATE_USER.format(kind=kind, material=material),
                            self.llm.get("think_screen"), 3000)
        except (ModelError, ModelDown) as error:
            log.info("  no review in this update (%s)", error)
            return ""
        return tidy(text)[:2500]

    # Reports

    def write_reports(self):
        out = self.reports_dir
        out.mkdir(parents=True, exist_ok=True)
        chapter_files = []
        for index, theme in enumerate(self.themes, 1):
            name = theme["name"]
            chapter = self.store.chapter(name)
            papers = self.store.read_papers(name)
            if chapter is None and not papers:
                continue
            body = chapter or f"## {name}\n\nNot written yet: {len(papers)} papers read so far."
            body += "\n\n### Papers read for this theme\n\n" + "\n".join(paper_line(paper) for paper in papers)
            path = out / f"{index:02d}_{slug(name)}.md"
            path.write_text(body + "\n", encoding="utf-8")
            chapter_files.append(path.name)

        totals = self.store.totals()
        summary = self.store.get("final_summary")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        footer = (f"\n\n*Written by {self.llm['model']} on {stamp}, from {totals['read']:,} papers "
                  f"({totals['full_text']:,} read in full). Chapters: {', '.join(chapter_files) or 'none yet'}.*\n")
        (out / "summary_check.md").write_text((self.store.get("summary_check") or "# Summary check\n\nNot run yet.") + "\n",
                                              encoding="utf-8")
        (out / "summary.md").write_text(
            (summary or "# Summary\n\nNot written yet. It comes after all the chapters.") + footer, encoding="utf-8")

        pack = prompts.PACK_HEADER.format(model=self.llm["model"], screened=f"{totals['screened']:,}",
                                          read=f"{totals['read']:,}", full_text=f"{totals['full_text']:,}",
                                          about=self.about)
        pack += "\n## Draft summary by the local model\n\n" + (summary or "(not written yet)")
        pack += "\n\n## Chapters by the local model\n\n" + "\n\n".join(
            self.store.chapter(theme["name"]) or f"## {theme['name']}\n\n(not written yet)" for theme in self.themes)
        papers = self.store.read_papers()
        pack += "\n\n## Paper notes\n\n" + "\n\n".join(
            format_note(paper, with_link=True) + f"\nThemes: {paper['themes']}" for paper in papers)
        (out / "claude_pack.md").write_text(pack + "\n", encoding="utf-8")

        with open(out / "papers.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "themes", "relevance", "title", "authors", "year", "venue", "cited_by",
                             "read_from", "strength", "key_findings", "for_the_app", "link"])
            for paper in papers:
                notes = json.loads(paper["notes"])
                writer.writerow([f"P{paper['pid']}", paper["themes"], paper["relevance"], paper["title"],
                                 paper["authors"], paper["year"], paper["venue"], paper["cited_by"],
                                 paper["text_source"], notes.get("strength"), " | ".join(notes.get("findings") or []),
                                 notes.get("for_app"), link(paper)])

        # The wanted list: before reading (phase 1), what the machine sources could not get; after, what was read
        # without a full text.
        wanted_rows = self.store.picked_with_cache() if self.phase == 1 else self.store.picked_papers()
        info = centrality(self.store)
        count = write_ris(wanted_rows, self.anchors, out / "zotero_import.ris", info, limit=self.b.get("zotero_top", 100))
        write_wanted(wanted_rows, self.anchors, out / "wanted.csv", info)
        log.info("Zotero list: %d papers still without full text in %s", count, out / "zotero_import.ris")

        with open(out / "method_cards.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["paper_id", "family", "source_type", "asset_class", "version", "read_from", "evidence",
                             "themes", "title", "year"] + [field for field in prompts.METHOD_CARD_FIELDS if field != "asset_class"]
                            + ["source_note", "checked"])
            for paper, notes, card in method_cards(papers, other_assets=True):
                writer.writerow([f"P{paper['pid']}", card.get("family", ""), card_source(paper, card),
                                 card.get("asset_class", "") or "not reported",
                                 "working paper" if card.get("version") else "", paper["text_source"],
                                 notes.get("strength"), paper["themes"], paper["title"], paper["year"]]
                                + [card.get(field, "") for field in prompts.METHOD_CARD_FIELDS if field != "asset_class"]
                                + [card.get("source_note", ""), card.get("checked", "")])

    # One paper on demand

    def read_single(self, work):
        """Read one paper now (the 'paper' command). Returns (notes, source)."""
        pid = self.store.add_paper(work)
        row = self.store.one("SELECT * FROM papers WHERE pid = ?", pid)
        text, source = self.fetch_text(row)
        if not text:
            return None, "nothing to read"
        theme = {"name": "Trading research in general",
                 "question": "What does this paper show that matters for traders and for the market insight app?"}
        return self.take_notes(theme, row, text, source), source

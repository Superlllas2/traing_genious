"""Everything the researcher learns goes into one SQLite file, so a restart never loses work."""

import json
import re
import sqlite3
import time
import unicodedata

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    pid INTEGER PRIMARY KEY AUTOINCREMENT,   -- shown in reports as [P12]
    openalex_id TEXT UNIQUE,
    doi TEXT,
    title TEXT,
    year INTEGER,
    venue TEXT,
    authors TEXT,
    cited_by INTEGER DEFAULT 0,
    abstract TEXT,
    pdf_url TEXT,
    oa_url TEXT,
    landing_url TEXT,
    refs TEXT,                  -- JSON list of OpenAlex ids this paper cites
    added_at REAL,
    text_source TEXT,           -- full text (pdf), full text (web page), abstract only
    text_chars INTEGER,
    notes TEXT,                 -- JSON notes from the reading step
    read_at REAL,
    read_seconds REAL,
    read_error TEXT,            -- why there are no notes; "no text ..." when there was nothing real to read
    title_key TEXT,             -- normalized title, to spot the same paper under another id
    repo_urls TEXT,             -- JSON list of repository copies (OpenAlex locations)
    local_pdf TEXT              -- a PDF you saved (Zotero import), read before anything else
);
CREATE TABLE IF NOT EXISTS paper_themes (
    pid INTEGER,
    theme TEXT,
    origin TEXT,                -- search, or snowball (found through references and citations)
    prefilter REAL DEFAULT 0,   -- cheap priority before the model looks at it
    relevance REAL,             -- 0 to 10 from screening; -1 when screening failed
    kind TEXT,
    one_line TEXT,
    screened_at REAL,
    screen_seconds REAL,
    picked INTEGER DEFAULT 0,   -- 1 when chosen for full reading under this theme
    PRIMARY KEY (pid, theme)
);
CREATE TABLE IF NOT EXISTS queries (
    theme TEXT,
    query TEXT,
    kind TEXT,
    done_at REAL,
    results INTEGER,
    PRIMARY KEY (theme, query, kind)
);
CREATE TABLE IF NOT EXISTS themes (
    name TEXT PRIMARY KEY,
    snowball_done INTEGER DEFAULT 0,
    chapter TEXT,
    chapter_at REAL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS api_usage (day TEXT, kind TEXT, calls INTEGER, PRIMARY KEY (day, kind));
CREATE INDEX IF NOT EXISTS pt_theme ON paper_themes (theme, origin, relevance);
CREATE TABLE IF NOT EXISTS text_cache (pid INTEGER PRIMARY KEY, source TEXT, text TEXT, fetched_at REAL);
CREATE TABLE IF NOT EXISTS s2_cache (pid INTEGER PRIMARY KEY, text TEXT, used INTEGER, citing INTEGER, fetched_at REAL);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS papers_doi ON papers (doi);
CREATE INDEX IF NOT EXISTS papers_title_key ON papers (title_key);
"""


def doi_key(doi):
    doi = (doi or "").strip().lower()
    return re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi)


def title_key(title):
    """Lower case letters and digits only: "Size, Analyst Coverage, and" and "Size, Analyst Coverage and" match."""
    text = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", text)


class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        columns = [row["name"] for row in self.db.execute("PRAGMA table_info(papers)")]
        for column in ("title_key", "repo_urls", "local_pdf"):
            if column not in columns:  # a database from an older version
                self.db.execute(f"ALTER TABLE papers ADD COLUMN {column} TEXT")
        self.db.executescript(INDEXES)
        self.db.commit()

    def close(self):
        self.db.close()

    def one(self, sql, *args):
        return self.db.execute(sql, args).fetchone()

    def all(self, sql, *args):
        return self.db.execute(sql, args).fetchall()

    def run(self, sql, *args):
        cursor = self.db.execute(sql, args)
        self.db.commit()
        return cursor

    # meta and API budget

    def get(self, key, default=None):
        row = self.one("SELECT value FROM meta WHERE key = ?", key)
        return row["value"] if row else default

    def put(self, key, value):
        self.run("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 key, None if value is None else str(value))

    def usage(self, day, kind):
        row = self.one("SELECT calls FROM api_usage WHERE day = ? AND kind = ?", day, kind)
        return row["calls"] if row else 0

    def add_usage(self, day, kind):
        self.run("INSERT INTO api_usage (day, kind, calls) VALUES (?, ?, 1) "
                 "ON CONFLICT(day, kind) DO UPDATE SET calls = calls + 1", day, kind)

    # searches

    def query_done(self, theme, query, kind):
        return self.one("SELECT 1 FROM queries WHERE theme = ? AND query = ? AND kind = ? AND done_at IS NOT NULL",
                        theme, query, kind) is not None

    def mark_query(self, theme, query, kind, results):
        self.run("INSERT OR REPLACE INTO queries (theme, query, kind, done_at, results) VALUES (?, ?, ?, ?, ?)",
                 theme, query, kind, time.time(), results)

    # papers

    def add_paper(self, work):
        """Insert a paper, or fill in what was missing. Returns its pid."""
        row = self.one("SELECT pid FROM papers WHERE openalex_id = ?", work["openalex_id"]) or self.same_paper(work)
        refs = json.dumps(work.get("refs") or [])
        if row:
            self.run("""UPDATE papers SET
                        cited_by = MAX(COALESCE(cited_by, 0), ?1),
                        abstract = CASE WHEN LENGTH(COALESCE(abstract, '')) < LENGTH(?2) THEN ?2 ELSE abstract END,
                        pdf_url = CASE WHEN COALESCE(pdf_url, '') = '' THEN ?3 ELSE pdf_url END,
                        oa_url = CASE WHEN COALESCE(oa_url, '') = '' THEN ?4 ELSE oa_url END,
                        refs = CASE WHEN COALESCE(refs, '[]') = '[]' THEN ?5 ELSE refs END,
                        repo_urls = ?7
                        WHERE pid = ?6""",
                     work.get("cited_by") or 0, work.get("abstract") or "", work.get("pdf_url") or "",
                     work.get("oa_url") or "", refs, row["pid"], json.dumps(self.merged_urls(row["pid"], work)))
            return row["pid"]
        cursor = self.run(
            """INSERT INTO papers (openalex_id, doi, title, year, venue, authors, cited_by, abstract,
                                   pdf_url, oa_url, landing_url, refs, added_at, title_key, repo_urls)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            work["openalex_id"], work.get("doi") or "", work.get("title") or "", work.get("year"),
            work.get("venue") or "", work.get("authors") or "", work.get("cited_by") or 0,
            work.get("abstract") or "", work.get("pdf_url") or "", work.get("oa_url") or "",
            work.get("landing_url") or "", refs, time.time(), title_key(work.get("title")),
            json.dumps(work.get("repo_urls") or []))
        return cursor.lastrowid

    def merged_urls(self, pid, work):
        """Repository copies of every version we have seen of this paper."""
        row = self.one("SELECT repo_urls, pdf_url, oa_url FROM papers WHERE pid = ?", pid)
        urls = json.loads(row["repo_urls"] or "[]") if row else []
        extra = list(work.get("repo_urls") or [])
        if work.get("pdf_url"):
            extra.append(work["pdf_url"])  # another version's own free copy (a working paper, say)
        for url in extra:
            if url not in urls:
                urls.append(url)
        return urls

    def same_paper(self, work):
        """The same paper under another OpenAlex id (a working paper and its journal version, for example):
        same DOI, or same title within a few years. Short titles like "Introduction" are not matched."""
        doi = doi_key(work.get("doi"))
        if doi:
            for row in self.all("SELECT pid, doi FROM papers WHERE doi LIKE ?", "%" + doi):
                if doi_key(row["doi"]) == doi:
                    return row
        key = title_key(work.get("title"))
        if len(key) < 25:
            return None
        for row in self.all("SELECT pid, year FROM papers WHERE title_key = ?", key):
            if not row["year"] or not work.get("year") or abs(row["year"] - work["year"]) <= 6:
                return row
        return None

    def link(self, pid, theme, origin, prefilter):
        """Connect a paper to a theme. Finding it again through another search raises its priority."""
        row = self.one("SELECT prefilter FROM paper_themes WHERE pid = ? AND theme = ?", pid, theme)
        if row:
            self.run("UPDATE paper_themes SET prefilter = ? WHERE pid = ? AND theme = ?",
                     max(row["prefilter"], prefilter) + 0.1, pid, theme)
            return False
        self.run("INSERT INTO paper_themes (pid, theme, origin, prefilter) VALUES (?, ?, ?, ?)",
                 pid, theme, origin, prefilter)
        return True

    def theme_openalex_ids(self, theme):
        rows = self.all("SELECT p.openalex_id FROM papers p JOIN paper_themes t ON t.pid = p.pid "
                        "WHERE t.theme = ?", theme)
        return {row["openalex_id"] for row in rows}

    # screening

    def screened_count(self, theme, origin=None):
        if origin:
            return self.one("SELECT COUNT(*) AS n FROM paper_themes WHERE theme = ? AND origin = ? "
                            "AND relevance IS NOT NULL", theme, origin)["n"]
        return self.one("SELECT COUNT(*) AS n FROM paper_themes WHERE theme = ? AND relevance IS NOT NULL",
                        theme)["n"]

    def candidate_count(self, theme, origin):
        return self.one("SELECT COUNT(*) AS n FROM paper_themes WHERE theme = ? AND origin = ?",
                        theme, origin)["n"]

    def next_unscreened(self, theme, origin):
        return self.one("""SELECT p.*, t.theme, t.prefilter FROM paper_themes t JOIN papers p ON p.pid = t.pid
                           WHERE t.theme = ? AND t.origin = ? AND t.relevance IS NULL
                           ORDER BY t.prefilter DESC, p.cited_by DESC LIMIT 1""", theme, origin)

    def save_screen(self, pid, theme, relevance, kind, one_line, seconds):
        self.run("""UPDATE paper_themes SET relevance = ?, kind = ?, one_line = ?, screened_at = ?, screen_seconds = ?
                    WHERE pid = ? AND theme = ?""", relevance, kind, one_line, time.time(), seconds, pid, theme)

    # reading

    def picked_count(self, theme):
        # papers with nothing real to read do not use up the reading budget
        return self.one("""SELECT COUNT(*) AS n FROM paper_themes t JOIN papers p ON p.pid = t.pid
                           WHERE t.theme = ? AND t.picked = 1 AND COALESCE(p.read_error, '') NOT LIKE 'no text%'""",
                        theme)["n"]

    def unpicked_candidates(self, theme, min_relevance, limit=300):
        return self.all("""SELECT p.*, t.relevance, t.kind, t.one_line FROM paper_themes t
                           JOIN papers p ON p.pid = t.pid
                           WHERE t.theme = ? AND t.picked = 0 AND t.relevance >= ?
                           ORDER BY t.relevance DESC, p.cited_by DESC LIMIT ?""", theme, min_relevance, limit)

    def picked_papers(self):
        """Every paper chosen for reading, with or without notes (papers waiting for a PDF too)."""
        return self.all("""SELECT p.*, MAX(t.relevance) AS relevance, GROUP_CONCAT(t.theme, '; ') AS themes
                           FROM paper_themes t JOIN papers p ON p.pid = t.pid
                           WHERE t.picked = 1 AND p.read_at IS NOT NULL GROUP BY p.pid""")

    def next_picked_unread(self):
        """A paper chosen for reading but not read yet, for example after a restart."""
        return self.one("""SELECT p.*, t.theme FROM paper_themes t JOIN papers p ON p.pid = t.pid
                           WHERE t.picked = 1 AND p.read_at IS NULL
                           ORDER BY t.relevance DESC LIMIT 1""")

    def mark_picked(self, pid, theme):
        self.run("UPDATE paper_themes SET picked = 1 WHERE pid = ? AND theme = ?", pid, theme)
        # new reading makes the chapter and the final summary out of date
        self.run("UPDATE themes SET chapter = NULL, chapter_at = NULL WHERE name = ?", theme)
        self.put("final_done", None)

    def save_notes(self, pid, notes, text_source, text_chars, seconds, error):
        self.run("""UPDATE papers SET notes = ?, text_source = ?, text_chars = ?, read_at = ?, read_seconds = ?,
                    read_error = ? WHERE pid = ?""",
                 json.dumps(notes, ensure_ascii=False) if notes else None, text_source, text_chars,
                 time.time(), seconds, error, pid)

    def read_papers(self, theme=None):
        """Papers with notes. For a theme: only the ones picked for it, best first."""
        if theme:
            return self.all("""SELECT p.*, t.relevance, t.kind, t.one_line, t.theme FROM paper_themes t
                               JOIN papers p ON p.pid = t.pid
                               WHERE t.theme = ? AND t.picked = 1 AND p.notes IS NOT NULL
                               ORDER BY t.relevance DESC, p.cited_by DESC""", theme)
        return self.all("""SELECT p.*, MAX(t.relevance) AS relevance,
                                  GROUP_CONCAT(t.theme, '; ') AS themes FROM paper_themes t
                           JOIN papers p ON p.pid = t.pid
                           WHERE t.picked = 1 AND p.notes IS NOT NULL
                           GROUP BY p.pid ORDER BY p.pid""")

    def top_read(self, theme, limit, picked_only=False):
        """The best papers read for a theme: seeds for following references and citations.
        With picked_only (phase 1, nothing read yet): the best papers chosen for reading."""
        notes = "" if picked_only else "AND p.notes IS NOT NULL"
        return self.all(f"""SELECT p.* FROM paper_themes t JOIN papers p ON p.pid = t.pid
                            WHERE t.theme = ? AND t.picked = 1 {notes}
                            ORDER BY t.relevance DESC, p.cited_by DESC LIMIT ?""", theme, limit)

    # phase 1 caches: full text found, and sentences from citing papers

    def cached_text(self, pid):
        return self.one("SELECT source, text FROM text_cache WHERE pid = ?", pid)

    def cache_text(self, pid, source, text):
        self.run("INSERT OR REPLACE INTO text_cache (pid, source, text, fetched_at) VALUES (?, ?, ?, ?)",
                 pid, source, text, time.time())

    def cached_contexts(self, pid):
        return self.one("SELECT text, used, citing FROM s2_cache WHERE pid = ?", pid)

    def cache_contexts(self, pid, text, used, citing):
        self.run("INSERT OR REPLACE INTO s2_cache (pid, text, used, citing, fetched_at) VALUES (?, ?, ?, ?, ?)",
                 pid, text, used, citing, time.time())

    def next_picked_unfetched(self):
        return self.one("""SELECT p.*, t.theme FROM paper_themes t JOIN papers p ON p.pid = t.pid
                           WHERE t.picked = 1 AND p.pid NOT IN (SELECT pid FROM text_cache)
                           ORDER BY t.relevance DESC LIMIT 1""")

    def picked_with_cache(self):
        """Phase 1: every paper chosen for reading, with what the machine sources found for it."""
        return self.all("""SELECT p.pid, p.title, p.authors, p.year, p.venue, p.doi, p.cited_by, p.local_pdf,
                                  MAX(t.relevance) AS relevance, GROUP_CONCAT(t.theme, '; ') AS themes,
                                  COALESCE(c.source, 'not fetched') AS text_source
                           FROM paper_themes t JOIN papers p ON p.pid = t.pid
                           LEFT JOIN text_cache c ON c.pid = p.pid
                           WHERE t.picked = 1 GROUP BY p.pid""")

    # themes

    def ensure_themes(self, names):
        for name in names:
            self.run("INSERT OR IGNORE INTO themes (name) VALUES (?)", name)

    def snowball_done(self, theme):
        row = self.one("SELECT snowball_done FROM themes WHERE name = ?", theme)
        return bool(row and row["snowball_done"])

    def set_snowball_done(self, theme):
        self.run("UPDATE themes SET snowball_done = 1 WHERE name = ?", theme)

    def chapter(self, theme):
        row = self.one("SELECT chapter FROM themes WHERE name = ?", theme)
        return row["chapter"] if row else None

    def save_chapter(self, theme, text):
        self.run("UPDATE themes SET chapter = ?, chapter_at = ? WHERE name = ?", text, time.time(), theme)

    # numbers for status and progress messages

    def average(self, column, table):
        row = self.one(f"SELECT AVG({column}) AS a FROM {table} WHERE {column} > 0")
        return row["a"] if row and row["a"] else None

    def totals(self):
        return {
            "papers": self.one("SELECT COUNT(*) AS n FROM papers")["n"],
            "screened": self.one("SELECT COUNT(*) AS n FROM paper_themes WHERE relevance IS NOT NULL")["n"],
            "read": self.one("SELECT COUNT(*) AS n FROM papers WHERE notes IS NOT NULL")["n"],
            "full_text": self.one("SELECT COUNT(*) AS n FROM papers WHERE notes IS NOT NULL "
                                  "AND text_source LIKE 'full text%'")["n"],
        }

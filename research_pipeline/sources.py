"""Where papers come from: the OpenAlex catalog, and free full texts from machine friendly sources only:
PDFs you saved (Zotero), CORE, arXiv, and repository copies found through Unpaywall and OpenAlex.
Publisher websites and SSRN are never tried, and a site that blocks us is left alone."""

import io
import json
import os
import queue
import re
import sqlite3
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser

from common import HTTPError, TimedOut, Unreachable, get_json, http_request, load_secrets, log

OPENALEX = os.environ.get("OPENALEX_URL", "https://api.openalex.org")
FIELDS = ("id,doi,title,display_name,publication_year,cited_by_count,abstract_inverted_index,"
          "best_oa_location,open_access,primary_location,locations,referenced_works,type,authorships")

# Never fetched: publisher websites (they block scripts and their terms forbid it) and SSRN.
BLOCKED_HOSTS = ("ssrn.com", "doi.org", "wiley.com", "sciencedirect.com", "elsevier.com", "springer.com",
                 "link.springer.com", "tandfonline.com", "jstor.org", "oup.com", "academic.oup.com",
                 "cambridge.org", "sagepub.com", "emerald.com", "informs.org", "aeaweb.org", "jstage.jst.go.jp",
                 "nature.com", "mdpi.com", "ieee.org", "acm.org", "degruyter.com", "uchicago.edu/doi",
                 "journals.uchicago.edu", "annualreviews.org", "worldscientific.com", "iopscience.iop.org")


def blocked_url(url):
    host = urllib.parse.urlsplit(url or "").netloc.lower()
    return not host or any(host == name or host.endswith("." + name) for name in BLOCKED_HOSTS) \
        or "uchicago.edu/doi" in (url or "")
SKIP_TYPES = {"paratext", "dataset", "erratum", "editorial", "letter", "peer-review", "retraction",
              "supplementary-materials", "libguides", "standard", "grant"}


class BudgetExceeded(RuntimeError):
    """OpenAlex's free daily allowance is used up. It refills at midnight UTC."""


def short_id(value):
    """https://openalex.org/W123 -> W123"""
    return (value or "").rstrip("/").rsplit("/", 1)[-1]


def rebuild_abstract(inverted):
    """OpenAlex stores abstracts as {word: [positions]}; put the words back in order."""
    if not inverted:
        return ""
    slots = {}
    for word, positions in inverted.items():
        for position in positions:
            slots[position] = word
    return " ".join(slots[i] for i in sorted(slots))


def parse_work(work):
    best = work.get("best_oa_location") or {}
    open_access = work.get("open_access") or {}
    primary = work.get("primary_location") or {}
    names = [(a.get("author") or {}).get("display_name") for a in work.get("authorships") or []]
    names = [name for name in names if name]
    authors = ", ".join(names[:3]) + (" et al." if len(names) > 3 else "")
    return {
        "openalex_id": short_id(work.get("id")),
        "doi": work.get("doi") or "",
        "title": (work.get("display_name") or work.get("title") or "").strip(),
        "year": work.get("publication_year"),
        "venue": ((primary.get("source") or {}).get("display_name") or ""),
        "authors": authors,
        "cited_by": work.get("cited_by_count") or 0,
        "abstract": rebuild_abstract(work.get("abstract_inverted_index")),
        "pdf_url": best.get("pdf_url") or "",
        "oa_url": open_access.get("oa_url") or best.get("landing_page_url") or "",
        "landing_url": primary.get("landing_page_url") or work.get("doi") or "",
        "refs": [short_id(ref) for ref in work.get("referenced_works") or []],
        "type": work.get("type") or "",
        "repo_urls": repository_urls(work),
    }


def repository_urls(work):
    """Copies in repositories (university archives, RePEc, NBER, Figshare...), PDF links first."""
    pdfs, pages = [], []
    for location in work.get("locations") or []:
        source = location.get("source") or {}
        if source.get("type") not in ("repository", None) and not location.get("is_oa"):
            continue
        if source.get("type") == "journal":
            continue  # the publisher's own copy
        for url, bucket in ((location.get("pdf_url"), pdfs), (location.get("landing_page_url"), pages)):
            if url and not blocked_url(url) and url not in pdfs + pages:
                bucket.append(url)
    return pdfs + pages


def usable(work, min_year=None):
    """Skip things that are not papers, or that we can't judge at all."""
    if not work["title"] or work["type"] in SKIP_TYPES:
        return False
    if min_year and work["year"] and work["year"] < min_year:
        return False
    return bool(work["abstract"]) or work["cited_by"] >= 20


class OpenAlex:
    """Small OpenAlex client that keeps itself inside the free daily allowance.

    If OpenAlex ever changes and refuses part of a request (the field list, the year filter,
    the name of the id filter), it falls back to a simpler request instead of stopping."""

    ID_FILTERS = ("openalex", "ids.openalex", "openalex_id")

    def __init__(self, store, api_key="", pause=0.25):
        self.store = store
        self.api_key = api_key or ""
        # Free allowance per day: about 100 searches without a key, 1,000 with a free key.
        self.limits = {"search": 950, "list": 9500} if self.api_key else {"search": 95, "list": 950}
        self.pause = pause
        self.sleep = time.sleep
        self.last_call = 0.0
        self.use_select = True
        self.use_year_filter = True
        self.id_filter = 0  # which name of the id filter works; past the end means one by one

    def _get(self, path, params, kind):
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if kind != "single" and self.store.usage(day, kind) >= self.limits[kind]:
            raise BudgetExceeded(f"{kind} allowance used up for today")
        params = dict(params)
        if self.api_key:
            params["api_key"] = self.api_key
        url = OPENALEX + path + ("?" + urllib.parse.urlencode(params, safe=":|,>*") if params else "")
        wait = self.pause - (time.time() - self.last_call)
        if wait > 0:
            self.sleep(wait)
        for attempt in range(4):
            self.last_call = time.time()
            try:
                data = get_json(url, timeout=60)
                break
            except HTTPError as error:
                if error.code == 429:
                    raise BudgetExceeded("OpenAlex says the daily limit is reached") from None
                if error.code >= 500 and attempt < 3:
                    self.sleep(5 * (attempt + 1))
                    continue
                raise
            except Unreachable:
                if attempt < 3:
                    self.sleep(10 * (attempt + 1))
                    continue
                raise
        if kind != "single":
            self.store.add_usage(day, kind)
        return data

    def _works(self, path, params, kind):
        """A request for works. If OpenAlex refuses the short field list, ask for full records instead."""
        if self.use_select:
            params = dict(params, select=FIELDS)
        try:
            return self._get(path, params, kind)
        except HTTPError as error:
            if error.code != 400 or "select" not in params or "select" not in error.detail.lower():
                raise
            log.info("OpenAlex refused the field list (%s). Asking for full records from now on.", error.detail[:150])
            self.use_select = False
            return self._get(path, {k: v for k, v in params.items() if k != "select"}, kind)

    def search(self, query, per_page=100, sort=None, min_year=None):
        params = {"search": query, "per_page": min(per_page, 100)}
        if sort:
            params["sort"] = sort
        if min_year and self.use_year_filter:
            params["filter"] = f"publication_year:>{min_year - 1}"
        try:
            data = self._works("/works", params, "search")
        except HTTPError as error:
            detail = error.detail.lower()
            if error.code != 400 or "filter" not in params or not ("filter" in detail or "year" in detail):
                raise
            log.info("OpenAlex refused the year filter (%s). Old papers are dropped afterwards instead.",
                     error.detail[:150])
            self.use_year_filter = False
            params.pop("filter")
            data = self._works("/works", params, "search")
        return [parse_work(work) for work in data.get("results") or []]

    def by_ids(self, ids):
        """Look up many works at once, 50 per request."""
        works = []
        ids = [i for i in ids if re.fullmatch(r"W\d+", i)]
        for start in range(0, len(ids), 50):
            works.extend(self._by_id_chunk(ids[start:start + 50]))
        return works

    def _by_id_chunk(self, chunk):
        while self.id_filter < len(self.ID_FILTERS):
            name = self.ID_FILTERS[self.id_filter]
            try:
                data = self._works("/works", {"filter": f"{name}:" + "|".join(chunk), "per_page": 100}, "list")
                return [parse_work(work) for work in data.get("results") or []]
            except HTTPError as error:
                if error.code != 400:
                    raise
                log.info("OpenAlex refused the \"%s\" filter (%s). Trying another way.", name, error.detail[:150])
                self.id_filter += 1
        works = []  # no filter name works: look them up one by one (free, only slower)
        for openalex_id in chunk:
            try:
                works.append(self.lookup(openalex_id))
            except HTTPError as error:
                if error.code != 404:
                    raise
        return works

    def citing(self, openalex_id, per_page=25):
        """The most cited papers that cite this one."""
        params = {"filter": f"cites:{openalex_id}", "sort": "cited_by_count:desc", "per_page": per_page}
        try:
            data = self._works("/works", params, "list")
        except HTTPError as error:
            if error.code != 400:
                raise
            log.info("OpenAlex refused the citation search (%s). Skipping it.", error.detail[:150])
            return []
        return [parse_work(work) for work in data.get("results") or []]

    def lookup(self, identifier):
        """One work by OpenAlex id, DOI or arXiv link. Single lookups are free."""
        identifier = identifier.strip()
        arxiv = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", identifier) if "arxiv" in identifier.lower() else None
        if arxiv:
            key = "doi:10.48550/arXiv." + arxiv.group(1)
        elif re.fullmatch(r"W\d+", identifier):
            key = identifier
        elif "doi.org/" in identifier:
            key = "doi:" + identifier.split("doi.org/", 1)[1]
        elif identifier.startswith("10."):
            key = "doi:" + identifier
        elif identifier.startswith("https://openalex.org/"):
            key = short_id(identifier)
        else:
            key = identifier
        data = self._works("/works/" + urllib.parse.quote(key, safe=":/."), {}, "single")
        return parse_work(data)


# Full text

class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg", "math", "button"}
    BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6",
             "table", "blockquote", "figcaption", "dd", "dt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def html_to_text(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:  # broken HTML: keep what we have
        pass
    return clean_text("".join(parser.parts))


def pdf_to_text(data, max_pages=60):
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""  # pypdf not installed: the paper is read from its abstract instead
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages[:max_pages]:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return clean_text("\n".join(pages))
    except Exception as error:
        log.info("    could not read the PDF (%s)", error)
        return ""


def clean_text(text):
    text = text.replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", text)
    return text.strip()


def looks_like_full_text(text):
    """A real paper is long and has the usual sections; a landing page usually is not."""
    if len(text) < 8000:
        return False
    lower = text.lower()
    markers = sum(word in lower for word in ("introduction", "conclusion", "references", "results", "data"))
    return markers >= 2


def arxiv_id(paper):
    for value in (paper["pdf_url"], paper["oa_url"], paper["landing_url"], paper["doi"]):
        value = value or ""
        match = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", value) or \
            re.search(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", value, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def first_surname(authors):
    """'Louis K.C. Chan, Narasimhan Jegadeesh' -> 'chan'"""
    first = (authors or "").split(",")[0].replace(" et al.", "").strip()
    return re.sub(r"[^a-z]", "", first.split()[-1].lower()) if first else ""


def same_title(a, b):
    key = lambda text: re.sub(r"[^a-z0-9]", "", (text or "").lower())
    a, b = key(a), key(b)
    return bool(a) and bool(b) and (a == b or (min(len(a), len(b)) > 30 and (a in b or b in a)))


def doi_of(paper):
    doi = (paper["doi"] or "").strip()
    return re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)


class TextFetcher:
    """Finds a full text for a paper, trying machine friendly sources in a fixed order.
    Polite: keeps each service's rate limit, and never retries a site that refused or blocked us."""

    def __init__(self, max_mb=25, secrets=None):
        secrets = load_secrets() if secrets is None else secrets
        self.core_key = secrets.get("core_api_key", "")
        self.email = secrets.get("unpaywall_email", "")
        self.wiley_token = secrets.get("wiley_tdm_token", "")
        self.elsevier_key = secrets.get("elsevier_api_key", "")
        self.elsevier_insttoken = secrets.get("elsevier_insttoken", "")
        self.s2_key = secrets.get("semantic_scholar_api_key", "")
        self.core_cache = None   # set by the pipeline: CORE answers that arrived in the background
        self.max_bytes = max_mb * 1_000_000
        self.last_hit = {}
        self.refused = set()   # hosts that blocked us (401, 403, captcha): not tried again in this run
        self.slow = {}         # host -> when it timed out or stayed busy: skipped for the next 30 minutes
        # Wiley allows 3 requests a second and 60 per 10 minutes; Elsevier a few a second; CORE 5 per 10 seconds.
        self.gaps = {"api.core.ac.uk": 2.1, "export.arxiv.org": 3.1, "arxiv.org": 3.1, "api.unpaywall.org": 0.2,
                     "api.wiley.com": 10.5, "api.elsevier.com": 1.0, "api.semanticscholar.org": 1.1}

    def _wait_for(self, url):
        host = urllib.parse.urlsplit(url).netloc
        wait = self.gaps.get(host, 2.0) - (time.time() - self.last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self.last_hit[host] = time.time()

    def _get(self, url, headers=None, timeout=60):
        """One polite request. 401 or 403 (or a captcha page) is a block: that site is not asked again in this run.
        429 means busy: wait and ask again, up to three times. A timeout, or still busy after three waits: the site
        is skipped for 30 minutes (CORE's own lookups, which are slow by nature, are exempt from the timeout rule)."""
        host = urllib.parse.urlsplit(url).netloc
        if host in self.refused:
            raise HTTPError(403, "this site blocked us earlier in this run")
        if time.time() - self.slow.get(host, 0) < 1800:
            raise Unreachable(f"{host} timed out or was busy in the last 30 minutes")
        for attempt in range(4):
            self._wait_for(url)
            try:
                return http_request(url, headers=headers, timeout=timeout, max_bytes=self.max_bytes)
            except HTTPError as error:
                if error.code == 429 and attempt < 3:
                    pause = 10 * (attempt + 1) ** 2
                    log.info("    %s is busy (HTTP 429): waiting %d seconds", host, pause)
                    time.sleep(pause)
                    continue
                if error.code == 429:
                    self.slow[host] = time.time()
                    log.info("    %s is still busy after three waits: skipping it for 30 minutes", host)
                if error.code in (401, 403) or "just a moment" in error.detail.lower():
                    self.refused.add(host)
                    log.info("    %s refused us (HTTP %s): not asking it again in this run", host, error.code)
                raise
            except TimedOut:
                if host != "api.core.ac.uk":
                    self.slow[host] = time.time()
                    log.info("    %s timed out: skipping it for 30 minutes", host)
                raise

    def fetch(self, paper):
        """Returns (text, source). Empty text means: no full text found anywhere."""
        steps = (("your PDF", self._local), ("CORE (cached)", self._core_cached),
                 ("publisher text mining", self._publisher_tdm), ("arXiv", self._arxiv),
                 ("Unpaywall", self._unpaywall), ("OpenAlex repositories", self._repositories))
        for name, step in steps:
            try:
                text, source = step(paper)
            except (HTTPError, Unreachable, ValueError, KeyError) as error:
                log.info("    %s: nothing (%s)", name, str(error)[:100])
                continue
            if text and looks_like_full_text(text):
                return text, source
        return "", "abstract only"

    def _local(self, paper):
        path = paper["local_pdf"] if "local_pdf" in paper.keys() else None
        if path and os.path.exists(path):
            with open(path, "rb") as handle:
                data = handle.read()
            text = pdf_to_text(data, max_pages=None) if data[:5] == b"%PDF-" else html_to_text(data)
            return text, "full text (your PDF)"
        return "", ""

    def _core_cached(self, paper):
        text = self.core_cache.get(paper["pid"]) if self.core_cache is not None and "pid" in paper.keys() else None
        return (text, "full text (CORE)") if text else ("", "")

    def _publisher_tdm(self, paper):
        """The publishers' own text mining APIs, for the DOIs they publish. They answer only where you are
        entitled (a subscribing institution's network, or its token); a refusal is final for the run."""
        doi = doi_of(paper).lower()
        if self.wiley_token and doi.startswith(("10.1111/", "10.1002/")):
            body, content_type, _ = self._get("https://api.wiley.com/onlinelibrary/tdm/v1/articles/"
                                              + urllib.parse.quote(doi, safe=""),
                                              {"Wiley-TDM-Client-Token": self.wiley_token})
            if body[:5] == b"%PDF-":
                return pdf_to_text(body, max_pages=None), "full text (publisher text mining)"
        if self.elsevier_key and doi.startswith("10.1016/"):
            headers = {"X-ELS-APIKey": self.elsevier_key, "Accept": "text/xml"}
            if self.elsevier_insttoken:
                headers["X-ELS-Insttoken"] = self.elsevier_insttoken
            body, _, _ = self._get("https://api.elsevier.com/content/article/doi/" + urllib.parse.quote(doi, safe="/")
                                   + "?view=FULL", headers)
            if b"<ce:sections" in body or b"<xocs:rawtext" in body:  # without entitlement only the abstract comes
                return html_to_text(body), "full text (publisher text mining)"
        return "", ""

    def _core(self, paper):
        if not self.core_key:
            return "", ""
        headers = {"Authorization": "Bearer " + self.core_key}
        title = 'title:"' + re.sub(r'["\\]', " ", paper["title"] or "")[:200] + '"'
        # one request: CORE often takes a minute or two to answer
        queries = [f'doi:"{doi_of(paper)}" OR {title}' if doi_of(paper) else title]
        for query in queries:
            url = "https://api.core.ac.uk/v3/search/works/?" + urllib.parse.urlencode({"q": query, "limit": 5})
            body, _, _ = self._get(url, headers, timeout=180)  # CORE often takes one to two minutes
            for result in json.loads(body.decode("utf-8")).get("results") or []:
                text = clean_text(result.get("fullText") or "")
                same_doi = doi_of(paper) and (result.get("doi") or "").lower() == doi_of(paper).lower()
                if text and (same_doi or same_title(result.get("title"), paper["title"])):
                    return text, "full text (CORE)"
        return "", ""

    def _arxiv(self, paper):
        found = arxiv_id(paper)
        if not found:
            title = re.sub(r"[^A-Za-z0-9 ]", " ", paper["title"] or "")
            words = " AND ".join(f"ti:{word}" for word in title.split() if len(word) > 3)[:300]
            if not words:
                return "", ""
            url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": words, "max_results": 5})
            body, _, _ = self._get(url)
            feed = body.decode("utf-8", errors="replace")
            for entry in re.findall(r"<entry>(.*?)</entry>", feed, re.DOTALL):
                title_match = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                id_match = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", entry)
                if title_match and id_match and same_title(title_match.group(1), paper["title"]):
                    found = id_match.group(1)
                    break
        if not found:
            return "", ""
        body, content_type, _ = self._get(f"https://export.arxiv.org/pdf/{found}")
        return pdf_to_text(body, max_pages=None), "full text (arXiv)"

    def _unpaywall(self, paper):
        if not self.email or not doi_of(paper):
            return "", ""
        url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi_of(paper))}?email={urllib.parse.quote(self.email)}"
        body, _, _ = self._get(url)
        record = json.loads(body.decode("utf-8"))
        urls = []
        for location in record.get("oa_locations") or []:
            if location.get("host_type") != "repository":
                continue  # publisher copies are skipped
            for key in ("url_for_pdf", "url_for_landing_page", "url"):
                if location.get(key) and location[key] not in urls:
                    urls.append(location[key])
        return self._first_text(urls, "full text (Unpaywall repository)")

    def _repositories(self, paper):
        urls = json.loads(paper["repo_urls"] or "[]") if "repo_urls" in paper.keys() else []
        for url in (paper["pdf_url"], paper["oa_url"]):
            if url and url not in urls:
                urls.append(url)
        return self._first_text(urls, "full text (OpenAlex repository)")

    def _figshare_files(self, url):
        """Figshare pages are built by JavaScript; its free API lists the files of an article."""
        match = re.search(r"/articles/(?:[^/]+/)*?(\d{6,})(?:/|$|\?)", url) if "figshare" in url or "aura.american.edu" in url else None
        if not match:
            return []
        body, _, _ = self._get(f"https://api.figshare.com/v2/articles/{match.group(1)}")
        files = json.loads(body.decode("utf-8")).get("files") or []
        return [item["download_url"] for item in files if item.get("name", "").lower().endswith(".pdf")]

    def _first_text(self, urls, label):
        expanded = []
        for url in urls:
            try:
                expanded += self._figshare_files(url) if not blocked_url(url) else []
            except (HTTPError, Unreachable, ValueError):
                pass
            expanded.append(url)
        for url in expanded:
            if blocked_url(url):
                continue
            try:
                body, content_type, final_url = self._get(url)
            except (HTTPError, Unreachable) as error:
                log.info("    no full text from %s (%s)", urllib.parse.urlsplit(url).netloc, str(error)[:80])
                continue
            if blocked_url(final_url):
                continue  # the repository only sent us on to the publisher
            if body[:5] == b"%PDF-" or "pdf" in content_type.lower():
                text = pdf_to_text(body, max_pages=None)
            elif "html" in content_type.lower() or body.lstrip()[:1] == b"<":
                text = html_to_text(body)
                link = find_pdf_link(body, final_url)
                if not looks_like_full_text(text) and link and not blocked_url(link):
                    try:
                        body, content_type, _ = self._get(link)
                        if body[:5] == b"%PDF-":
                            text = pdf_to_text(body, max_pages=None)
                    except (HTTPError, Unreachable):
                        pass
            else:
                continue
            if looks_like_full_text(text):
                return text, label
        return "", ""


class CoreQueue:
    """CORE off the critical path: lookups run one at a time in a background thread, and every answer
    (text or nothing) is cached in the database, so a paper is asked about once and reading never waits."""

    def __init__(self, fetcher, db_path):
        self.fetcher = fetcher
        self.db_path = str(db_path)
        self.jobs = queue.Queue()
        self.pending = set()
        self.arrived = []          # pids whose full text came in since the last look
        self.lock = threading.Lock()
        db = sqlite3.connect(self.db_path, timeout=30)
        db.execute("CREATE TABLE IF NOT EXISTS core_cache (pid INTEGER PRIMARY KEY, text TEXT, checked_at REAL)")
        db.commit()
        db.close()
        self.thread = None

    def get(self, pid):
        db = sqlite3.connect(self.db_path, timeout=30)
        row = db.execute("SELECT text FROM core_cache WHERE pid = ?", (pid,)).fetchone()
        db.close()
        return row[0] if row and row[0] else None

    def checked(self, pid):
        db = sqlite3.connect(self.db_path, timeout=30)
        row = db.execute("SELECT 1 FROM core_cache WHERE pid = ?", (pid,)).fetchone()
        db.close()
        return row is not None

    def submit(self, paper):
        if not self.fetcher.core_key or self.checked(paper["pid"]):
            return
        with self.lock:
            if paper["pid"] in self.pending:
                return
            self.pending.add(paper["pid"])
        self.jobs.put({"pid": paper["pid"], "doi": paper["doi"], "title": paper["title"]})
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._work, name="core", daemon=True)
            self.thread.start()

    def busy(self):
        with self.lock:
            return bool(self.pending)

    def take_arrived(self):
        with self.lock:
            arrived, self.arrived = self.arrived, []
        return arrived

    def _work(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        while True:
            try:
                job = self.jobs.get(timeout=5)
            except queue.Empty:
                with self.lock:
                    if not self.pending:
                        break
                continue
            text = ""
            try:
                text, _ = self.fetcher._core(job)
                text = text if looks_like_full_text(text) else ""
            except (HTTPError, Unreachable, ValueError, KeyError) as error:
                log.info("    CORE (background): nothing for P%s (%s)", job["pid"], str(error)[:80])
            db.execute("INSERT OR REPLACE INTO core_cache (pid, text, checked_at) VALUES (?, ?, ?)",
                       (job["pid"], text, time.time()))
            db.commit()
            with self.lock:
                self.pending.discard(job["pid"])
                if text:
                    self.arrived.append(job["pid"])
            if text:
                log.info("    CORE (background): full text arrived for P%s (%s characters)", job["pid"], f"{len(text):,}")
        db.close()


class SemanticScholar:
    """Sentences from citing papers that describe a paper (Semantic Scholar citation contexts).
    Used for papers without full text: what others report about it, marked as secondary."""

    API = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, fetcher, api_key=""):
        self.fetcher = fetcher
        self.headers = {"x-api-key": api_key} if api_key else {}

    def _json(self, url):
        try:
            body, _, _ = self.fetcher._get(url, self.headers)   # waits and retries by itself when busy (429)
            return json.loads(body.decode("utf-8"))
        except HTTPError as error:
            if error.code == 404:
                return {}
            raise

    def paper_key(self, paper):
        """Find the paper in Semantic Scholar: by DOI; if that DOI is unknown (older journal DOIs often are), by
        title. A title result counts only if the title, the year (two years apart allowed: working paper versus
        journal) and the first author's surname all match."""
        doi = doi_of(paper)
        if doi and self._json(f"{self.API}/paper/DOI:{urllib.parse.quote(doi, safe='/')}?fields=title"):
            return "DOI:" + doi
        fields = "paperId,title,year,authors"
        found = self._json(self.API + "/paper/search/match?" + urllib.parse.urlencode(
            {"query": paper["title"] or "", "fields": fields}))
        for item in found.get("data") or []:
            if self.same_paper(item, paper):
                return item["paperId"]
        surname = first_surname(paper["authors"])
        found = self._json(self.API + "/paper/search?" + urllib.parse.urlencode(
            {"query": f"{paper['title'] or ''} {surname}".strip(), "fields": fields, "limit": 10}))
        for item in found.get("data") or []:
            if self.same_paper(item, paper):
                return item["paperId"]
        return None

    @staticmethod
    def same_paper(item, paper):
        if not same_title(item.get("title"), paper["title"]):
            return False
        year = paper["year"] if "year" in paper.keys() else None
        if year and item.get("year") and abs(int(item["year"]) - int(year)) > 2:
            return False
        surname = first_surname(paper["authors"])
        names = " ".join((author.get("name") or "") for author in item.get("authors") or []).lower()
        return not surname or surname in re.sub(r"[^a-z ]", "", names)

    def contexts(self, paper, cap=300, max_chars=24000):
        """Returns (snippets as text, number of snippets used, number of citing papers seen)."""
        key = self.paper_key(paper)
        if not key:
            return "", 0, 0
        items, offset = [], 0
        while offset < cap:
            page = self._json(f"{self.API}/paper/{urllib.parse.quote(key, safe=':/')}/citations?"
                              + urllib.parse.urlencode({"fields": "contexts,intents,title,year",
                                                        "limit": min(100, cap - offset), "offset": offset}))
            data = page.get("data") or []
            items += data
            if not data or page.get("next") is None:
                break
            offset = page["next"]
        surname = (re.split(r"[ ,]", (paper["authors"] or "").split(",")[0].strip()) or [""])[-1].lower()
        scored = []
        for item in items:
            citing = item.get("citingPaper") or {}
            intents = [intent.lower() for intent in item.get("intents") or []]
            for sentence in item.get("contexts") or []:
                lower = sentence.lower()
                score = 3 * any(intent in ("methodology", "result") for intent in intents)
                score += 2 * bool(re.search(r"\d+(\.\d+)?\s*(%|percent|basis points|bp|months?|days?)", lower))
                score += 6 * bool(surname and re.search(r"\b" + re.escape(surname) + r"\b", lower))  # names the paper
                score += bool(re.search(r"\b(find|found|show|document|report|drift|return)", lower))
                scored.append((score, f"[{citing.get('title') or 'citing paper'}, {citing.get('year') or ''}] {sentence.strip()}"))
        scored.sort(key=lambda pair: -pair[0])
        picked, size = [], 0
        for score, line in scored:
            if size + len(line) > max_chars:
                break
            picked.append(line)
            size += len(line) + 1
        return "\n".join("* " + line for line in picked), len(picked), len(items)


def find_pdf_link(body, base):
    """Repository landing pages usually name their PDF in a citation_pdf_url meta tag."""
    page = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    match = re.search(r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)', page, re.IGNORECASE) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url', page, re.IGNORECASE)
    return urllib.parse.urljoin(base, match.group(1)) if match else None


# Reading for the method card: pick the parts of the paper that hold the details, never cut blindly.

CARD_PATTERNS = {
    "sample period": r"sample period|sample (?:covers|spans|runs)|from (?:19|20)\d\d (?:to|through|until) (?:19|20)\d\d|(?:19|20)\d\d\s*(?:-|–|to)\s*(?:19|20)\d\d",
    "holding period": r"holding period|hold(?:ing)? (?:the|each|for)|event window|days? after|months? after|trading days|\[\s*[-+]?\d+\s*,\s*\+?\d+\s*\]|rebalanc",
    "returns": r"abnormal return|excess return|alpha|basis points|\bbp\b|per month|annuali[sz]ed|cumulative|\bcar\b|hedge portfolio|long.short|drift",
    "costs": r"transaction cost|trading cost|bid.ask|commission|after costs|net of cost|turnover|price impact|implementation",
    "tables": r"^\s*table\s+\d+|\btable\s+\d+\s+(?:shows|reports|presents)",
}


def split_chunks(text, size=3000):
    """Split on paragraph breaks into pieces of about `size` characters."""
    chunks, current = [], ""
    for paragraph in re.split(r"\n\s*\n", text):
        if current and len(current) + len(paragraph) > size:
            chunks.append(current)
            current = ""
        while len(paragraph) > size * 2:  # one huge paragraph (PDFs without blank lines)
            cut = paragraph.rfind("\n", 0, size) if paragraph.rfind("\n", 0, size) > size // 2 else size
            chunks.append((current + "\n" + paragraph[:cut]).strip())
            current, paragraph = "", paragraph[cut:]
        current = (current + "\n\n" + paragraph).strip()
    if current:
        chunks.append(current)
    return chunks


def select_for_card(text, budget_chars):
    """Keep the opening (abstract and introduction), the conclusion, and the chunks that mention the sample
    period, holding period, returns, costs and the main tables, best first, in paper order.
    Returns (selected text, chunks used, chunks in total). The reference list is dropped."""
    matches = list(re.finditer(r"\n\s*(references|bibliography|literature cited|works cited)\s*\n", text, re.IGNORECASE))
    if matches and matches[-1].start() > len(text) * 0.6:
        text = text[:matches[-1].start()]
    chunks = split_chunks(text)
    if sum(len(chunk) for chunk in chunks) <= budget_chars:
        return text, len(chunks), len(chunks)
    scores = []
    for index, chunk in enumerate(chunks):
        lower = chunk.lower()
        found = {name: len(re.findall(pattern, lower, re.MULTILINE)) for name, pattern in CARD_PATTERNS.items()}
        score = sum(min(count, 6) for count in found.values()) + 2 * sum(1 for count in found.values() if count)
        if re.search(r"\bconclu", lower[:300]):
            score += 15
        scores.append((score, index))
    keep = {0, 1}  # abstract and introduction
    conclusions = [i for i, chunk in enumerate(chunks) if re.search(r"(^|\n)\s*(\d+\.?\s*|[ivx]+\.\s*)?(conclusions?|concluding remarks|summary and conclusions?)\b", chunk[:400], re.IGNORECASE)]
    keep.add(conclusions[-1] if conclusions else len(chunks) - 1)  # the conclusion, or the last part before the references
    used = sum(len(chunks[i]) for i in keep if i < len(chunks))
    for score, index in sorted(scores, reverse=True):
        if index in keep or score == 0:
            continue
        if used + len(chunks[index]) > budget_chars:
            continue
        keep.add(index)
        used += len(chunks[index])
    picked = sorted(i for i in keep if i < len(chunks))
    parts, last = [], -1
    for index in picked:
        if index != last + 1:
            parts.append(f"[... part of the paper left out: no sample, holding period, return, cost or table details ...]")
        parts.append(chunks[index])
        last = index
    return "\n\n".join(parts), len(picked), len(chunks)

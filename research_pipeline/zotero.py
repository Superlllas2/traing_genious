"""Zotero handoff for papers the machine sources could not get in full.

1. reports/zotero_import.ris lists every paper read without full text, ranked: anchor papers first,
   then by relevance and citations. Import it into Zotero and run Find Available PDF; save the rest by hand.
2. Export the collection from Zotero as BibTeX with "Export Files" ticked, and copy that folder to pdfs/.
3. python3 researcher.py import-pdfs matches the PDFs to papers through the DOIs (or titles) in the .bib
   file, rereads those papers, and rewrites only the chapters they belong to.
"""

import json
import math
import re
from pathlib import Path

from osap import authors_match, same_team_size, surnames
from store import doi_key, title_key


def anchor_of(paper, anchors):
    """The anchor this paper is, if any: same year (one apart allowed) and the anchor's surnames."""
    for anchor in anchors or []:
        names = surnames(anchor["authors"])
        # three years apart allowed: working paper and journal versions, and odd years in OpenAlex
        if paper["year"] and abs(paper["year"] - anchor["year"]) <= 3 and authors_match(names, paper["authors"]) \
                and same_team_size(anchor["authors"], names, paper["authors"]):
            return anchor
    return None


def anchor_papers(papers, anchors, window=5):
    """For the anchor check: each anchor's one best paper among those with its surnames and team size. The closest
    year wins (working paper years in OpenAlex can be 4 years early), then a full text, then the lowest id."""
    best = {}
    for anchor in anchors or []:
        names = surnames(anchor["authors"])
        matches = [paper for paper in papers if paper["year"] and abs(paper["year"] - anchor["year"]) <= window
                   and authors_match(names, paper["authors"])
                   and same_team_size(anchor["authors"], names, paper["authors"])]
        if matches:
            best[anchor["what"]] = min(matches, key=lambda paper: (
                abs(paper["year"] - anchor["year"]), not (paper["text_source"] or "").startswith("full text"),
                paper["pid"]))
    return best


def centrality(store):
    """For each chosen paper: how many other chosen papers cite it, in how many themes it was chosen, and how many
    method cards it has (0 before reading)."""
    chosen = store.all("""SELECT p.pid, p.openalex_id, p.refs, p.notes, COUNT(DISTINCT t.theme) AS themes
                          FROM paper_themes t JOIN papers p ON p.pid = t.pid WHERE t.picked = 1 GROUP BY p.pid""")
    cited = {}
    for row in chosen:
        for ref in json.loads(row["refs"] or "[]"):
            cited[ref] = cited.get(ref, 0) + 1
    info = {}
    for row in chosen:
        cards = len((json.loads(row["notes"]) or {}).get("method_cards") or []) if row["notes"] else 0
        info[row["pid"]] = {"cited_by_chosen": cited.get(row["openalex_id"], 0), "themes": row["themes"], "cards": cards}
    return info


def importance(paper, info):
    """Citations (log scale), how many other chosen papers cite it, themes, screening relevance, method cards."""
    extra = info.get(paper["pid"], {}) if info else {}
    return round(2 * math.log10(1 + (paper["cited_by"] or 0)) + 0.5 * min(extra.get("cited_by_chosen", 0), 10)
                 + (extra.get("themes", 1) - 1) + (paper["relevance"] or 0) / 5 + 0.5 * min(extra.get("cards", 0), 4), 2)


def wanted(papers, anchors, info=None):
    """Papers without a full text, most important first: anchors, then by importance."""
    rows = [paper for paper in papers if not (paper["text_source"] or "").startswith("full text")
            and not (paper["local_pdf"] if "local_pdf" in paper.keys() else None)]
    return sorted(rows, key=lambda paper: (anchor_of(paper, anchors) is None, -importance(paper, info)))


def refused_by_login_publishers(folder):
    """Paper ids that fetch_entitled.py could not get from Elsevier (its API needs an institution token, but
    a library login in Zotero works): these always go on the Zotero list."""
    import csv
    ids = set()
    for log_file in Path(folder).rglob("fetch_log.csv"):
        with open(log_file, encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("route") == "Elsevier API" and not row.get("result", "").startswith("saved"):
                    ids.add(int(row["id"].lstrip("P")))
    return ids


def write_ris(papers, anchors, path, info=None, limit=None, always=()):
    """The ranked list as RIS: the top `limit` papers, plus every paper in `always` further down."""
    lines = []
    ranked = wanted(papers, anchors, info)
    chosen = ranked[:limit] + [paper for paper in ranked[limit:] if paper["pid"] in set(always)] if limit else ranked
    for rank, paper in enumerate(chosen, 1):
        anchor = anchor_of(paper, anchors)
        lines.append("TY  - JOUR")
        lines.append(f"TI  - {paper['title']}")
        for name in re.split(r",\s*", (paper["authors"] or "").replace(" et al.", "")):
            if name.strip():
                lines.append(f"AU  - {name.strip()}")
        if paper["year"]:
            lines.append(f"PY  - {paper['year']}")
        if paper["venue"]:
            lines.append(f"JO  - {paper['venue']}")
        if doi_key(paper["doi"]):
            lines.append(f"DO  - {doi_key(paper['doi'])}")
        lines.append(f"KW  - P{paper['pid']}")
        note = f"Trading research P{paper['pid']}, rank {rank}, read from: {paper['text_source']}"
        if anchor:
            note += f", anchor paper ({anchor['what']})"
        lines.append(f"N1  - {note}")
        lines.append("ER  - ")
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return len([line for line in lines if line.startswith("TY")])


def write_wanted(papers, anchors, path, info=None):
    """The whole ranked list as a CSV, for fetch_entitled.py on a network with library access."""
    import csv
    rows = wanted(papers, anchors, info)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "id", "doi", "title", "authors", "year", "read_from", "anchor", "importance",
                         "citations", "cited_by_chosen_papers", "themes", "method_cards"])
        for rank, paper in enumerate(rows, 1):
            anchor = anchor_of(paper, anchors)
            extra = (info or {}).get(paper["pid"], {})
            writer.writerow([rank, f"P{paper['pid']}", doi_key(paper["doi"]), paper["title"], paper["authors"],
                             paper["year"], paper["text_source"], anchor["what"] if anchor else "",
                             importance(paper, info), paper["cited_by"], extra.get("cited_by_chosen", 0),
                             extra.get("themes", 1), extra.get("cards", 0)])
    return len(rows)


def bib_entries(text):
    """Very small BibTeX reader: the doi, title and file fields of each entry."""
    entries = []
    for chunk in re.split(r"\n@", "\n" + text)[1:]:
        fields = {}
        for name in ("doi", "title", "file"):
            match = re.search(r"\b" + name + r"\s*=\s*[{\"](.*?)[}\"]\s*,?\s*\n", chunk, re.IGNORECASE | re.DOTALL)
            if match:
                fields[name] = re.sub(r"[{}]", "", match.group(1)).strip()
        entries.append(fields)
    return entries


def pdf_paths(file_field, base):
    """Zotero writes files as 'Full Text PDF:files/12/name.pdf:application/pdf', several joined by ';'."""
    paths = []
    for part in re.split(r";(?=[^;]*\.pdf)", file_field or ""):
        pieces = part.split(":")
        candidates = [piece for piece in pieces if piece.lower().endswith(".pdf")] or [part]
        for candidate in candidates:
            candidate = candidate.replace("\\:", ":").strip()
            if not candidate.lower().endswith(".pdf"):
                continue  # an entry without a file: no match (it used to match the export folder itself)
            path = Path(candidate)
            path = path if path.is_absolute() else Path(base) / path
            if path.is_file():
                paths.append(path)
    return paths


def import_pdfs(folder, store):
    """Match PDFs in the folder to papers. Returns a list of (pid, path) that were attached."""
    folder = Path(folder)
    by_doi, by_title, short_titles = {}, {}, {}
    for row in store.all("SELECT pid, doi, title_key, authors FROM papers"):
        if doi_key(row["doi"]):
            by_doi[doi_key(row["doi"])] = row["pid"]
        if row["title_key"] and len(row["title_key"]) >= 10:
            first = (row["authors"] or "").split(",")[0].replace(" et al.", "").split()
            surname = re.sub(r"[^a-z]", "", first[-1].lower()) if first else ""
            (by_title if len(row["title_key"]) >= 25 else short_titles).setdefault(row["title_key"], []).append(
                (row["pid"], surname))
    bib_titles = {key: papers[0][0] for key, papers in by_title.items()}  # .bib entries match on title alone
    attached, unmatched = [], []
    for bib in folder.rglob("*.bib"):
        for entry in bib_entries(bib.read_text(encoding="utf-8", errors="replace")):
            pid = by_doi.get(doi_key(entry.get("doi"))) or bib_titles.get(title_key(entry.get("title")))
            paths = pdf_paths(entry.get("file"), bib.parent)
            if pid and paths:
                attached.append((pid, str(paths[0].resolve())))
    files = list(folder.rglob("P*.pdf")) + list(folder.rglob("P*.xml"))
    for pdf in files:  # files named after the paper id (by hand, or by fetch_entitled.py) also work
        match = re.fullmatch(r"P(\d+)", pdf.stem)
        if match and not any(pid == int(match.group(1)) for pid, _ in attached):
            attached.append((int(match.group(1)), str(pdf.resolve())))
    # Any other PDF (saved by hand under any name): recognise it by the DOI or the title printed in it.
    known = {path for _, path in attached}
    taken = {pid for pid, _ in attached}
    for pdf in folder.rglob("*.pdf"):
        if str(pdf.resolve()) in known:
            continue
        recognised = recognise_pdf(pdf, by_doi, by_title, short_titles)
        if not recognised:
            unmatched.append(str(pdf))
        for pid in recognised:
            if pid not in taken:  # a second copy of a paper that already has a file is simply not used
                attached.append((pid, str(pdf.resolve())))
                taken.add(pid)
    for pid, path in attached:
        store.run("UPDATE papers SET local_pdf = ? WHERE pid = ?", path, pid)
    import_pdfs.unmatched = unmatched
    return attached


def recognise_pdf(path, by_doi, by_title, short_titles=None):
    """The paper(s) a PDF holds: a known DOI in its first pages; otherwise a known title in its opening text
    together with that paper's first author's surname. Long titles (25+ letters) may sit anywhere in the first
    4,000 characters, short ones only at the very top. Returns a list of paper ids: several when the database
    holds the same paper twice."""
    from sources import pdf_to_text
    try:
        text = pdf_to_text(Path(path).read_bytes(), max_pages=3)
    except OSError:
        return []
    for doi in re.findall(r"10\.\d{4,9}/[^\s\"<>]+", text):
        pid = by_doi.get(doi_key(doi.rstrip(".,;)")))
        if pid:
            return [pid]
    opening, top = title_key(text[:4000]), title_key(text[:1500])
    found = []
    for key, papers in list(by_title.items()) + list((short_titles or {}).items()):
        where = opening if len(key) >= 25 else top
        if key in where:
            # a title at the very top beats one further down (a cited paper), then the longer title wins
            found += [((key in top, len(key)), pid) for pid, surname in papers if surname and surname in opening]
    if not found:
        return []
    best = max(score for score, _ in found)
    return sorted({pid for score, pid in found if score == best})


def reread(store, pids):
    """Read these papers again, and mark only their chapters (and the summary) out of date."""
    for pid in pids:
        store.run("UPDATE papers SET notes = NULL, read_at = NULL, read_error = NULL WHERE pid = ?", pid)
        for row in store.all("SELECT theme FROM paper_themes WHERE pid = ? AND picked = 1", pid):
            store.run("UPDATE themes SET chapter = NULL, chapter_at = NULL WHERE name = ?", row["theme"])
    store.put("final_done", None)

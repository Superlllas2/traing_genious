"""Open Source Asset Pricing (Chen and Zimmermann, openassetpricing.com): a public dataset that rebuilds
hundreds of published return signals from the original papers.

Two files in data/osap/ (download them from openassetpricing.com, Data, if missing):
* SignalDoc.csv: one row per signal, with the paper (authors, year), sample years, holding period,
  the return and t stat the original paper reported.
* PredictorLSretWide.csv: monthly long short returns of every signal (optional). With it, the card also
  gets the return after publication.

A paper matches a signal when the year is the same (one year apart is allowed: working paper and journal
versions) and every author surname in the dataset appears in the paper's author list."""

import csv
import math
import re
import unicodedata
from pathlib import Path

from common import DATA_DIR, log

OSAP_DIR = DATA_DIR / "osap"
DATASET_NAME = "Open Source Asset Pricing"
# Fields a dataset card fills in. The others say "not reported (dataset)".
DATASET_FIELDS = ["method", "trigger", "direction", "entry", "holding_days", "reported_return", "after_costs",
                  "stocks", "market_years", "still_works", "data_needed"]
DATA_NOTES = {
    "Analyst": "analyst estimates (I/B/E/S): paid",
    "Accounting": "company accounts: paid as a database (Compustat), free from SEC filings by hand",
    "Price": "prices and volumes: paid as a database (CRSP), free daily prices from many sites",
    "Event": "company events: SEC filings and announcements, mostly free",
    "Trading": "trading data (spreads, volume): mostly paid",
    "13F": "fund holdings (SEC 13F filings): free",
    "Options": "options data: paid",
    "Other": "varies: see the paper",
}


def plain(text):
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def surnames(authors):
    """'Chan, Jegadeesh and Lakonishok 1996' -> ['chan', 'jegadeesh', 'lakonishok']"""
    text = re.sub(r"\b(19|20)\d\d\b", "", plain(authors))
    text = re.sub(r"\bet al\.?", "", text)
    parts = re.split(r",|\band\b|&", text)
    names = [re.sub(r"[^a-z]", "", part.strip().split()[-1]) for part in parts if part.strip()]
    return [name for name in names if name]


def authors_match(names, paper_authors):
    """Every surname (up to three) appears in the paper's author list. Hyphens and accents are ignored."""
    haystack = " " + re.sub(r"[^a-z ]", "", plain(paper_authors).replace("-", "")) + " "
    return bool(names) and all(" " + name + " " in haystack.replace(",", " ") for name in names[:3])


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def team_size(paper_authors):
    """Authors in the paper's list ('A, B, C et al.' means more than three)."""
    names = [name for name in re.split(r",\s*", (paper_authors or "").replace(" et al.", "")) if name.strip()]
    return len(names) + (1 if "et al" in (paper_authors or "") else 0)


def same_team_size(dataset_authors, surnames, paper_authors):
    """'Barber et al.' must not match Barber and Odean: et al. needs three or more authors, and a full list of
    names needs the same number of authors."""
    size = team_size(paper_authors)
    if re.search(r"et al", dataset_authors or "", re.IGNORECASE):
        return size >= 3
    return size == len(surnames) or (size > 3 and len(surnames) >= 3)


class SignalData:
    def __init__(self, folder=OSAP_DIR):
        folder = Path(folder)
        self.signals = []
        self.returns = {}
        doc = folder / "SignalDoc.csv"
        if not doc.exists():
            log.info("Open Source Asset Pricing: %s is missing, so no dataset cards", doc)
            return
        with open(doc, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("Cat.Signal") == "Predictor":
                    row["_surnames"] = surnames(row.get("Authors"))
                    row["_year"] = int(number(row.get("Year")) or 0)
                    self.signals.append(row)
        wide = folder / "PredictorLSretWide.csv"
        if wide.exists():
            with open(wide, encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader)
                for name in header[1:]:
                    self.returns[name] = []
                for row in reader:
                    year = int(row[0][:4])
                    for name, value in zip(header[1:], row[1:]):
                        if value not in ("", "NA"):
                            self.returns[name].append((year, float(value)))
        log.info("Open Source Asset Pricing: %d signals, monthly returns %s", len(self.signals),
                 "loaded" if self.returns else "not loaded (PredictorLSretWide.csv missing)")

    def match(self, paper):
        """Signals from this paper: same year (or one apart), every dataset surname in the author list."""
        year = paper["year"] or 0
        return [signal for signal in self.signals
                if abs(signal["_year"] - year) <= 1 and authors_match(signal["_surnames"], paper["authors"])
                and same_team_size(signal.get("Authors"), signal["_surnames"], paper["authors"])]

    def after_publication(self, signal):
        """Mean monthly long short return in the years after publication, with a t stat."""
        series = [value for year, value in self.returns.get(signal["Acronym"], []) if year > signal["_year"]]
        if len(series) < 24:
            return None
        mean = sum(series) / len(series)
        spread = math.sqrt(sum((value - mean) ** 2 for value in series) / (len(series) - 1))
        last = max(year for year, _ in self.returns[signal["Acronym"]])
        return mean, mean / (spread / math.sqrt(len(series))), signal["_year"] + 1, last

    def card(self, signal):
        months = number(signal.get("Portfolio Period"))
        ret, tstat = number(signal.get("Return")), number(signal.get("T-Stat"))
        start, end = signal.get("SampleStartYear") or "?", signal.get("SampleEndYear") or "?"
        if ret is not None:
            reported = f"{ret:.2f}% a month, long short portfolio" + (f", t stat {tstat:.2f}" if tstat else "") + \
                       " (as reported in the original paper)"
        elif tstat is not None:
            reported = f"return not recorded; t stat {tstat:.2f} in the original paper"
        else:
            reported = "not reported (dataset)"
        after = self.after_publication(signal) if self.returns else None
        if after:
            mean, t_after, first, last = after
            verdict = "yes" if mean > 0 and t_after >= 2 else ("mixed" if mean > 0 else "no")
            still = f"{verdict}: {mean:.2f}% a month after publication ({first} to {last}), t stat {t_after:.1f}"
        else:
            still = "not reported (monthly returns not loaded)" if not self.returns else "not reported (too few months)"
        weight = {"EW": "equal weighted", "VW": "value weighted"}.get(signal.get("Stock Weight"),
                                                                       signal.get("Stock Weight") or "")
        stocks = "US stocks (CRSP), " + (weight or "weighting not reported")
        if signal.get("Filter"):
            stocks += f", filter: {signal['Filter']}"
        quantile = number(signal.get("LS Quantile"))
        if quantile:
            stocks += f", top and bottom {quantile * 100:g}% of stocks" if quantile < 1 else f", top and bottom of {quantile:g} groups"
        category = signal.get("Cat.Data") or "Other"
        return {
            "method": f"{signal['LongDescription']} ({signal['Acronym']})",
            "trigger": (signal.get("Detailed Definition") or signal["LongDescription"])[:280],
            "direction": "both (buy the top group, sell short the bottom group)",
            "entry": "portfolio formed at the start of the month after the signal is known"
                     + (f", rebalanced in month {number(signal['Start Month']):g}" if number(signal.get("Start Month")) else ""),
            "holding_days": f"about {round(months * 21)} ({months:g} month{'s' if months != 1 else ''})" if months
                            else "not reported (dataset)",
            "reported_return": reported,
            "after_costs": "no (returns before trading costs)",
            "stocks": stocks,
            "market_years": f"US, {start} to {end}",
            "still_works": still,
            "data_needed": DATA_NOTES.get(category, category),
            "storyline_fit": "not reported (dataset)",
            "retail_usable": "not reported (dataset)",
            "asset_class": "stocks",
            "source_note": f"{DATASET_NAME}, signal {signal['Acronym']}: fields "
                           + ", ".join(DATASET_FIELDS) + " come from the dataset",
        }

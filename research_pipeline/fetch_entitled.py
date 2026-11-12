#!/usr/bin/env python3
"""Download the papers your library is entitled to, through the publishers' text mining APIs.

Run it on a network with library access (Saxion's, on campus or on its VPN). It needs only Python 3,
no extra packages. It reads the wanted list the researcher writes (reports/wanted.csv), downloads every
paper the publisher lets you have into one folder, at a polite rate, and logs which ones were refused.

  python3 fetch_entitled.py wanted.csv
  python3 fetch_entitled.py wanted.csv --out entitled --wiley-token TOKEN --elsevier-key KEY

Tokens can also come from the environment (WILEY_TDM_TOKEN, ELSEVIER_API_KEY, ELSEVIER_INSTTOKEN);
if they are missing you are asked for them. Leave one empty to skip that publisher.

Routes, by DOI:
* 10.1111/ and 10.1002/  Wiley text and data mining API (at most one request every 10 seconds)
* 10.1016/               Elsevier ScienceDirect article API, full text XML (one request a second)
* anything else          the publisher's text mining link listed in Crossref, if it has one (one request
                         every 5 seconds per website)

Then copy the output folder to pdfs/ next to researcher.py on the Spark and run:
  python3 researcher.py import-pdfs
Files are named after the paper id (P123.pdf or P123.xml). Running the script again skips files you have.
"""

import argparse
import csv
import getpass
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "TradingResearchTDM/1.0 (personal literature review; text and data mining)"
GAPS = {"api.wiley.com": 10.5, "api.elsevier.com": 1.0, "api.crossref.org": 1.0}
DEFAULT_GAP = 5.0
last_hit = {}


def wait(url):
    host = urllib.parse.urlsplit(url).netloc
    pause = GAPS.get(host, DEFAULT_GAP) - (time.time() - last_hit.get(host, 0))
    if pause > 0:
        time.sleep(pause)
    last_hit[host] = time.time()


def get(url, headers=None, timeout=90):
    wait(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(60_000_000), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        return error.code, error.read(2000), error.headers.get("Content-Type", "")
    except ssl.SSLError as error:
        sys.exit(f"SSL problem ({error}). On a Mac with Python from python.org, run 'Install Certificates.command' "
                 "in the Python folder of Applications once, or use /usr/bin/python3.")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return 0, str(error).encode(), ""


def wiley(doi, token):
    status, body, _ = get("https://api.wiley.com/onlinelibrary/tdm/v1/articles/" + urllib.parse.quote(doi, safe=""),
                          {"Wiley-TDM-Client-Token": token})
    if status == 200 and body[:5] == b"%PDF-":
        return body, "pdf", "saved"
    return None, None, f"refused (HTTP {status})" if status else f"error ({body[:80].decode(errors='replace')})"


def elsevier(doi, key, insttoken):
    headers = {"X-ELS-APIKey": key, "Accept": "text/xml"}
    if insttoken:
        headers["X-ELS-Insttoken"] = insttoken
    status, body, _ = get("https://api.elsevier.com/content/article/doi/" + urllib.parse.quote(doi, safe="/")
                          + "?view=FULL", headers)
    if status == 200 and (b"<ce:sections" in body or b"<xocs:rawtext" in body):
        return body, "xml", "saved"
    if status == 200:
        return None, None, "not entitled (only the abstract came back)"
    return None, None, f"refused (HTTP {status})" if status else f"error ({body[:80].decode(errors='replace')})"


def crossref_tdm(doi):
    status, body, _ = get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"))
    if status != 200:
        return None, None, f"not in Crossref (HTTP {status})"
    links = [link for link in (json.loads(body).get("message") or {}).get("link") or []
             if link.get("intended-application") == "text-mining"]
    if not links:
        return None, None, "no text mining link"
    reasons = []
    for link in sorted(links, key=lambda item: "pdf" not in (item.get("content-type") or "")):
        status, body, content_type = get(link["URL"])
        if status == 200 and body[:5] == b"%PDF-" and len(body) > 50_000:
            return body, "pdf", "saved"
        if status == 200 and b"<body" in body[:200_000].lower() and len(body) > 50_000 and "xml" in content_type:
            return body, "xml", "saved"
        reasons.append(f"HTTP {status}" if status != 200 else "not a full text")
    return None, None, "refused or not entitled (" + ", ".join(reasons) + ")"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wanted", help="wanted.csv from the researcher's reports folder")
    parser.add_argument("--out", default="entitled", help="folder for the papers (default: entitled)")
    parser.add_argument("--wiley-token")
    parser.add_argument("--elsevier-key")
    parser.add_argument("--elsevier-insttoken")
    args = parser.parse_args()
    wiley_token = args.wiley_token or os.environ.get("WILEY_TDM_TOKEN") or getpass.getpass(
        "Wiley TDM token (Enter to skip Wiley): ").strip()
    elsevier_key = args.elsevier_key or os.environ.get("ELSEVIER_API_KEY") or getpass.getpass(
        "Elsevier API key (Enter to skip Elsevier): ").strip()
    insttoken = args.elsevier_insttoken or os.environ.get("ELSEVIER_INSTTOKEN", "")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(args.wanted, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    log_path = out / "fetch_log.csv"
    new_log = not log_path.exists()
    counts = {}
    with open(log_path, "a", newline="", encoding="utf-8") as log_handle:
        log = csv.writer(log_handle)
        if new_log:
            log.writerow(["time", "id", "doi", "route", "result", "title"])
        for number, row in enumerate(rows, 1):
            pid, doi = row["id"], (row["doi"] or "").strip().lower()
            if any((out / f"{pid}.{ext}").exists() for ext in ("pdf", "xml")):
                continue
            if not doi:
                route, result, body, ext = "none", "no DOI", None, None
            elif doi.startswith(("10.1111/", "10.1002/")):
                route = "Wiley TDM"
                body, ext, result = wiley(doi, wiley_token) if wiley_token else (None, None, "skipped (no token)")
            elif doi.startswith("10.1016/"):
                route = "Elsevier API"
                body, ext, result = elsevier(doi, elsevier_key, insttoken) if elsevier_key else \
                    (None, None, "skipped (no key)")
            else:
                route = "Crossref TDM link"
                body, ext, result = crossref_tdm(doi)
            if body:
                (out / f"{pid}.{ext}").write_bytes(body)
            counts[result.split(" (")[0]] = counts.get(result.split(" (")[0], 0) + 1
            log.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), pid, doi, route, result, row.get("title", "")[:120]])
            log_handle.flush()
            print(f"[{number}/{len(rows)}] {pid} {route}: {result}")
    print("\nDone. " + ", ".join(f"{name}: {count}" for name, count in sorted(counts.items())))
    print(f"Papers are in {out.resolve()}; the log is {log_path}.")
    print("Copy that folder to pdfs/ on the Spark, then run: python3 researcher.py import-pdfs")


if __name__ == "__main__":
    main()

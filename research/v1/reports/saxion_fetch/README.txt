Fetch the papers Saxion is entitled to (run on Saxion's network: campus or VPN)

1. Open Terminal in this folder.
2. Run (one line):
   WILEY_TDM_TOKEN=<your-wiley-tdm-token> ELSEVIER_API_KEY=<your-elsevier-api-key> python3 fetch_entitled.py wanted.csv
3. Papers land in the folder "entitled" (P123.pdf or P123.xml), with a log in entitled/fetch_log.csv.
   Running it again skips what you already have.
4. Copy the "entitled" folder to the Spark, into trading_researcher_run2/pdfs/
5. On the Spark: .venv/bin/python researcher.py zotero-list   (writes the top 100 still missing for Zotero)

If Python complains about SSL certificates: run "Install Certificates.command" in the Python folder in
Applications once, or use /usr/bin/python3 instead of python3.

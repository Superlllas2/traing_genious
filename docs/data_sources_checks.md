# Data source checks

Run on 18 November 2026 from the Spark (Dutch home connection). These were quick, read-only looks:

* each request sent the User-Agent "TradingGenious research check (personal project)"
* requests to the same site were at least 3.5 seconds apart, and no check used more than 6 requests
* no sign-up, no login and no forms
* checks stopped on 403, 429 or a browser challenge

Page contents were not kept. This file holds only the findings. The open checks are listed in [data_sources.md](data_sources.md).

| # | Source | Result | Conclusion |
| --- | --- | --- | --- |
| 1 | AFM register (NL director dealings) | Partly | The export works but holds only date, issuer, person, role and LEI. Price, volume and type are only on each notice's detail page. |
| 2 | AMF BDIF (FR director dealings) | Blocked | The home page loads, but the RSS subscriptions page returned a firewall "Web Page Blocked!" page. |
| 3 | EQS news (DE director dealings) | Partly | No RSS feed or category page was found. The home page lists Directors' Dealings items in its HTML, and each item has every MAR field. The terms are restrictive. |
| 4 | Euronext press releases (NL, FR) | Partly | The list is not in the page HTML, and a second page met a bot challenge. The terms forbid systematic retrieval without written permission. |
| 5 | Ticker API (UK, RNS) | Works (terms only, no key used) | Free tier: 15-minute delay, 7 days of history, 1 request a second, 350 requests a week. Allowed only if the app is used by you alone. |
| 6 | FinancialReports / FinancialFilings | Needs a key | 500 free credits a month and a "Director's Dealing" filing type. Coverage per country for director dealings is not stated without a key. |
| 7 | GDELT DOC API (news) | Partly | 2 of 4 queries ran (NL: 0 articles, UK: 11 copies of one story). DE and FR got 429 because the spacing was below GDELT's 5 seconds. |
| 8 | Stooq (daily prices) | Blocked | The CSV download answered with a JavaScript browser check, not data. Symbols, bulk files and delisted history were not tested. |

## 1. AFM register of managers' transactions

**Result: partly.**

* **The date filter does not apply to the export.** The export links are `https://www.afm.nl/export.aspx?type=0ee836dc-5520-459d-bcf4-a4a689de6614&format=csv` (or `format=xml`). Adding `date-from` and `date-till` made no difference: the export always holds the whole register, 9,607 notifications from 31 December 2005 onward. That is 0.7 MB as CSV and 4.9 MB as XML, small enough to fetch whole once a day. The footer line says "Datum laatste update 18 Nov 2026". Of the 9,607 notifications, 20 have a transaction date from 11 November onward.
* **CSV columns:** `Transactie` (transaction date, with no time), `Uitgevende instelling` (issuer), `Meldingsplichtige` (person), `MeldingsPlichtigeAchternaam` (surname). The file is semicolon-separated and Latin-1 encoded.
* **XML fields:** `meldingid`, `transactiedatum`, `uitgevendeinstelling`, `meldingsplichtige`, `meldingsplichtigeachternaam`, `nauwgelieerdaan` (closely associated with), `functie` (role), `lei`. That is more than the CSV has.
* **Neither export has a publication time, a transaction type, a price or a volume.** Each notice's detail page (`.../details?id=<meldingid>`) has them: instrument type, ISIN, transaction category and type (for example "Vervreemding" / "Verkoop", disposal / sale), stock option programme, trading place, price, quantity and currency. The detail page shows no publication time either. The first 8 digits of `meldingid` look like a date (YYYYMMDD), but that is a guess.
* **Newest entry:** transaction date 13 November 2026, 5 days before today (18 November). It is unclear how much of that gap is the 3 business days managers have to report, and how much is AFM processing time. The intake should log when each new `meldingid` is first seen.

## 2. AMF BDIF

**Result: blocked.**

* `https://bdif.amf-france.org/fr` loaded (HTTP 200, title "AMF : Base des décisions et informations financières (BDIF)"). It is a JavaScript application, so the HTML holds no search results.
* `https://bdif.amf-france.org/fr/abonnements-flux-rss` returned HTTP 500 with a firewall page: "The URL you requested has been blocked … Web Page Blocked! The page cannot be displayed. Please contact the administrator for additional information."
* Following the rules, I stopped there. I didn't fetch the RSS feed and didn't look for its address some other way. The search was not tested.
* It is unknown whether the block is about location, the User-Agent, or automated clients in general. A next step would be to open the page in a normal browser on the Spark. If it loads there, the block is about clients, not location.

## 3. EQS news

**Result: partly.**

* **No feed.** No RSS or Atom link appears in the HTML, and `/news/directors-dealings/` returns 404. The only list is the home page news feed. It shows the latest items in the HTML, and Directors' Dealings is one of its filter categories (`DIRECTORS_DEALINGS`, id 2). Each list item has the time, category, company, headline and a stable link: `/news/directors-dealings/<slug>/<uuid>_en`.
* **Fields on one item page** (Zalando SE, 18 November 2026, 16:00 CET):
  * category, date and time
  * company, ISIN and country
  * the person's name and position, and who they are closely associated with
  * initial notification or amendment
  * the issuer's name and LEI
  * instrument type and ISIN
  * nature of the transaction (for example "Acquisition")
  * a table of price(s) and volume(s), here many partial fills
* **robots.txt** blocks a long list of AI and scraper bots completely. For all other agents it allows `/` except `/search/`, `/wp-json/` and the admin paths.
* **Terms** ([Legal notice](https://www.eqs-news.com/legal-notice/)):
  > "They are intended for personal use only and may not be copied, either for trading purposes or for transfer to third parties, nor modified and used on other websites."

  > "News agency content is merely for editorial purposes and user's individual information. The storage in databases and any forwarding to third parties as part of or for the purposes of commercial use is only permitted with written consent by EQS Group."

  > "EQS Group does not permit the use or downloading of content from this website by third parties for the development, training or operation of artificial intelligence or other machine learning systems ("text and data mining") without the express written consent of EQS Group."
* Reading for personal information seems to fit. Storing items in a database for a commercial product, or running them through AI, needs written consent from EQS.

## 4. Euronext company press releases

**Result: partly.**

* **No rows in the page HTML.** `https://live.euronext.com/en/listview/company-press-releases/404/Persberichten` returns the page with its filters (trading location, market, industry, topic, provider, date) and the text "no results match your search criteria". The rows come from a separate request.
* **The view behind it:** `company_press_releases_view`, display `page_3`, arguments `404/Persberichten`, served through `https://live.euronext.com/en/views/ajax`. A plain GET to that address with those parameters returned the filter block with "no results match your search criteria". The real request probably needs the page's form state (most likely a POST), and I didn't go further.
* **Bot challenge on a second page.** `https://live.euronext.com/en/products/equities/company-news` returned HTTP 202 with an empty body, which is typical of a bot challenge. I stopped requesting live.euronext.com there.
* **Terms** ([Euronext terms of use](https://www.euronext.com/en/terms-use)):
  > "you will not sell, license, rent, modify, print, copy, reproduce, download, upload, transmit, distribute, disseminate, publicly display, publicly perform, publish, edit, adapt, compile or create derivative works from any Content or materials (including, without limitation, through framing or systematic retrieval to create collections, compilations, databases or directories) or otherwise transfer any of the Content to any third person"

  > "You may print or download a single, unaltered, permanent copy or one temporary copy in a single computer's memory of any Content for your personal, non-commercial use only"

  > "Euronext prohibits caching, unauthorised hypertext links by others to the Euronext Website and the framing of any Content available on its Euronext Website."
* Automated collection into a database needs written permission from Euronext. Euronext can't be the version zero intake for NL and FR announcements without asking first.

## 5. Ticker API

**Result: works (docs and terms only; no key used).**

* **Free tier:** 15-minute delay ("Free and Lite: 15-minute delay"), 7 days of history, 1 request a second with a burst of 2, and a weekly quota of 350 requests. Going over either limit returns 429. Per the [rate limits page](https://developers.ticker.app/docs/core-concepts/rate-limits): "Per request, not per result. A single response containing 200 items counts as one request."
* **350 requests a week** is about one poll every 29 minutes, around the clock. Polling only during London trading hours (8:00 to 16:30 on weekdays, about 42.5 hours a week) allows about one poll every 7 minutes. The next plan up, Lite (£29 a month), has a 30-day history and 1,500 requests a week.
* **Terms** ([Terms of Service, 3 June 2026](https://developers.ticker.app/terms), section 6):
  > "Individual subscription plans are licensed for your personal use only: your own investment research, analysis, and management of your own portfolio."

  > "You may use the data and any outputs you compute from it for your own personal analysis. That includes running queries against your own archive, backtesting your own strategies, generating alerts for your own portfolio, and displaying it in tools you use yourself and that no other person has access to."

  Among the things you must not do:
  > "Display data to any third party, or on any website, application, dashboard, feed, channel, or service, whether public, private, internal, or behind authentication"
* [Pricing](https://developers.ticker.app/pricing):
  > "Any commercial application, product integration, or using the data in a professional capacity requires a Professional plan."
* **Fit:** a personal app that only you use fits the free tier. As soon as anyone else sees the data or its signals (a second user, a Telegram channel, a product), you need a Professional plan.

## 6. FinancialReports / FinancialFilings

**Result: needs a key.**

* **Free allowance:** "Every account gets 500 free credits a month, no card required", at 120 requests a minute. Per the [pricing page](https://financialfilings.com/pricing/): "Search 1 · Markdown 6 · Premium markdown 12 · Financials 40 credits per call". After that, 1 credit is $0.01, and with a card on file the limit is 50 requests a second. 500 credits buys about 500 search or list calls a month, about 16 a day.
* **Director dealings are a filing type:** "Director's Dealing: Report of personal share transactions by company directors and executives (insider trades)" ([filing types](https://financialfilings.com/filings/filing-types/)). List calls can be filtered by country (`countries=DE`), ISIN or LEI.
* **Coverage** ([coverage](https://financialfilings.com/coverage/)) lists all four countries:

  | Country | From | Filings | Companies |
  | --- | --- | --- | --- |
  | Netherlands | 2005 | 73,586 | 646 |
  | Germany | 1997 | 304,526 | 1,469 |
  | France | 2006 | 341,727 | 742 |
  | United Kingdom | 2010 | 1,523,356 | 2,788 |

  The page doesn't say whether director dealings are covered in each of these markets. One filtered call per country with a free key would show it.
* **Terms** ([API terms](https://financialfilings.com/api-terms/)): the licence covers "your personal use or your own organisation's internal business purposes". You must not:
  > "publicly display the Data — for example on a website, in an app, or in a product screen visible to people outside your organisation"

  The terms also say:
  > "Pull-only. Bulk delivery and redistribution are Enterprise."

  Since 27 October 2026 the terms also prohibit "systematic extraction of all or a substantial part of the Data". Sign-up is one POST with an email address. I didn't sign up.

## 7. GDELT DOC 2.0 API

**Result: partly.**

* **Query:** `(shares OR earnings OR CEO) sourcecountry:XX`, `mode=artlist`, `timespan=24h`, `maxrecords=250`, using GDELT's FIPS country codes: NL, GM, FR and UK.
* **Netherlands (NL):** 0 articles. The English keywords probably miss Dutch-language sources. A Dutch query would need words like `aandelen` or `winst`.
* **United Kingdom (UK):** 11 articles, all the same syndicated story on 11 local news sites ("Nvidia chairman says board does not intend to reinstate Jensen Huang", 18 November 2026 01:15 UTC). There was only one distinct title, so I can't give 3 samples.
* **Germany (GM) and France (FR):** HTTP 429: "Please limit requests to one every 5 seconds". My requests were 3.5 seconds apart. That's my mistake; GDELT's own limit is 5 seconds. I stopped as the rules say and didn't retry.
* **Takeaway:** keyword queries by country return very little. A rerun should space requests 6 seconds or more apart, use local-language words per market, and try `mode=timelinevolraw` to count volume instead of listing articles.

## 8. Stooq

**Result: blocked.**

* `https://stooq.com/q/d/l/?s=sap.de&i=d` and `https://stooq.com/q/d/l/?s=ulvr.uk&i=d` both returned a short HTML page instead of a CSV: "This site requires JavaScript to verify your browser. Please enable JavaScript and reload."
* That is a browser challenge, so I stopped as the rules say. Not tested: the symbol formats for ASML and TotalEnergies, the bulk pages at `https://stooq.com/db/h/`, and a delisted stock such as Intertrust.
* Automated downloads from Stooq can't be relied on from here, whatever its coverage. For version zero, a manual bulk download in a browser may still work. Otherwise the planned paid fallback (EODHD) becomes the main option sooner.

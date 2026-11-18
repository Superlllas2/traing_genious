# Data sources for version zero

As of 18 November 2026. Markets: Netherlands, Germany, France, United Kingdom.

Director dealings and company announcements can be read for free from official or near official sources in all four markets. The one exception is fast UK news: the London Stock Exchange's news service (RNS) is licensed. Version zero costs about $20 a month, for price data only.

## Pick per item

| Item | Version zero pick | Cost | Why | Later |
| --- | --- | --- | --- | --- |
| Director dealings, NL | AFM register, CSV or XML export | Free | Official, complete, machine readable, history from 2005 | Same |
| Director dealings, DE | EQS news, "EQS-DD" items | Free to read | Most German issuers publish through EQS, within minutes, with ISIN, price, volume and venue | FinancialReports API |
| Director dealings, FR | AMF BDIF, "Déclarations des dirigeants" RSS feed | Free | Official, in French and English since August 2026 | Same |
| Director dealings, UK | Ticker API, free tier | Free | Licensed RNS redistributor; free tier has a 15 minute delay and 7 days of history | Ticker paid plan, or FinancialReports API |
| Announcements, NL and FR | Euronext company press releases page | Free to read | One list for Amsterdam and Paris, all distributors, minute timestamps, topic tags | Same |
| Announcements, FR (regulated documents) | info-financière API | Free, 10,000 calls a day | Official French storage of regulated information | Same |
| Announcements, DE | EQS news | Free to read | The main channel for German ad hoc and corporate news | Same |
| Announcements, UK | Ticker API (RNS) | Free tier | See UK director dealings | Same |
| General news | GDELT DOC 2.0 API | Free, no key | Updated every 15 minutes, 65 languages, news volume over time | Marketaux or EODHD news, if GDELT misses too much |
| Daily prices | EODHD, EOD Historical Data All World | $19.99 a month | 60+ exchanges, 30+ years, delisted stocks, splits, dividends, bulk download | Same |
| Company size | Index membership (AEX, AMX, AScX, DAX, MDAX, SDAX, CAC 40, SBF 120, FTSE 100, FTSE 250) | Free | Good enough for large, mid and small labels | Market value from EODHD Fundamentals, $59.99 a month |
| Instrument reference (ISIN, exchange, LEI) | ESMA FIRDS files, FCA FIRDS for the UK | Free | Official, full weekly files and daily changes | Same |

Stooq is a free fallback for daily prices while testing. It has a daily request limit and bulk ZIP downloads, but fewer European exchanges.

## Notes per market

**Netherlands.** The AFM register of managers' transactions has a date filter, a search box, and a CSV and XML export of the results ([AFM register](https://afm.nl/en/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-)). It listed 9,607 notifications on 18 November 2026. Third party trackers report history from October 2005.

**Germany.** Do not use BaFin's own database as the live source. BaFin says entries can take several days or weeks, they stay listed for 12 months only, and the primary storage is the company register ([BaFin](https://www.bafin.de/ref/19590874)). Issuers publish through distribution services, and EQS is the main one: its "EQS-DD" notices carry the person, role, ISIN, price, volume, date and venue (example: [DEUTZ AG](https://www.investegate.co.uk/announcement/eqs/deutz-ag--0e4k/eqs-dd-deutz-ag-oliver-neu-buy/9216927)). Since 1 January 2026, German managers only report once their yearly total passes €50,000, up from €20,000 ([Heuking](https://www.heuking.de/en/news-events/newsletter-articles/detail/listing-act-simplification-of-directors-dealings-bafin-raises-threshold-for-notifications-of-transactions.html)). Small purchases no longer show up in Germany.

**France.** BDIF offers free subscriptions and RSS feeds per topic, one of them for "Déclarations des dirigeants" ([AMF](https://www.amf-france.org/fr/actualites-publications/actualites/bdif-fait-peau-neuve-pour-mieux-repondre-vos-attentes)). Since August 2026 the AMF publishes these notices in French and English ([AMF](https://www.amf-france.org/fr/actualites-publications/actualites/lamf-publie-desormais-les-declarations-des-dirigeants-en-francais-et-en-anglais)). The info-financière API gives regulated documents such as annual reports, buyback reports and voting rights, but not director dealings ([data.gouv.fr](https://www.data.gouv.fr/dataservices/api-info-financiere)). One third party scraper says BDIF blocks requests from outside France; this needs a test from the Spark.

**United Kingdom.** RNS carries over 75% of regulatory UK announcements ([LSEG](https://www.lseg.com/en/capital-markets/regulatory-news-service)). Real time RNS is not available on the London Stock Exchange website for professional users. Redistributing it costs £26,000 a year for real time and £17,000 for delayed information, while historical information is free ([RNS pricing 2026](https://www.lseg.com/content/dam/lseg/en_us/documents/rns/rns-pricing-and-policy-guidelines-2026.pdf)). The Ticker API is an authorised RNS redistributor with a free tier: 15 minute delay, 7 days of history, personal licence ([Ticker FAQ](https://developers.ticker.app/docs/reference/faqs)). The FCA's National Storage Mechanism is free and exports search results as CSV, but it is not real time and has no API yet ([FCA](https://www.fca.org.uk/markets/primary-markets/regulatory-disclosures/national-storage-mechanism)). Investegate is convenient but its terms allow private, non commercial use only and forbid passing anything on ([Investegate](https://www.investegate.co.uk/help)).

**Euronext.** The company press releases page lists every release for Amsterdam and Paris issuers with the time to the minute, the distributor (EQS, GlobeNewswire, Business Wire, Les Echos and others) and a topic, including "Mandatory notification of trade primary insiders" and "Major shareholding notifications" ([Euronext](https://live.euronext.com/en/listview/company-press-releases/404/Persberichten)).

## One paid option that covers everything

FinancialReports (now also called FinancialFilings) collects filings from regulators across Europe into one API, including MAR Article 19 director dealings. It claims processing within about 5 minutes and coverage of about 97% of the STOXX Europe 600 ([FinancialFilings](https://financialfilings.com/for/hedge-funds/)). There is a free API allowance; larger plans are priced on request. These are the vendor's own claims. It is worth a trial before building four separate readers, and it is the obvious upgrade if one of the free sources breaks.

## Coming later: one EU access point

ESMA's European Single Access Point opens to the public by July 2027. Market abuse disclosures, which include director dealings, join in phase 2 from January 2028 ([Regnology](https://www.regnology.net/en/resources/regulatory-topics/european-single-access-point-esap/)). From then on one source could replace the national ones for the EU markets. The UK is outside it.

## Rules the intake must follow

* **Two timestamps per item.** The time the source says it was published, and the time we first saw it. The log uses the second one, so results never use information before we had it.
* **Keep the source link.** Every fact in the app points to its original notice.
* **Read, do not republish.** The free sources allow reading. A public Telegram channel or a paid product that reposts announcement text needs a licence check per source first. For the UK this is certain: RNS redistribution is licensed.
* **Respect limits.** Poll each source at a polite interval, identify the app in the request, and stop on errors.

## Open checks, to run from the Spark

- [ ] AFM export: which fields the CSV holds (time, type, price, volume) and how fast new notices appear
- [ ] BDIF: does the RSS feed and search work from a Dutch IP address
- [ ] EQS: is there an RSS feed or a stable list page for EQS-DD items, and what do its terms allow
- [ ] Euronext: terms of use for automated reading of the press release list
- [ ] Ticker API: confirm the free tier terms fit a personal app
- [ ] FinancialReports: ask for a trial key and the price for four markets
- [ ] GDELT: how many items a day mention companies from the four markets

## Monthly cost

| Phase | Items | Cost |
| --- | --- | --- |
| Version zero | EODHD EOD Historical Data | $19.99 |
| With market values | EODHD Fundamentals instead | $59.99 |
| Possible upgrades | FinancialReports API, Ticker paid plan, a paid news feed | On request or plan based |

## Sources

* [AFM register of managers' transactions](https://afm.nl/en/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-)
* [BaFin notes on the managers' transactions database](https://www.bafin.de/ref/19590874)
* [Heuking: BaFin raises the threshold to €50,000](https://www.heuking.de/en/news-events/newsletter-articles/detail/listing-act-simplification-of-directors-dealings-bafin-raises-threshold-for-notifications-of-transactions.html)
* [AMF: BDIF subscriptions and RSS feeds](https://www.amf-france.org/fr/actualites-publications/actualites/bdif-fait-peau-neuve-pour-mieux-repondre-vos-attentes)
* [AMF: director dealings in French and English](https://www.amf-france.org/fr/actualites-publications/actualites/lamf-publie-desormais-les-declarations-des-dirigeants-en-francais-et-en-anglais)
* [data.gouv.fr: API info-financière](https://www.data.gouv.fr/dataservices/api-info-financiere)
* [FCA: National Storage Mechanism](https://www.fca.org.uk/markets/primary-markets/regulatory-disclosures/national-storage-mechanism)
* [LSEG: RNS](https://www.lseg.com/en/capital-markets/regulatory-news-service)
* [LSEG: RNS pricing and policy 2026](https://www.lseg.com/content/dam/lseg/en_us/documents/rns/rns-pricing-and-policy-guidelines-2026.pdf)
* [Ticker API FAQ](https://developers.ticker.app/docs/reference/faqs)
* [Investegate help and terms](https://www.investegate.co.uk/help)
* [Euronext company press releases](https://live.euronext.com/en/listview/company-press-releases/404/Persberichten)
* [FinancialFilings for hedge funds](https://financialfilings.com/for/hedge-funds/)
* [GDELT DOC 2.0 API announcement](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
* [EODHD pricing](https://eodhd.com/pricing)
* [ESMA FIRDS, Wikipedia overview](https://en.wikipedia.org/wiki/Financial_Instruments_Reference_Database_System)
* [Regnology: ESAP timeline](https://www.regnology.net/en/resources/regulatory-topics/european-single-access-point-esap/)

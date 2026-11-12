# Research library

Text results of the paper research runs. The app reads its evidence from here.

* `v1/`: the library frozen on 28 October 2026 (1,180 method cards, 378 papers). Never edited after import.
* `v2/`: research round 3, when it runs. It never changes `v1`.

What is in git: method cards, chapters, summary, paper list, final check, settings and other text files.

What is not in git: the database and its backups, and the PDFs. They stay on the Spark, with one backup copy elsewhere. The paper list holds a link for every paper.

To import a frozen library folder on the machine that holds it:

```
scripts/import_research.sh /path/to/library_final_2026-10-28 v1
```

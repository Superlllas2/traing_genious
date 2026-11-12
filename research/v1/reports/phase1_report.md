# Phase 1 done

375 papers chosen for reading. 258 still need a full text: they are in wanted.csv and zotero_import.ris, anchors first.

## What the machine sources found

* no full text: 258
* full text (OpenAlex repository): 53
* full text (Unpaywall repository): 34
* full text (CORE): 22
* full text (arXiv): 8

Next: run fetch_entitled.py at Saxion on wanted.csv (the whole list) and copy its folder to pdfs/. Then python3 researcher.py zotero-list writes zotero_import.ris with the top 100 papers still missing. After Zotero, copy its export to pdfs/ too, then: python3 researcher.py run --phase 2

# Macro-benchmark

Sixty real Python packages at pinned releases, each with a hand-written call
graph of its source: the ground truth. The micro-benchmark shows which
language feature a tool gets wrong; this set shows how a tool does on real
code, where the features mix and most calls cross modules and classes.

A ground truth is written as a call-site ledger: one entry per place in the
source that can call a function, with the callees of that site. A naive list
of candidate callees by name, for every site, protects the ledger against
missed edges by construction. Where a package's own test suite runs, a trace
of the calls it makes checks the ground truth further. A trace is a lower
bound: every traced call of the package must be in the ground truth, which
also has the calls that no test makes.

The rules by which a ground truth is written, audited and extended, and a
batch is drawn, are in [benchmark-rules.md](../benchmark-rules.md).

## How it was built

The packages came in batches. Batches 1 and 2 were chosen by hand; five
packages of PyCG's ICSE 2021 evaluation were added between batches 3 and 4.
Batches 3 to 8 were drawn by a seeded draw, stratified by size, from a frame
of PyPI's most downloaded packages that passed quality filters and was then
frozen. Batches 1 to 5 have five packages each, batches 6 to 8 ten.

Each batch after the first was measured once by a frozen engine before
anyone read its false positives and false negatives. Batches 2 to 6 then
became development batches: their errors were read and the analysis was
improved on them. Batches 7 and 8 are held out. The procedure stopped when
two held-out batches in a row came within 10 points of precision and of
recall of the development set.

## Held-out evidence

Edges inside the package, each batch measured once by the engine at commit
`2372b60`:

| Set | Projects | Precision | Recall | TP / FP / FN | Against development |
|---|---|---|---|---|---|
| Development: batches 1 to 6, ICSE 2021 | 40 | 0.9297 | 0.8782 | 12180 / 921 / 1690 | |
| Batch 7, measured 2026-11-23 | 10 | 0.9268 | 0.8301 | 1950 / 154 / 399 | -0.3 / -4.8 points |
| Batch 8, measured 2026-11-24 | 10 | 0.8590 | 0.8463 | 3101 / 509 / 563 | -7.1 / -3.2 points |

Both held-out batches are within 10 points of development, so the stop
rule is met. The 10-point threshold was set after these measurements;
batches 3 and 4 would also have passed under it.

## How a ground truth is checked

1. A writer builds the ledger from the source and the trace, deciding every
   candidate of every site.
2. Another agent audits it blind: it re-derives a sample of sites without
   seeing the writer's decisions, and the writer applies or answers each
   finding.
3. A referee, a model of another provider, rules on disputes and on
   questions that decide many edges.
4. Audit rounds over the whole set repeat until a round finds at most 100
   missed and 20 false edges.

The 60 ground truths hold 42,377 edges.

## Projects

| Project | Release | Licence | Batch |
|---|---|---|---|
| jmespath | 1.1.0 | MIT | 1 |
| tenacity | 9.2.1 | Apache-2.0 | 1 |
| cachetools | v8.0.0 | MIT | 1 |
| pluggy | 1.7.0 | MIT | 1 |
| h11 | v0.16.0 | MIT | 1 |
| marshmallow | 4.4.0 | MIT | 2 |
| asyncstdlib | v3.14.0 | MIT | 2 |
| configargparse | v1.9.0 | MIT | 2 |
| sqlparse | 0.6.1 | BSD-3-Clause | 2 |
| anytree | 2.13.0 | Apache-2.0 | 2 |
| aiocache | v0.12.3 | BSD-3-Clause | 3 |
| argcomplete | v3.7.2 | Apache-2.0 | 3 |
| pypinyin | v0.55.0 | MIT | 3 |
| markdown2 | 2.5.5 | MIT | 3 |
| netaddr | 1.3.0 | BSD-3-Clause | 3 |
| autojump | release-v22.5.3 | GPL-3.0-or-later | ICSE 2021 |
| fabric | commit 34edfe4a1c | BSD-2-Clause | ICSE 2021 |
| asciinema | commit 350d5e9d8b | GPL-3.0-or-later | ICSE 2021 |
| face_classification | commit 2f152a227c | MIT | ICSE 2021 |
| Sublist3r | commit 3f5fc6da01 | GPL-2.0-only | ICSE 2021 |
| dagster-pipes | 1.13.28 (sdist) | Apache-2.0 | 4 |
| fastjsonschema | v2.22.3 | BSD-3-Clause | 4 |
| pyflakes | 4.1.0 | MIT | 4 |
| bottle | 0.13.4 | MIT | 4 |
| itables | v2.9.1 | MIT | 4 |
| whitenoise | 6.12.0 | MIT | 5 |
| funcy | 2.1 | BSD-3-Clause | 5 |
| python-barcode | 0.16.1 (sdist) | MIT | 5 |
| pyrate-limiter | v4.5.1 | MIT | 5 |
| structlog | 26.1.0 | MIT OR Apache-2.0 | 5 |
| path | v17.1.1 | MIT | 6 |
| django-constance | 4.5.0 | BSD-3-Clause | 6 |
| tinytag | 2.3.2 | MIT | 6 |
| jsonpickle | v4.1.4 | BSD-3-Clause | 6 |
| json-repair | v0.64.2 | MIT | 6 |
| django-environ | v0.14.0 | MIT | 6 |
| validators | 0.36.0 | MIT | 6 |
| tabulate | v0.10.0 | MIT | 6 |
| more-itertools | v11.2.1 | MIT | 6 |
| prometheus-client | v0.26.0 | Apache-2.0 AND BSD-2-Clause | 6 |
| pyfiglet | 1.0.4 (sdist) | MIT | 7 |
| uncertainties | 3.2.3 (sdist) | BSD-3-Clause | 7 |
| einops | v0.8.2 | MIT | 7 |
| pymysql | v1.2.3 | MIT | 7 |
| segno | 1.6.6 | BSD-3-Clause | 7 |
| tinydb | v4.9.0 | MIT | 7 |
| pgvector | v0.5.1 | MIT | 7 |
| textdistance | 4.6.3 | MIT | 7 |
| websocket-client | v1.9.2 | Apache-2.0 | 7 |
| mss | v10.2.0 | MIT | 7 |
| honcho | v2.0.0 | MIT | 8 |
| nodeenv | 1.12.0 | BSD-3-Clause | 8 |
| flit-core | 4.2.0 | BSD-3-Clause | 8 |
| pyusb | v1.3.1 | BSD-3-Clause | 8 |
| vulture | v2.16 | MIT | 8 |
| toolz | 1.2.0 | BSD-3-Clause | 8 |
| tablib | v3.10.0 | MIT | 8 |
| avro | 1.12.2 (sdist) | Apache-2.0 | 8 |
| pubchempy | v1.0.5 | MIT | 8 |
| m3u8 | 6.0.0 | MIT | 8 |

A release is the tag of the pinned commit, or the version of the source
archive from PyPI where a project is pinned as an sdist; three projects of
the ICSE 2021 set are pinned at a commit without a release.

## Results

[evaluation/README.md](../README.md) gives PyCG's precision and recall on
the 60 packages, inside and outside the package.

## Records

`selection/` holds the data of the draw (the list, the frame, the
exclusions and the log of each round), and the rulings and audits of
batch 8 and of the corrections of 2026-11-25. Each ground truth's blind
audit and judgements are beside it in `ground-truth/`.

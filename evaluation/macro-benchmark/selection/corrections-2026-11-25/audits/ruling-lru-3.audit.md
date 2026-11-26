# Audit of the application of ruling-lru-3 (2026-11-25)

Branch `vitsalis/gt-lru-cache-wrapper` (9ea197c, PR #114) against `main`
(459eb33). The ruling (`../rulings/ruling-lru-3.md`) is byte-identical to
the copy that the lead adopted. I compared the ledgers, graphs and
rejected-edge files of both commits with a script that parses each ledger
into its sites and callees, read the traces (`dynamic/*.json`), and ran
`check.py` on the 13 packages with their sources from the inputs image.
Nothing ran of the packages; no PyCG output was read.

## The 40 sites

At 459eb33 the callee `functools._lru_cache_wrapper.__call__` appears in
exactly 13 ledgers, at 40 sites: configargparse 2, django-constance 1,
einops 10, fastjsonschema 2, flit-core 1, itables 1, m3u8 3, markdown2 2,
more-itertools 1, nodeenv 1, pyflakes 2, tablib 2, validators 12. At
9ea197c every one of these 40 sites, and no other site of the 13 ledgers,
changes, and each changes in exactly one callee: it loses
`functools._lru_cache_wrapper.__call__` and gains
`_functools._lru_cache_wrapper.__call__`. The 40 sites (caller and
`line:column`) are those of the ruling's table, row for row. No ground
truth of the benchmark keeps the old name in a ledger, graph or added-edge
file.

The graphs agree: in each of the 13 `.json` files the only removed pairs
are `caller -> functools._lru_cache_wrapper.__call__` and the only added
pairs are the same callers to `_functools._lru_cache_wrapper.__call__`,
36 in all (three callers with several sites share their pairs:
m3u8's `absolute_uri`, validators' `_port_validator` and
`_validate_auth_segment`); the node sets are unchanged. The seven
`functools._lru_cache_wrapper.wrapper` edges (configargparse 2,
markdown2 2, more-itertools 1, pyflakes 2) and their ledger lines are
unchanged; itables' added-edge file now shows an existing note that
mentions the PyPy closure, because its site is no longer confirmed by the
trace, not a new callee.

## The 33 trace rejections

The traces name the type by its facade qualname. Every trace pair
`caller -> functools._lru_cache_wrapper.__call__` in `dynamic/*.json` is
33 pairs in 11 packages (configargparse 2, einops 9, fastjsonschema 2,
itables 1, m3u8 2, markdown2 2, more-itertools 1, nodeenv 1, pyflakes 2,
tablib 2, validators 9), and the entries added to the `rejected.json`
files are exactly these 33 pairs, each as a naming artefact under rule A
(a new `validators.rejected.json`); no existing rejection is removed or
changed. django-constance's and flit-core's sites are not in their
traces, and einops' `_prepare_recipes_for_all_dims` is not traced, which
is why einops has 10 renamed edges and 9 rejections.

`check.py` on the 13 packages passes, and `--origin` and `--report`
too: for example configargparse 328 traced and 80 added, einops 243 and
1888, validators 385 and 37, tablib 865 and 221, all with unchanged edge
counts.

## The READMEs and the micro graph

- The micro README's "Calls of instances" is the ruling's replacement
  text, word for word (rewrapped).
- The macro README's two fastjsonschema examples (`:823`, `:1936`) take
  the new prefix, as the ruling asks; its new entry under "Rulings for the
  corrections of 2026-11-25" states the ruling's rule, sources, scope and
  limits, and the counts (36 edges, 40 sites, 13 packages, 33 traced pairs
  in 11 packages).
- `mss.md`'s example follows.
- `decorators/functools_cache/callgraph.json` renames the one node and the
  one edge, and nothing else. The ruling itself "makes no decision about
  that graph", but its new README bullet decides the name; the expected
  failure until the engine maps the name is known (the PR waits for
  engine-core).

## Findings

| Id | Finding | Where | Fix |
|---|---|---|---|
| A1 | the Statistics paragraph still says "the trace confirms 867 of 1086 (79.8%) ... 14 rejected"; after the change the trace confirms 865 (79.7%) and 16 are rejected (its origin table, updated, says so) | `tablib.md`, "Statistics" | 865 of 1086 (79.7%); 16 rejected |
| A2 | "28 edges come from reading only" is stale: 37 now (11 inside, 26 outside), since the nine renamed edges are no longer confirmed by the trace | `validators.md`, the opening paragraph | 37 |
| R1 | Remark: the dated "Status (for resuming)" note says "the 3 trace edges that the graph lacks are in `einops.rejected.json`"; there are 12 now. It is a dated status, so a note may suffice | `einops.md:7` | optional |

**Verdict.** The renames, the rejections, the README texts and the micro
graph match the ruling exactly, and nothing is missed. A1 and A2 correct
two stale counts; no edge depends on them.

A1, A2 and R1 were applied (tablib.md, validators.md and einops.md give the
current counts). The audit is closed.

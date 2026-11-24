# anytree: independent audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

Release 2.13.0, commit `2e0a1b956172654d75aff93277ce3d883355e0bf`. Audited
files (not yet committed; SHA-1 of the files as audited):
`anytree.ledger` (`c3e7a94d`, 572 entries, 151 notes), `anytree.json`
(`935c9d03`, 565 edges: 354 in the package, 211 outside), `anytree.md`
(`43487de6`). The ledger already applies the lead's ruling on cross-family
calls (J1). There is no `anytree.rejected.json`. `check.py anytree`: no
errors; the trace confirms 486 edges (all 486 trace edges), 79 come from
reading only.

I judged the files by the scope rules of `macro-benchmark/README.md` (A,
B1-B5, C). I read the source, the docs (`docs/`, `README.rst`) and the tests
as data. I did not run the package and did not use a static analysis tool.

**Final state.** The blind sample found no disagreement. The exhaustive
checks found no missing edge and no edge that cannot happen. There are 2
low findings (A1, A2), 1 remark (R1), and 3 questions for the lead (Q1-Q3).
None of them changes the graph unless the lead rules against the writer on
Q1 (+7 edges) or Q2 (about +87 edges). I recommend that the lead keeps the
writer's decisions.

## Findings

| Id | Kind | Site | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| A1 | low: wrong note | `abstractiter.py` 27:26 `self._iter(...)` | The note says "all but PostOrderIter._iter are generator functions". `AbstractIter._iter` (`abstractiter.py:47-49`) only raises `NotImplementedError`; it is no generator function either. The callees are right. | 0 | certain |
| A2 | low: incomplete reason (J3, ledger header) | `symlinknodemixin.py:52, 58`, `symlinknode.py:53`; J1 last paragraph | J3 restricts the target of a `SymlinkNode` to the `NodeMixin` family because "the docs call it another tree node" (`symlinknode.py:10`). But the md's own value set "Nodes" says that a parameter that takes a tree node gets a node of either family. So that reason alone admits a `LightNodeMixin` target. The reason that holds is the lead's ruling (no `isinstance` check admits a light node for this role), together with `SymlinkNode.__init__`, which reads `self.target.__dict__` (`symlinknode.py:47`): the documented light node class uses `__slots__` (`lightnodemixin.py:26-29`) and has no `__dict__`. J3 should say this. The restriction matters: with a light target, `LightNodeMixin.__attach` succeeds through the link (Q1). | 0 (Q1: +7) | likely |
| R1 | remark: reason wording | default rejection of `SymlinkNodeMixin.__getattr__` | Python also calls `__getattr__` when a property getter raises `AttributeError`. The reason names "normal lookup finds the attribute". I checked every `NodeMixin` property on a `SymlinkNode` receiver: `parent` and `__children_or_empty` guard with `hasattr` (`nodemixin.py:116, 125, 171`), and no other getter raises `AttributeError`. So the default holds; one clause in the reason would make that visible. | 0 | certain |

## Questions for the lead

- **Q1. Can the target of a `SymlinkNode` be a `LightNodeMixin` node?**
  The README does not decide it. Nearest rule: the lead's J1 ruling (the
  families mix only where an `isinstance` check admits the other one) says
  no, and I recommend no (A2). If the lead says yes: in
  `LightNodeMixin.__attach`, `parent.__children_or_empty` on a link
  (`lightnodemixin.py:162`) goes through `__getattr__` to the light target,
  whose property returns its child list, so the attach succeeds and a light
  node gets a `SymlinkNode` parent. That adds 7 edges:
  `SymlinkNodeMixin.__getattr__ -> LightNodeMixin.__children_or_empty`
  (`symlinknodemixin.py:52:23`); `LightNodeMixin.__detach ->
  SymlinkNodeMixin.__getattr__` (149:37) and `-> SymlinkNodeMixin.__setattr__`
  (153:20); `LightNodeMixin.iter_path_reverse -> NodeMixin.parent` (323:25);
  `LightNodeMixin.root -> NodeMixin.parent` (386:20, 387:25);
  `LightNodeMixin.ancestors -> NodeMixin.path` (347:28);
  `LightNodeMixin.siblings -> NodeMixin.children` (413:46).
- **Q2. J4: a client attribute name that names a node property.** At
  `render.py:344`, `resolver.py:349` and `search.py:234`, `getattr(node, name)`
  would run a property if the client passed a property name (`"depth"`).
  The writer does not consider it. The README does not decide it; the
  nearest rule is B3 (a value that the package never produces for the
  role): the default is `"name"`, and the docs and tests pass only data
  attributes (`name`, `lines`, `id`, `foo`; `docs/tricks/readonly.rst:45`
  uses a client attribute). I agree. The other reading adds the 15
  `NodeMixin` and 14 `LightNodeMixin` properties at each of the three sites:
  about 87 edges.
- **Q3. J5: the name of what `fastcache.clru_cache(32)` returns** at the
  four `@_cache(CACHE_SIZE)` decorator sites. The writer uses the stub rule
  (`fastcache.clru_cache`). The edge `anytree.cachedsearch ->
  fastcache.clru_cache` exists anyway from the call sites, so the graph does
  not depend on the name. I agree.

## Step 1: blind re-derivation

I made the skeleton without the ledger: a scratch benchmark directory with a
copy of `projects.toml` and a `projects` link, then `check.py --skeleton
anytree` (1083 sites, 35 value sites, no defaults). I numbered the sites from
0 in skeleton order and drew `random.Random(20261111).sample(range(1083),
70)`, then added every value site: 103 sites (2 random sites are value
sites). I wrote the callees of each site from the source before I opened any
writer file (scratch file `blind-answers.md`).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random, not value sites (36 getattr, 8 setattr, 13 call, 4 decorator, 4 iter, 3 format) | 68 | 68 | 0 |
| Value sites (35, of which 2 random) | 35 | 35 | 0 |
| **Total** | **103** | **103** | **0** |

One naming point, not a disagreement: at `render.py:287:23` and `293:19`
(`Row(...)`, a class that `collections.namedtuple` makes) I left the outside
callee open between "no edge" and `anytree.render.Row`. The writer chose no
edge, as cachetools' `CacheInfo`; the trace has no `Row` callee. I agree.

## Step 2: dispatch sets and value roles

| Role or site | Values (evidence) | Ledger |
|---|---|---|
| `self._iter(...)` `abstractiter.py:27` | `AbstractIter` (public, concrete) and the five iterators | 6 `_iter`, agree |
| hooks `self._pre_*`/`_post_*` (16 sites) | no package subclass overrides one | own family's hook, agree |
| `parent`/`children` property sites (59) | node parameters of public functions: both families; inside a family method: own family (J1) | agree at every site |
| `child.parent = ...` `nodemixin.py:251, 265`, `lightnodemixin.py:250, 264` | 251: NodeMixin family, SymlinkNode (`__setattr__`), light child admitted by `isinstance` (`:230`); others own family | agree |
| `filter_` (7 value sites) | `__default_filter`; PreOrderIter also 6 package filters (`dotexporter.py:236, 244`, `mermaidexporter.py:192, 198`, `nodemixin.py:443`, `lightnodemixin.py:431`, `search.py:113, 212`) | agree |
| `stop` (`preorderiter.py:44`, `abstractiter.py:57`, `mermaidexporter.py:201`) | `__default_stop`, `MermaidExporter.__iter__.<lambda2>` | agree |
| exporter callables (11 value sites) | the client's, or `self._default_*` (DotExporter/RenderTreeGraph: DotExporter's; UniqueDotExporter: its two overrides) | agree |
| `style()` `render.py:265` | the four style classes (`render.py:134`, `tests/test_render.py:46`); not `AbstractStyle` (binding fails) | agree |
| `self.nodecls(...)` `dictimporter.py:46` | `AnyNode` (default), `Node` (`tests/test_dictimporter.py:44`) | agree |
| `cmp_` `resolver.py:226` | `__cmp` (from `get`), `__match` (from `glob`) | agree |
| `func(*args, **kwargs)` `cachedsearch.py:21` | the four decorated functions; `_cache` is private | agree |
| `childiter`, `dictcls`, `attriter`, `attrname` | `list`, `dict`, `DictExporter.export.<lambda1>`; `attrname`: client only | agree |
| `dictexporter.export`, `dictimporter.import_` | documented as `DictExporter`/`DictImporter` | agree |

**J1 (the lead's ruling) re-derived.** Only two `isinstance` checks admit
the other family: `nodemixin.py:122` (value of `NodeMixin.parent`) and
`nodemixin.py:230` (children given to `NodeMixin.children`). I followed both
paths to their failure and found exactly the writer's four edges:
`NodeMixin.__check_loop -> LightNodeMixin.iter_path_reverse`,
`NodeMixin.children -> LightNodeMixin.parent`,
`LightNodeMixin.__check_loop -> NodeMixin.iter_path_reverse`,
`LightNodeMixin.__attach -> SymlinkNodeMixin.__getattr__`. The `%r` of the
loop errors cannot fire across families (a `NodeMixin` node never has a light
ancestor), and a light child given twice runs no package `__repr__`.

## Step 3: default rejections (all sites, `--report anytree --default`)

| Default | Sites | Check |
|---|---|---|
| `SymlinkNodeMixin.__getattr__` | 387 | Every load on a possible `SymlinkNode` receiver: class attributes of `NodeMixin` (properties, methods, `separator`), `__dict__`, `__class__`, and `target` (always set first, B3). No property getter raises `AttributeError` (R1). The names that live in the target (`node.name`, `getattr` with a data name) are the explicit accepts. The light `hasattr` calls have a light receiver. Holds. |
| `SymlinkNodeMixin.__setattr__` | 68 | All 68 assign on iterators, exporters, importers, styles, resolvers, exceptions, `Node`/`AnyNode` self, or light nodes (J1). Holds. |
| `AbstractIter.__iter__`/`__next__`, `RenderTree.__iter__`, both exporter `__iter__` | 116 / 120 / 123 / 123 / 123 | The iterables are lists, tuples, sets, dicts, strs, generators, `*args`, `zip`, `enumerate` objects; `next()` gets `itertools.count` and a list iterator; the 7 sites that iterate a `PreOrderIter` accept the `AbstractIter` methods. Holds. |
| `RenderTree.__repr__`, `__str__`, `AbstractStyle.__repr__` | 74, 63, 74 | No package code formats a `RenderTree`; a style only at `render.py:307` (accepted). Holds. |
| `Node`/`AnyNode`/`SymlinkNode.__repr__` | 68 each | The values are strs, ints, client data (`{value!r}` in `_repr`, `node.name`), non-node client objects (`nodemixin.py:123, 231`) or light nodes (`lightnodemixin.py:140, 143, 236`). The 12 sites that format a `NodeMixin`-family node accept them. Holds. |

## Step 4: the 79 edges from reading only

All are possible: 19 `LightNodeMixin` property edges from public functions
that take a node of either family; 19 node `__repr__` edges (`AnyNode`,
`SymlinkNode`, and `Node` through `str(attr)`, J4); 11 `__getattr__`/
`__setattr__` edges of `SymlinkNode` receivers and targets (J2, J3); 4 J1
edges; 9 edges of `DotExporter.to_picture` (its test is deselected) and 2 of
the deprecated `anchestors`; 9 calls under `if ASSERTIONS:` (`any`, `len`,
`isinstance`, J7); 3 style `__init__` at `style()`;
`AbstractIter.__init -> AbstractIter._iter` (a bare `AbstractIter`);
`SymlinkNodeMixin.__setattr__ -> NodeMixin.children`;
`fastcache.clru_cache` (J5).

## Step 5: other checks

- **Nodes that no edge calls** (71: all 33 modules and 38 functions):
  public API, special methods that only a client triggers, and the 12
  properties `depth`, `descendants`, `is_root`, `leaves`, `siblings`, `size`
  of both families, which no package code loads (search of the source).
  Each keeps the out-edges of its body (rule A).
- **Outside callees** (75 names, 211 edges): each exists and follows the
  rules. Receivers of method edges are package values or B4 types: the
  `__dict__` of package node classes, the `tuple` of `children`, the `str`
  path, the `re` patterns, `codecs.StreamReaderWriter`,
  `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper` (checked in the
  3.15 standard library), `collections.abc.Mapping.get` for `os.environ`.
- **Rejections and notes**: all 179 rejection lines and 151 notes read. Every
  reason holds; one note is wrong (A1).
- **Judgements J1-J7 and items 8-11 of `anytree.md`**: agree; J3 needs the
  reason of A2; J4 and J5 are Q2 and Q3.
- **Rejected trace edges**: none; `check.py` reports no trace edge without a
  site.

## README and tools

- `sites.py` matches names without name mangling. That gives 30 "name
  mangling" rejections and two false value sites (`dotexporter.py:196:27`,
  `mermaidexporter.py:158:27`). Harmless: the candidates are naive by design.
- The README does not say how to name a direct call of a
  `collections.namedtuple` class (`Row(...)`). The cachetools precedent (no
  edge) and the trace agree.


## Round 4 addendum (2026-11-16)

The historical audit above is preserved byte for byte. A fresh source-first
review found R4-F1: an exact package SymlinkNode's inherited property can
raise AttributeError through an opaque client parent/child getter, activating
its package __getattr__ and forwarding to an exact package Node target.
The earlier R1 conclusion that no found getter can fail is too broad.
The current judgements record seven static witness families, their exception
cutoffs and all sites. This adds 18 pairs and 22 site relations, removes none,
and leaves 223 nodes with 581 pairs (369 internal, 212 external).
The review covered every one of the 563 prior pairs, all 1,337 AST sites,
all 229 source bodies including repeated property accessors, all 13 default
candidates and both exclusions. Normal/-O/-OO is a working assumption, not
claimed user approval; the assertion switch already admits disabled checks.
No target or dependency code was executed. Shared verification is run by the
root auditor after handoff; these are semantic findings, not a claim of a
completed structural or origin gate.

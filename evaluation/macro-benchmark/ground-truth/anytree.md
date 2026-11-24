# anytree: judgements of the ground truth

Global-rule audit (2026-11-15): 3 removed edges, 1 added
edge; 563 edges after correction. See the
complete audit (audit record `2026-11-15/README.md`).

Release 2.13.0 (commit `2e0a1b9`). Analysed source: `src/anytree/` (`root =
"src"`): 33 modules, 190 functions (11 lambdas), 35 classes.
`pyproject.toml` sets `requires-python = ">=3.9.2,<4.0"`, so the supported
versions are CPython >=3.9.2,<4.0 (the classifiers stop at 3.13,
which is not an upper bound). This release declares no alternative interpreter
support. Normal, -O and -OO modes form the working configuration union;
this is a working assumption, not claimed user approval. No module has
`from __future__ import annotations`, and the source has no annotations, no
`if TYPE_CHECKING:` block and no branch on the Python version.

The ledger is `anytree.ledger`; the graph `anytree.json` is generated from
it. No trace edge is rejected, so there is no `anytree.rejected.json`.

## Architecture, as the ledger uses it

- **Two node families.** `NodeMixin` (`node/nodemixin.py`) and
  `LightNodeMixin` (`node/lightnodemixin.py`, the same code with
  `__slots__`) keep the tree in name-mangled attributes
  (`_NodeMixin__parent`, `_NodeMixin__children`, and the `_LightNodeMixin__`
  ones). `parent` and `children` are properties with setters (and a
  `children` deleter) that call the hooks `_pre_attach`, `_post_detach`, ...
  `Node`, `AnyNode` and `SymlinkNodeMixin` (with `SymlinkNode`) subclass
  `NodeMixin`. Only `Node`, `AnyNode` and `SymlinkNode` define `__repr__`.
- **Symbolic links.** `SymlinkNodeMixin` (`node/symlinknodemixin.py`)
  defines `__getattr__` and `__setattr__`. Python calls `__getattr__` only
  when normal lookup fails, and calls `__setattr__` for every assignment on
  the instance (see J2).
- **Iterators.** `AbstractIter` (`iterators/abstractiter.py`) is public and
  can be instantiated. `__next__` builds the generator `self._iter(...)` on
  the first call (the private `__init`) and resumes it. Each of the five
  public iterators defines `_iter`; `AbstractIter._iter` raises
  `NotImplementedError`.
- **Exporters.** `DotExporter` (with `UniqueDotExporter` and the legacy
  `dotexport.RenderTreeGraph`) and `MermaidExporter` take callables as
  parameters. `__iter__` replaces each missing callable by a default and
  passes them to private generators.

## Scope rules

`macro-benchmark/README.md` ("Scope rules") states the rules. This section
shows how the ledger applies them.

**A. Edges are per function.** Every function keeps the edges of its body.
`AbstractIter._iter`, `NodeMixin.anchestors` and `DotExporter.to_picture`
never ran in the tests (the trace deselects `test_tree_png`); their edges
are from reading.

**B1. Receivers.** Public methods admit constructible classes and concrete
subclasses that inherit them. Private methods use actual package inputs; an
uncalled private body uses the public-parameter fallback. Failed argument
binding enters no function. A failing initializer retains calls reached in
its body but supplies no completed receiver. Clients do not reinitialize
instances or reuse arbitrary half-changed objects.

- `self._iter(...)` (`abstractiter.py:27:26`): `self` is an `AbstractIter`
  (public and concrete) or one of the five public iterators. All six `_iter`
  are callees.
- In `NodeMixin` methods, `self` is a `NodeMixin`, `Node`, `AnyNode`,
  `SymlinkNodeMixin` or `SymlinkNode` (or a client subclass). No package
  subclass overrides a hook, so each `self._pre_*`/`self._post_*` call has the
  `NodeMixin` hook as callee. The same holds for `LightNodeMixin`.
- `self.__iter(...)` in `DotExporter.__iter__` (`dotexporter.py:196:27`) and
  `MermaidExporter.__iter__` (`mermaidexporter.py:158:27`): name mangling
  makes them two attributes other than the `self.__iter` that `AbstractIter`
  assigns; the callee is the class's own `__iter` method. (The first site
  finder took them for value sites; see "Tools".)

**B2. Arguments and stored values.** Broad `Any`, `object`, `type` and
`Callable` annotations do not admit arbitrary package objects. Client assignment
of a package value to a public attribute requires a documentation or test witness
for that role; public visibility alone does not provide one. This release has
no annotations; its docs, tests and own calls name the package values of a role.
- Tree nodes: see "Value sets" below and J1.
- `DictImporter.nodecls` (`dictimporter.py:46:28`): the default `AnyNode`,
  and `Node`, which the tests pass (`tests/test_dictimporter.py:44`).
  `SymlinkNode.__init__` is excluded.
- `RenderTree(style=...)` (`render.py:265:26`): a style class; the docs pass
  `DoubleStyle` (`render.py:134`). The four subclasses' `__init__` are
  callees. `AbstractStyle.__init__` is excluded: `AbstractStyle()` fails
  when Python binds its three required arguments, before the function runs.
- `childiter` (`render.py:280:42`, `dictexporter.py:68:39`), `dictcls`
  (`dictexporter.py:63:23`), `attriter` (`dictexporter.py:62:31`): the
  defaults `list`, `dict` and the lambda of `dictexporter.py:58`. The docs
  and tests pass only client callables (`reversed`, lambdas).
- `JsonExporter.dictexporter` and `JsonImporter.dictimporter`: the docs name
  `DictExporter` and `DictImporter`, so `dictexporter.export` and
  `dictimporter.import_` call those classes' methods only.

**B3. Not considered.** A non-node value given as parent or child
(`{value!r}` at `nodemixin.py:123`, `{child!r}` at `nodemixin.py:231`) is a
client object. A package object stored as a node attribute (`{value!r}` in
`node/util.py:9`) is an arbitrary package object. A `SymlinkNodeMixin`
instance without `target` (which would make `self.target` recurse through
`__getattr__`) breaks the documented contract ("MUST have a target
attribute").

**B4. Concrete outside types.** Annotations, including shipped stubs, take
precedence over conflicting documentation. This release ships no stubs.
Abstract outside types alone do not identify a concrete implementation.

`Resolver` paths are `str`
(`<builtin>.str.split`, `.startswith`, `.upper`); `children` returns a
`tuple` (`<builtin>.tuple.index` in `util.py`); the private lists and dicts
give `<builtin>.list.append`, `.pop`, `<builtin>.dict.clear`, `.pop`,
`.items`, `.update`.

**B5. Client objects are opaque.** The client's callables (`filter_`,
`stop`, `nodenamefunc`, `attrname`, ...) and the iterable given to
`children` are client code. A client subclass that overrides a hook or
`__repr__` is client code.

**C. Public.** Everything `anytree`, `anytree.exporter`,
`anytree.importer`, `anytree.iterators` and `anytree.node` export is public,
also `anytree.dotexport.RenderTreeGraph` and `anytree.util`. Private:
`_cache`, `_repr`, `_getattr`, `_is_last`, `_format_row_any`, `_findall`,
`_find`, `_filter_by_name` and every name-mangled method.

## Value sets

- **Nodes.** A public function that takes a tree node (iterators,
  `RenderTree`, the exporters, `Resolver`, `Walker`, `util`, `search`) gets
  a node of either family: the `LightNodeMixin` docs render light trees with
  `RenderTree` (`lightnodemixin.py:45`) and the tests iterate them
  (`tests/test_lightnode.py`). So `node.children`, `node.parent`,
  `node.root`, `node.path` and `node.ancestors` have the property of both
  families as callees.
- **Node reprs.** `repr()`, `%r`, `{x!r}` and `str()` of a `NodeMixin`-family
  node run `Node.__repr__`, `AnyNode.__repr__` or `SymlinkNode.__repr__`.
  `LightNodeMixin` defines no `__repr__`, so a light node runs none.
- **Iterator filters and stops (J6).**
  `filter_` at `preorderiter.py:46:23` has 7 callees, at the other
  iterators only `AbstractIter.__default_filter`. `stop` at
  `preorderiter.py:44:20` and `abstractiter.py:57:56` has
  `AbstractIter.__default_stop` and `MermaidExporter.__iter__.<lambda2>`.
- **Exporter callables.** `DotExporter.__iter__` takes each callable from
  the client or `self._default_*`. `self` is a `DotExporter`,
  `RenderTreeGraph` (both: the `DotExporter` defaults) or
  `UniqueDotExporter` (its own `_default_nodenamefunc` and
  `_default_nodeattrfunc`). `MermaidExporter` uses its own defaults and the
  two lambdas of `mermaidexporter.py:156-157`.

## Judgement calls

1. **J1: a tree has nodes of one family; cross-family calls only where an
   `isinstance` check admits the other family.** A node of one family
   cannot be attached to a node of the other: `__attach` reads the parent's
   name-mangled `__children_or_empty`, which the other family lacks, and
   raises `AttributeError` (`nodemixin.py:160`, `lightnodemixin.py:162`). So
   the parent, the children and the ancestors of a node are of its own
   family (`iter_path_reverse`, `root`, `ancestors`, `siblings`, `leaves`,
   `height`, the `children` deleter). The calls that run before the failure
   count where the package's own `isinstance` check admits the other family
   (**lead, B2: an isinstance check names the type for the role**): a
   `LightNodeMixin` node as the value of `NodeMixin.parent`
   (`nodemixin.py:122`) and as a child given to `NodeMixin.children`
   (`nodemixin.py:230`). The second one makes the package itself pass a
   `NodeMixin`-family node to the `LightNodeMixin.parent` setter
   (`nodemixin.py:251`). That gives four edges, all from reading:
   - `NodeMixin.__check_loop -> LightNodeMixin.iter_path_reverse`
     (`nodemixin.py:139:69`);
   - `NodeMixin.children -> LightNodeMixin.parent` (`nodemixin.py:251:23`);
   - `LightNodeMixin.__check_loop -> NodeMixin.iter_path_reverse`
     (`lightnodemixin.py:141:69`);
   - `LightNodeMixin.__attach -> SymlinkNodeMixin.__getattr__`
     (`lightnodemixin.py:162:37`): a `SymlinkNode` parent lacks
     `_LightNodeMixin__children_or_empty`, so its `__getattr__` runs and
     forwards the name to the target, which lacks it too (J3).

   Mixing does not extend to roles that no check admits:
   `LightNodeMixin.parent` and `LightNodeMixin.children` check nothing, and
   the target of a `SymlinkNode` is a `NodeMixin`-family node (J3). A light
   child never ends up attached to a `NodeMixin` node, so the `children`
   deleter (`nodemixin.py:265`) sees no light node. `%r` of a light node
   (`nodemixin.py:141`, `237`) runs no package `__repr__`.
2. **J2: how `SymlinkNodeMixin` intercepts attributes.**
   - `hasattr(self, "_NodeMixin__parent")` and
     `hasattr(self, "_NodeMixin__children")` (`nodemixin.py:116, 125, 171`)
     call `SymlinkNodeMixin.__getattr__` for a `SymlinkNode` whose parent or
     children were never set. `__getattr__` then evaluates
     `super().__getattr__(name)` (`symlinknodemixin.py:49`): neither
     `NodeMixin` nor `object` defines `__getattr__`, so the attribute lookup
     raises `AttributeError` and no call happens; the site has a note and no
     callee. The trace confirms the two `hasattr` edges.
   - Names that live in the target (`name` and other data attributes) make
     `__getattr__` run at `node.name` (`node.py:80:68`,
     `dotexporter.py:200:21, 458:31`, `mermaidexporter.py:172:46`) and at
     `getattr()` with an attribute name (`render.py:344:35`,
     `resolver.py:349:23`, `search.py:234:23`).
   - Every assignment on a `SymlinkNode` calls `SymlinkNodeMixin.__setattr__`
     (`symlinknode.py:46, 48, 50`; `nodemixin.py:151, 152, 165, 172, 251,
     256, 265`). For `parent` and `children`, `super().__setattr__`
     (`symlinknodemixin.py:56`) is `object.__setattr__`, which calls the
     property setter `NodeMixin.parent` or `NodeMixin.children` back; both
     are callees of that site, not of the assignment. The trace confirms
     `__setattr__ -> NodeMixin.parent` and `<builtin>.object.__setattr__`.
   - `SymlinkNodeMixin` defines no `__delattr__`: `del self.children`
     (`nodemixin.py:247`) runs the deleter directly.
3. **J3: the target of a `SymlinkNode` is a `NodeMixin`-family node, also
   another `SymlinkNode`, never a `LightNodeMixin` node** (**lead, Q1**). No
   `isinstance` check or annotation admits a light node as a target (lead,
   B2), and `SymlinkNode.__init__` reads `target.__dict__`
   (`symlinknode.py:47`), which the slotted `LightNodeMixin` class does not
   have. The docs and tests link `Node`s. With a `SymlinkNode` target,
   `getattr(self.target, name)` and `setattr(self.target, name, value)`
   (`symlinknodemixin.py:52, 58`) call the target's `__getattr__` and
   `__setattr__`, and `repr(self.target)` (`symlinknode.py:53`) its
   `__repr__`. These three edges are from reading. A `Node` or `AnyNode` target has the same package properties as the link.
   A found property can nevertheless raise `AttributeError` on the link and
   cause the getter forwarding call to enter the target property; R4-F1
   below records the concrete cases. The setter still forwards no package
   property setter, because `parent` and `children` are stored locally.
4. **J4: attribute names given by the client name data attributes.**
   `RenderTree.by_attr(attrname)`, `Resolver(pathattr)` and the `name` of
   `findall_by_attr`/`find_by_attr` default to `"name"`; the docs and tests
   use `name`, `lines`, `id`, `foo`. A name of a node property (such as
   `"depth"`) would make `getattr` run that property; that is not
   considered (**lead, Q2**, B3: a value that the package never produces
   for that role). The three `getattr` sites (`render.py:344`,
   `resolver.py:349`, `search.py:234`) keep no property callee.
   `by_attr` also accepts a callable. Its result remains opaque under B5,
   even when the test passes `lambda node: node` (test_render.py:167).
   The other branch reads arbitrary client data (B3). `str(attr)` at
   render.py:354 therefore has no package node-repr callee.
5. **J5: optional import of fastcache** (`cachedsearch.py:10-13`). Both
   sides run. The ordinary `_cache(CACHE_SIZE)` call keeps
   `fastcache.clru_cache` beside the fallback `_cache`. Applying its result
   is a package-definition decorator site, so the global exception reads
   the admitted implementation. In fastcache 1.1.0, `clru_cache` creates
   `fastcache.lru` (_lrucache.c:1187); its `tp_name` and `tp_call`
   (:1034,1048) identify `fastcache.lru.__call__`. Each of the four
   decorator sites keeps this name beside `_cache.decorator`. The former
   project-specific stub-name ruling is superseded.

   Static dependency evidence: fastcache 1.1.0 `fastcache/__init__.py` (2,670 bytes), SHA-256 `8ff9bc8c53055957c78f6d25ae81f45845679e00480ad5047c22c2496eac4922`; `src/_lrucache.c` (35,648 bytes), SHA-256 `727336b96e9bc67ca7025771482d4f7ec76b9a8b1280fe45344dd30358ec3780`. Upstream source commit `f56b7aefcbb20ec8d683b484f017bc61add57c67`: [initializer](https://github.com/pbrady/fastcache/blob/f56b7aefcbb20ec8d683b484f017bc61add57c67/fastcache/__init__.py), [C implementation](https://github.com/pbrady/fastcache/blob/f56b7aefcbb20ec8d683b484f017bc61add57c67/src/_lrucache.c). Exact copies: initializer (audit record `2026-11-15/pass-2/evidence/anytree/fastcache-1.1.0-init.py`), C implementation (audit record `2026-11-15/pass-2/evidence/anytree/fastcache-1.1.0-lrucache.c`). Read-only source evidence; the dependency was not imported or executed.

6. **J6: filter and stop values follow the data flow.** The package passes
   its own filters only to `PreOrderIter` (`DotExporter`,
   `MermaidExporter`, the `leaves` properties, `findall_by_attr`,
   `find_by_attr`) and its own stop only from `MermaidExporter`. The
   lambdas are local and the defaults private, so a client cannot pass them
   to the other iterators. `AbstractIter._get_children` gets `stop` from
   `__init`, which every iterator shares, so it has `MermaidExporter`'s stop
   too.
7. **J7: `ASSERTIONS`** (`config.py:6`) is true when
   `bool(int(os.environ.get("ANYTREE_ASSERTIONS", "0")))` is true. All 14
   assertions are guarded by this switch. Default normal execution already
   disables them; `-O`/`-OO` also remove them even with the switch enabled.
   Normal-mode assertion calls remain (`any`, `len`, `start.root`).
   No runtime code reads docstrings, so `-OO` adds no distinct edge.
8. **Names outside the package.**
   - `os.environ.get` (`config.py:6:37`): `os._Environ` is private; the
     method is named through `collections.abc.Mapping`, the public class of
     its MRO that defines `get` (the trace's name).
   - `super().__init__()` in `AbstractStyle` and `Resolver` (base `object`):
     `<builtin>.object.__init__`; `super().__setattr__` in
     `SymlinkNodeMixin`: `<builtin>.object.__setattr__`.
   - `TreeError`, `LoopError`, `WalkError` define no `__init__`:
     `<builtin>.RuntimeError.__init__`, as `ResolverError` and `CountError`
     reach through `super()`.
   - `dotfile.write` and `dotfile.flush` on a `NamedTemporaryFile`
     (`dotexporter.py:294, 295`): the wrapper's `__getattr__` returns its
     local function, `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper`.
   - `file.write` on `codecs.open(...)`: `codecs.StreamReaderWriter.write`.
   - `@wraps(func)`: `functools.partial.__call__` (as tenacity).
9. **`Row(...)`** (`render.py:287, 293`): `Row` is a `collections.namedtuple`
   class. Its `__new__` is generated code (no node) and its `__init__` is
   `object.__init__`: no edge, as cachetools' `CacheInfo`.
10. **Callbacks of builtins.** `tuple(PreOrderIter(...))`
    (`nodemixin.py:379, 443`, `lightnodemixin.py:367, 431`,
    `search.py:221`) calls the iterator's `__iter__` and `__next__`.
    `enumerate(PreOrderIter(self), 1)` (`nodemixin.py:546:33`,
    `lightnodemixin.py:534:33`) calls `__iter__` during construction;
    only the enclosing `for` later calls `__next__`. `next(_iter)`
    (`zigzaggroupiter.py:56, 57`) calls `__next__`. In `_repr`, `sorted`
    immediately calls lambda2; `filter` at `node/util.py:5:29` stores
    lambda1, which the enclosing `for` later calls. `_RE_ESC.sub` calls
    the `esc` lambdas.

    The site finder suppresses separate iteration sites for builtin
    iterable expressions. Its `iter` entries at `546:13`, `534:13` and
    `5:9` describe tuple unpacking, which invokes none of these callbacks.
    The ledger retains the deferred callbacks at the construction
    expressions, as allowed by the global site-finder convention when
    one function builds and consumes the object. The existing ledger
    notes already distinguish loop consumption; they now also explain
    this placement. No caller/callee pair or site relation changes.
11. **Arguments that the site finder takes for callbacks.** At
    `len(self.children)`, `tuple(self.__children_or_empty)`,
    `AbstractIter._get_children(child.children, stop)` and similar sites,
    the property runs at its own getattr site; the call receives its value.
    Lambdas and bound methods passed to `PreOrderIter(...)`, `_findall(...)`
    and `self.__start(...)` are stored or passed on and called by package
    code elsewhere (an edge of that code).

## Default rejections

| Candidate | Sites decided | Accepted explicitly at |
|---|---|---|
| `SymlinkNodeMixin.__getattr__` | 376 | the `hasattr` sites (`nodemixin.py:116, 125, 171`), `parent.__children_or_empty` (`lightnodemixin.py:162`, J1), `node.name` (`node.py:80`, `dotexporter.py:200, 458`, `mermaidexporter.py:172`), `getattr()` (`render.py:344`, `resolver.py:349`, `search.py:234`, `symlinknodemixin.py:52`), plus the eleven inherited-getter failure sites in R4-F1 |
| `SymlinkNodeMixin.__setattr__` | 68 | `symlinknode.py:46, 48, 50`; `nodemixin.py:151, 152, 165, 172, 251, 256, 265`; `symlinknodemixin.py:58` |
| `AbstractIter.__iter__` / `__next__` | 116 / 120 | the `PreOrderIter` loops (`dotexporter.py:236, 244`, `mermaidexporter.py:192, 198`, `resolver.py:259`), `tuple()`/`enumerate()` of a `PreOrderIter` (7 sites), `next(_iter)` (2 sites, `__next__` only) |
| `RenderTree.__iter__` | 123 | `for row in self` (`render.py:297, 339, 343`) |
| `DotExporter.__iter__` | 123 | `for line in self` (`dotexporter.py:279, 293`) |
| `MermaidExporter.__iter__` | 123 | `for line in self` (`mermaidexporter.py:226`) |
| `RenderTree.__repr__`, `RenderTree.__str__` | 74, 63 | nowhere |
| `AbstractStyle.__repr__` | 74 | `{self.style!r}` (`render.py:307`) |
| `Node.__repr__`, `AnyNode.__repr__`, `SymlinkNode.__repr__` | 68 each | 11 sites that format a `NodeMixin`-family node: `nodemixin.py:138, 141, 237`, `symlinknode.py:53`, `render.py:298, 307`, `resolver.py:336, 344`, `search.py:243`, `walker.py:69` (2) |

The explicit sites that a default decides are calls of builtins on lists,
tuples, sets, generators and dicts (`tuple(children)`, `any(...)`,
`set()`, `sorted(...)`, `dict(data)`, `zip(...)`, `iter(iterable)`), the
`hasattr` calls of `LightNodeMixin` (a light node is never a
`SymlinkNodeMixin`), and `super().__getattr__(name)` (no call, J2).

## Exclusions

| Site | Excluded | Why |
|---|---|---|
| `dictimporter.py:46:28` `self.nodecls(...)` | `SymlinkNode.__init__` | no test, doc or package call passes it as `nodecls` |
| `render.py:265:26` `style()` | `AbstractStyle.__init__` | argument binding fails before the function runs |

## Functions that no site calls

The public API (constructors, properties, `export`, `import_`, `get`,
`glob`, `walk`, the search functions, `to_dotfile`, `to_file`, ...) and the
methods that Python calls implicitly (`__repr__`, `__iter__` of the
exporters and `RenderTree`, the property setters and the deleter). Three
functions never ran in the tests: `DotExporter.to_picture` (needs graphviz;
its test is deselected), `AbstractIter._iter` (only a bare `AbstractIter`
reaches it) and `NodeMixin.anchestors` (deprecated).

## Tools

`sites.py` matched names without name mangling. A private attribute
`self.__x` in class `C` is `_C__x`, but the site finder took it as `__x`:
- `self.__iter(...)` in `DotExporter.__iter__` (`dotexporter.py:196:27`) was
  marked as a value site, because `AbstractIter` assigns `self.__iter`
  (`abstractiter.py:19`, really `_AbstractIter__iter`). The same held for
  `mermaidexporter.py:158:27`.
- `self.__check_loop(value)` in `NodeMixin.parent` (`nodemixin.py:130:30`)
  got `LightNodeMixin.__check_loop` as a candidate, and likewise every
  mangled method and property of the two node families, the two exporters,
  the two importers and `RenderTree.__next`/`PostOrderIter.__next`.

The ledger rejected each of these candidates with "name mangling". Fixed:
`sites.py` now mangles private names as Python does. The two sites are no
longer value sites (their notes stay), and the ledger no longer rejects the
40 names that stopped being candidates (39 rejection lines: 35 deleted, 4
shortened). No edge changed.

## Statistics

| | Count |
|---|---|
| All AST sites | 1,337: the 1,083 sites below plus 254 implicit sites without package candidates |
| Explicit or candidate-bearing sites | 1083 (385 call, 73 decorator, 81 iter, 20 op, 388 getattr, 78 setattr, 2 delattr, 56 format) |
| Sites with candidates / value sites | 871 / 33 |
| Ledger entries | 572 (385 call, 73 decorator, 77 getattr, 17 setattr, 2 delattr, 11 iter, 5 format, 2 op) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 718 / 147 (14) / 2 (2 nodes) / 163 |
| Default rejections | 6 lines, 13 candidates (table above) |
| Nodes | 223 (190 functions, 33 modules) |
| Edges | 581: 369 in the package, 212 to 76 callees outside |
| Edges that the trace confirms | 486 of 581 (83.6%) |
| Edges only from reading | 95 (75 in the package, 20 outside) |
| Trace edges rejected | 0 |
| Functions that the tests run | 187 of 190 |


## Round 4 source-first audit (2026-11-16)

R4-F1 corrects an original-baseline omission: 18 package pairs and 22 site
relations added; no pair removed and no node changed. The graph now has 581
pairs on 223 nodes. A client getter's exception can control package lookup
without making client methods or their results named callees (global B5).

A concrete `SymlinkNode` uses an inherited `NodeMixin` property first. That
property can call a client parent/child getter which raises `AttributeError`.
Python then calls the concrete link's `SymlinkNodeMixin.__getattr__`, even
though the property exists. At `symlinknodemixin.py:52:23`, forwarding enters
the same property on a concrete package `Node` target. This supersedes the
old default reason that no found property could fall back. It does not change
J4's exclusion of arbitrary client-supplied property names.

The following static witnesses use fresh objects, successful constructors,
and a first lookup. They were not executed. Client parent/child overrides
are opaque; the link and forwarded target are exact package classes.

- **W1:** A client `Node` subclass P preserves the `NodeMixin.parent` setter.
  Its parent getter returns None while its children are empty, then raises
  `AttributeError`. Build `p=P('p')`, `t=Node('t')`,
  `s=SymlinkNode(t,parent=p)`. The loop check reads p.parent before attachment
  adds s, so construction completes. Reading public s.path, s.root or s.depth
  reaches a failure inside its inherited getter. The public path getter
  reads self._path, which falls back to t._path and then repairs s.path;
  the root/depth lookups forward directly to t.root/t.depth.
- **W2:** Use two fresh P parents: `t=Node('t',parent=P('p1'))` and
  `s=SymlinkNode(t,parent=P('p2'))`. Both attachments complete. On s.path,
  the inner _path fallback also fails on t, so the outer path fallback
  enters t.path before that body raises. For the ancestors caller at
  348:28, attach another plain Node below s with the P getters disarmed by
  a client-owned flag; arm that flag after construction and make the first
  ancestors read. No package state is edited and no failed object is reused.
- **W3:** P is a client Node with a path getter that raises. For ordinary
  t and `s=SymlinkNode(t,parent=P('p'))`, attachment never reads p.path.
  Reading s.ancestors fails at p.path and forwards to t.ancestors.
- **W4:** Give both the exact target t and the exact link s distinct W3
  parents. On s.anchestors, the inner ancestors fallback also fails on t;
  the outer fallback then enters t.anchestors before that getter raises.
- **W5:** P overrides children to raise, preserving the public setter.
  `s=SymlinkNode(Node('t'),parent=P('p'))` constructs because attachment
  reads the parent's private child storage. First s.siblings fails at
  p.children and forwards to the target's siblings.
- **W6:** Put a client Node child C whose height getter raises below
  `s=SymlinkNode(Node('t'))`. First s.height fails at C.height and forwards
  to the target's height. Place s below a plain Node to reach the upstream
  recursive height site at 499:30.
- **W7:** Put a client Node child C whose children getter raises (original
  setter retained) below `s=SymlinkNode(Node('t'))`. Attachment does not
  read C.children. On fresh instances, first s.descendants, s.leaves or
  s.size consumes PreOrderIter, fails at C.children, and forwards to the
  corresponding target property.

The eleven new forwarding pairs at `symlinknodemixin.py:52:23` have
`NodeMixin._path`, `path`, `root`, `depth`, `ancestors`, `anchestors`,
`siblings`, `height`, `descendants`, `leaves` and `size` as callees.

The eleven upstream site relations, with `SymlinkNodeMixin.__getattr__`
as callee, form seven graph pairs:

| Caller | Site | Witness and cutoff |
|---|---|---|
| NodeMixin.path | nodemixin.py:298:21 | W1, inner _path fallback |
| NodeMixin.ancestors | nodemixin.py:348:28 | W2 variant, parent is exact link |
| NodeMixin.anchestors | nodemixin.py:359:21 | W3, ancestors fallback |
| NodeMixin.height | nodemixin.py:499:30 | W6, exact link child |
| Resolver.__start | resolver.py:218:25 | W1, get(s, '/t') reads s.root |
| commonancestors | util/__init__.py:26:23 | W3, commonancestors(s) |
| Walker.walk | walker.py:66:27, 67:23 | W2, s is start or end; preceding path succeeds when s is end |
| Walker.walk | walker.py:68:18, 68:34 | W1, start/end are s and t in either order; both paths succeed via inner _path repair |
| Walker.walk | walker.py:74:39 | W1, start=s/end=t; roots match t, common is (t,); normal mode with ANYTREE_ASSERTIONS=1 |

Parent, children, is_leaf and is_root on a concrete link remain protected by
package storage and have no such failure path. No client SymlinkNode subclass
is used to expand receivers. Mixed-family storage, arbitrary property names,
client callback results, generated Row constructors, and failed AbstractStyle
argument binding retain their exclusions. The 13 default families, all 563
baseline pairs, 1,337 inventory sites and 229 body definitions were reviewed.
Fastcache 1.1.0's retained initializer/C source was read to confirm the four
package-definition decorator names; ordinary missing-library calls remain
opaque. No package, dependency, test, example, generated code or PyCG ran.

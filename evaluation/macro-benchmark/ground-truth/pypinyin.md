# pypinyin: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 0 edges and adds 42. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

The second complete audit found 0 false positives and 0 missed edges,
plus 1 correction to source-site attribution or explanations. See
the pass-2 report (audit record `2026-11-15/pass-2/pypinyin-review.json`).
The current ledger and statistics below include both audit passes.

The third complete source-first audit found no false positive or missing
caller-callee pair. As an allowed same-function placement normalization, it
adds the callback witness at the outer `list` call of `core.py:46:21` while
retaining `map` at46:25. The earlier map placement was valid on both language
branches under README ruling 12. The graph remains at 494 edges; site-target relations increase
from 749 to 750. It also corrects stale receiver and scope explanations.

The fourth complete source-first audit retains all 181 nodes, 494 edges and
750 site-target relations. It corrects one remaining stale version note at
`toneconvert.py:71`: the admitted older branch is Python 2.7 and 3.4–3.6,
not 3.3 (explicit support drop in `CHANGELOG.rst:413-414`). Normal, `-O`
and `-OO` were considered as the round-4 working assumption; the sole
bytes assertion introduces no additional pair. The two Python-2-only
encode/decode edges remain under the global README's explicit convention.

Release v0.55.0 (commit `df10157`). Analysed source: `pypinyin/` without
`pypinyin/__pyinstaller/`: 43 modules, 138 functions (9 lambdas), 22
classes. The `*.pyi` stubs are not analysed as source. The three modules of
`pypinyin/legacy/` hold only literal data: they are nodes without sites.
`setup.py:75` sets `python_requires='>=2.6, !=3.0.*, !=3.1.*, !=3.2.*, <4'`,
which admits 2.6, 2.7 and 3.3 and later below 4. However, version 0.33.0
stopped testing and guaranteeing compatibility for 2.6 and 3.3
(`CHANGELOG.rst:413-414`). Python 2.7 and 3.4-3.6 provide sufficient
witnesses for the historical branches and regex names (judgement 1).

The ledger is `pypinyin.ledger`; the graph `pypinyin.json` is generated
from it. Two trace edges are rejected in `pypinyin.rejected.json`
(judgement 5).

| Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions |
|---|---|---|---|---|---|---|---|---|---|
| 181 | 494 (210 / 284) | 433 (87.7%) | 61 | 2 | 132 of 138 | 670 | 10 | 1 (33) | 1 |

The full site inventory has 1643 sites: 666 calls, 3 decorators and
974 other implicit sites. Of these, 703 need a decision before defaults;
670 have ledger entries. The audit also reviewed all 973 unlisted sites:
33 decided by the membership default and 940 without candidates.
The three large legacy literal dictionaries were checked by AST only;
the source-first inventory records exact counts and hashes.

The independent audit is in `pypinyin.audit.md`. It applied F1 (the table
said `1 (34)`) and F2 (judgement 2); the lead's rulings on the judgement
calls are recorded with each call below.

## Architecture, as the ledger uses it

- `Pinyin` (`core.py:56`) splits the text (`seg`, with the hooks
  `pre_seg`, `get_seg`, `post_seg`) and hands each word to its converter
  (`self._converter.convert`, `core.py:107`). `get_seg` returns
  `simpleseg.seg`, which uses the `Seg` object `mmseg.seg`
  (`mmseg.py:123`) and its `PrefixSet`.
- The converters (`converter.py`): `Converter` (a plain class whose
  `convert` raises `NotImplementedError`), `DefaultConverter` and
  `UltimateConverter`. `DefaultConverter` calls its own hooks on `self`
  (`post_pinyin`, `pre_convert_style`, `post_convert_style`,
  `pre_handle_nopinyin`, `post_handle_nopinyin`). `UltimateConverter`
  overrides `post_convert_style` and `post_pinyin`; they make a new private
  `_v2UConverter`, `_neutralToneWith5Converter` or `_toneSandhiConverter`
  (each a mixin of `pypinyin.contrib` before `DefaultConverter`) and call
  one mixin method on it (`converter.py:362`, `368`, `382`). Each mixin
  method calls `super()`, which finds the `DefaultConverter` method.
- The styles (`style/__init__.py`): `_registry` maps each `Style` to a
  function. `auto_discover()` (`converter.py:20`, run when `pypinyin` is
  imported) imports the nine style modules, which register 18 functions:
  `initials.convert` through `@register`, and bound methods of the
  converter objects of `others`, `tone`, `finals`, `bopomofo`, `cyrillic`,
  `gwoyeu`, `braille_mainland`, and `wadegiles.to_wade_glides`.
  `pypinyin.style.convert` calls `_registry[style](...)`
  (`style/__init__.py:26`).
- `register(style)` used as a decorator stores the undecorated function in
  `_registry` and returns `wrapper` (`style/__init__.py:52-59`). So the
  module attribute `pypinyin.style.initials.convert` is the wrapper, and
  `_registry[Style.INITIALS]` is the function `initials.convert` itself.
- `runner.py` (the `pypinyin` command) and `tools/toneconvert.py` are
  command-line programs with argparse.

## Scope rules

**A. Edges are per function.** Every function keeps the out-edges of its
body. Functions that the tests do not run: `compat.callable_check`
(no edges: no supported version defines it, judgement 2),
`Converter.convert` (one implicit raise site, with no package callee),
`runner.NullWriter.write`
(no sites), `runner.main` (its 14 edges come from reading),
`style._utils.has_finals` (only an `in` test on a str) and
`utils._replace_tone2_style_dict_to_default` (1 edge).

**B1. Receivers.**
- Public methods inherited from `DefaultConverter` also run on the constructed
private package subclasses `_v2UConverter`, `_neutralToneWith5Converter` and
`_toneSandhiConverter`. Rule A does not require a package caller of each
inherited body. Thus `convert` reaches `ToneSandhiMixin.post_pinyin`, and
`convert_style` reaches `V2UMixin.post_convert_style` and
`NeutralToneWith5Mixin.post_convert_style`, alongside the original two
converters.
- `self` in a mixin method is the package's private converter of that mixin
  or a bare mixin object (the mixins are plain public classes). On the
  private converter, `super()` finds `DefaultConverter`; on a bare mixin it
  finds nothing (`AttributeError`). So `uv.py:39`, `neutral_tone.py:51` and
  `tone_sandhi.py:22` have one callee each, the `DefaultConverter` method.
- `self` in `Pinyin`, `Seg`, `PrefixSet` and the style converter classes
  is an object of that class; none has a package subclass.

**B2. Arguments and stored values.** The `.pyi` stubs next to the modules
give the parameter types (judgement 3).
- `Pinyin(converter)`: stub type `Converter` (`core.pyi`). The package
  values are `Converter`, `DefaultConverter` and `UltimateConverter`, so
  `core.py:107` has `DefaultConverter.convert` and `Converter.convert`
  (judgement 4). `isinstance(self._converter, ToneSandhiMixin)`
  (`core.py:94`) names the mixin for the role, but a bare `ToneSandhiMixin`
  has no `convert` (no edge).
- `errors` (`converter.py:319`): stub type `Union[Callable[[Text], Text],
  Text]`, a bare callable. The documentation passes lambdas, the tests
  lambdas and a callable class. No package callee.
- `Seg(prefix_set)`: `PrefixSet` (docstring and stub), so `word in
  self._prefix_set` (`mmseg.py:33`) runs `PrefixSet.__contains__`, and
  `self._prefix_set.train` (`mmseg.py:81`) is `PrefixSet.train`.
  `retrain(seg_instance)`: `Seg`, so `mmseg.py:133` is `Seg.train`.
- `runner.main`: `func` (`runner.py:126`) is `pypinyin.pinyin` or
  `pypinyin.slug`, because argparse limits `--func` to these choices
  (`runner.py:60`).
- `toneconvert.re_sub`: `func = ACTIONS[action]` (`toneconvert.py:47`) is
  one of the four `to_*` functions of the dict; any other key raises
  `KeyError`.
- `register.decorator.wrapper`: `func` (`style/__init__.py:57`) is a
  function that `@register(...)` decorates: `initials.convert` in the
  package, client functions otherwise.

**B3. Not considered.** An arbitrary package callable passed by a client
to `register` or as `errors` without evidence for that role. The package
registers the 18 style implementations listed above, which remain in scope;
it supplies no package callable as `errors`. The wrapper of
`initials.convert` put into `_registry` by a client is also excluded
(at `style/__init__.py:26`).

**B4. Concrete outside types.** Text parameters (`Text` in the stubs) are
`str`: `<builtin>.str.replace`, `.join`, `.format`, `.index`,
`.startswith`, `.split`, `.strip`. `load_single_dict` and
`load_phrases_dict` take `Dict` (stub and docstring):
`<builtin>.dict.items`. `re_sub` takes `re.Match`: `re.Match.group`.
`toneconvert.main` takes `List[Text]`: `<builtin>.list.append`.

**B5. Client objects are opaque.** The `hans` list of a client, a client's
`errors` callable, a client's style function in `_registry`, a client's
container as `prefix_set`.

**C. Public.** `pypinyin.core.Pinyin`, `pypinyin.converter.Converter`,
`DefaultConverter`, `UltimateConverter`, the three mixins of
`pypinyin.contrib`, `pypinyin.seg.mmseg.Seg` and `PrefixSet`, and the style
converter classes are public. `_v2UConverter`, `_neutralToneWith5Converter`
and `_toneSandhiConverter` are private.

## Default rejection

`pypinyin.seg.mmseg.PrefixSet.__contains__` is proposed at every `in` and
`not in` test (34 sites). The default rejects it; 33 sites test a str,
list, tuple, set or dict. The entry of `mmseg.py:33:25` (`word in
self._prefix_set`) accepts it.

## Value sites

Ten value sites, each with a note: `errors(chars)` (no callee),
`self.seg(...)` three times (`Pinyin.seg`), `self.get_seg()(hans)`
(`simpleseg.seg`), `func(...)` in `runner.main` (`core.pinyin`,
`core.slug`), `_registry[style](...)` (18 callees), `@wraps(func)`
(`functools.partial.__call__`), `func(pinyin, **kwargs)` in the wrapper
(`initials.convert`), and `func(...)` in `toneconvert.re_sub` (four `to_*`
functions). The checker does not mark `args.func(args)`
(`toneconvert.py:99`) as a value site; its entry has
`functools.partial.__call__` and the callback `toneconvert.convert`, with
a note.

## Judgement calls and the lead's rulings

The lead ruled on each call after the audit: 1, 3, 4, 5, 6, 7 and 8 are
kept as written; 2 is changed (audit F2).

1. **Python 2 is a supported version.** `requires-python` admits 2.6 and
   2.7, and `tox.ini` still lists `py26` and `py27`, but version 0.33.0
   stopped testing and guaranteeing 2.6/3.3 compatibility
   (`CHANGELOG.rst:413-414`). `README_en.rst:15` and the classifiers name
   Python 2.7, which suffices for the Python-2-only branches:
   `pypinyin/__init__.py:54-56` (`x.encode('utf-8')`),
   `runner.py:100-103` (`han.decode(...)`), `runner.py:117-118` (an
   attribute, no call) and `toneconvert.py:70-71` (the same callee as the
   other branch). I named the builtin callees of Python-2-only code by the
   Python 3 counterpart of the Python 2 type: `unicode.encode` is
   `<builtin>.str.encode`, and Python 2 `str.decode` is
   `<builtin>.bytes.decode` (`bytes` is `str` on Python 2). Code that runs
   on both versions gets only its Python 3 names: `text_type(...)`
   (`converter.py:329`, `331`) is `<builtin>.str`, not also
   `<builtin>.unicode`. Effect: 2 edges (`pypinyin -> <builtin>.str.encode`,
   `pypinyin.runner.main -> <builtin>.bytes.decode`). Ruling: kept. The
   README rule "a version branch runs if a supported version takes it"
   decides, and the builtin callees of such a branch keep the Python 3 name
   of the type.
2. **`compat.callable_check` (`compat.py:26-30`).** The `def` is the
   `except NameError` fallback for a missing builtin `callable`, which only
   Python 3.0 and 3.1 lack; `requires-python` excludes them. So on every
   supported version `callable_check` is the builtin `callable`:
   `converter.py:318` has `<builtin>.callable` and rejects the candidate
   `compat.callable_check`. I first kept the edge of the fallback's body,
   `compat.callable_check -> <builtin>.hasattr`, by rule A. Ruling (audit
   F2): no edge. A `def` in a branch that no supported version takes makes
   no function, so its body has no edges, as for code under `if
   TYPE_CHECKING:`. The site `compat.py:30:23` has a note with this reason
   and no callee. Effect: -1 edge.
3. **The `.pyi` stubs as annotations.** The README says that the stubs
   are not analysed; I read that as scope (they are not nodes) and used
   their parameter types as annotations for rules B2 and B4. They decide
   judgement 4 (`converter: Converter`), the `PrefixSet` and `Seg` roles
   (the docstrings say the same), the `Dict` parameters, and the bare
   callable of `errors`. Ruling: confirmed.
4. **`Converter.convert` is a callee of `Pinyin.pinyin` (`core.py:107`).**
   `pypinyin.converter.Converter` is public and plain (`converter.py:23`:
   "TODO: use ``abc`` module"), so a client can make one, and the stub type
   of `Pinyin`'s `converter` admits it (B1, B2). Its `convert` raises
   `NotImplementedError`. Edge from reading only. Ruling: kept (B1).
5. **Mixin dispatch.** The three constructed package subclasses admit
   the three inherited-body edges described under B1, independently of
   the client subclass that exposed each pair in the trace. Only the two
   cross-mixin `super()` calls remain rejected:
   `NeutralToneWith5Mixin.post_convert_style` to
   `V2UMixin.post_convert_style`, and the reverse. These require the
   client-created combined classes `HerConverter` and `TheyConverter`.
6. **Version branch `constants.py:33`.** `SUPPORT_UCS4` is false on narrow
   builds (Python 2 on some platforms); both branches call `re.compile`.
   Notes at `constants.py:34` and `58`.
7. **Outside names, by earlier rulings.** `os.environ.get` is
   `collections.abc.Mapping.get` (`os._Environ` is private; as in anytree),
   the file of `codecs.open` is `codecs.StreamReaderWriter` (as in
   anytree), and the default `sys.stdin` is `io.TextIOWrapper` (as the
   README names `sys.stdout`).
8. **`runner.NullWriter`.** `runner.main` sets `sys.stdout` and
   `sys.stderr` to a `NullWriter` while it calls `pinyin` or `slug`
   (`runner.py:125-129`). Neither writes or prints, so the package never
   calls `NullWriter.write`; it has no caller. `NullWriter()` runs
   `object.__init__`: no edge.

## Trace

The trace (985 tests passed, 2 skipped) has 435 edges. 433 of them are in
the graph; the other 2 are judgement 5. Of the 61 edges from reading only,
39 are the historical regex names below. The other 22 are
`pypinyin -> <builtin>.str.encode` (Python 2), `Converter.convert` (1), the module-level `main()` calls of
`__main__`, `runner` and `toneconvert` (3, under `if __name__ ==
'__main__'`), all 14 edges of `runner.main` (one is the Python 2
`bytes.decode`; the tests call only its parser), `toneconvert.main ->
<builtin>.list.append` (stdin is empty in the tests), the wrapper of
`@register` calling `initials.convert` (the tests decorate only their own
functions), and `utils._replace_tone2_style_dict_to_default` (1).

Historical Python 3 runtimes admitted by `requires-python` also lack the
public `re.Pattern` and `re.Match` aliases. The ledger keeps 39 additional
`_sre.SRE_Pattern` and `_sre.SRE_Match` method pairs for these runtimes.
Modern public names remain for Python 3.7 and later.

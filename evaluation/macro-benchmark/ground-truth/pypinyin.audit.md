# pypinyin: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [pypinyin.md](pypinyin.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release v0.55.0, commit `df101577145af2eb1abe5656e592e34e3bb56d23`. Audited
files, as of 2026-11-13: `pypinyin.ledger` (670 entries, 39 notes, 70
rejection lines, 1 exclusion, 1 default rejection), `pypinyin.json` (453
edges, 207 in the package and 246 outside), `pypinyin.rejected.json` (5
edges) and `pypinyin.md`. `check.py --benchmark-dir macro-benchmark-heldout-2
pypinyin` reports no errors. The trace confirms 430 edges; 23 come from
reading only.

I applied the scope rules of `macro-benchmark/README.md` (A, B1 to B5, C).
I read every module of `pypinyin/` except the literal data of
`pypinyin/legacy/` (no sites), the `.pyi` stubs, `setup.py`, `tox.ini`,
`CHANGELOG.rst`, and the tests and docs as data. I did not run or import
the package, and I used no static analysis tool.

## Result

The blind sample has 79 sites and 0 disagreements. The exhaustive checks
found no missed edge and no edge that cannot happen. The open items are the
writer's eight judgement calls (rulings below) and one wrong number in
`pypinyin.md` (F1). If the lead follows the version-branch default for
judgement 2 (F2), the graph loses 1 edge: 452 edges (207 / 245), 22 from
reading only. All other rulings keep the graph as it is.

## Findings

| Id | Severity | Site or edge | Evidence | Edges |
|---|---|---|---|---|
| F1 | wording | `pypinyin.md`, the table: "Default rejections (sites) 1 (34)" | The README defines the column as the sites that a default decides. `check.py --report pypinyin` gives 33 sites for `PrefixSet.__contains__`: 34 `in` tests propose it, and the entry of `mmseg.py:33:25` accepts it. The table must say `1 (33)`. | 0 |
| F2 | ruling (minor) | `pypinyin.compat.callable_check -> <builtin>.hasattr` (`compat.py:30`) | The `def` is the `except NameError` fallback of `compat.py:26-30`. Only Python 3.0 and 3.1 lack `callable`, and `setup.py:75` excludes them. So on no supported version does the function exist, and its body cannot run. The README edge rule needs "when A runs, on any Python version that the release supports". The version-branch default ("a version branch runs if a supported version takes it") and the pluggy precedent (calls under `if TYPE_CHECKING:` have no callees, `pluggy.md`, `_execution.py:40-41`) give no edge. Rule A keeps the body edges of a function that nothing calls; it does not cover a function that never exists. The competing reading is the optional-import default ("both sides run"), but here the fallback depends only on the version, not on the environment. | -1 |

## Rulings on the writer's judgement calls (`pypinyin.md`)

| # | Writer's call | Ruling that the nearest rule supports | Rule | Edges |
|---|---|---|---|---|
| 1 | Python 2 branches run; their builtin callees get the Python 3 name of the counterpart type (`<builtin>.str.encode`, `<builtin>.bytes.decode`) | Keep. The edges exist: requires-python admits 2.6 and 2.7. The README has no rule for Python 2 names; the writer's mapping keeps every name resolvable by the Python 3 tools and is applied the same way at all sites (`text_type(...)` is `<builtin>.str`). Caveat: on Python 2, `<builtin>.str.encode` resolves to the byte-string method, not to `unicode.encode`. Write the convention into the README. | "Ground-truth conventions": Edges ("any Python version that the release supports") and Judgements ("a version branch runs if a supported version takes it"); names: none | 0 (no Python 2 edges: -2; Python 2 names: 2 renamed and +1 `<builtin>.unicode` at `converter.py:329, 331`) |
| 2 | `compat.callable_check` keeps its body edge (rule A) | Remove the edge (F2). | Judgements: version-branch default; Edges | -1 |
| 3 | The `.pyi` stubs give the parameter types for B2 and B4 | Keep. The stubs are not nodes, but they are the package's annotations. The cachetools audit used `__init__.pyi` the same way, with the lead's decision on its `_AbstractCondition` protocol. | B2 ("When a parameter has an annotation, the annotation decides"), B4 | 0 |
| 4 | `Converter.convert` is a callee of `core.py:107` | Keep. `Converter` is public and not abstract by `abc`; the stub type `converter: Converter` (`core.pyi:92`) admits it. | B1 ("a plain public class is a receiver of its own methods"), B2 | 0 |
| 5 | Client classes that combine the mixins are client code; the 5 trace edges through them are rejected | Keep the rejections. The mixins are documented for client subclasses (`uv.py:20`, `neutral_tone.py:28`); the package's own private converters reach only `DefaultConverter`. | B1 ("A base class that the package documents for subclassing is judged on the class itself"; "the client's subclasses are client code") | 0 (counting client compositions: +5) |
| 6 | `constants.py:33` (`SUPPORT_UCS4`): both branches run | Keep. Narrow builds exist on Python 2; both branches call `re.compile`. | Judgements: version-branch default | 0 |
| 7 | `os.environ.get` is `collections.abc.Mapping.get`; `codecs.StreamReaderWriter.read`; `io.TextIOWrapper` for the default `sys.stdin` | Keep. Same names as anytree (`anytree.ledger` 6:37, 280:27) and the README (`sys.stdout`); the trace gives `collections.abc.Mapping.get` as canonical and `io.TextIOWrapper.*` as aliases. | Callees outside the package; micro-benchmark "Methods" | 0 |
| 8 | `runner.NullWriter.write` has no caller; `NullWriter()` has no edge | Keep. Between `runner.py:125` and `:129` only `pinyin` or `slug` runs, and neither writes, prints or warns (no `print`, `warnings` or `logging` call in that path). | Rule A; Edges (instantiation: `object.__init__` gives no edge) | 0 |

## Step 1: blind re-derivation

**Method.** I copied `projects.toml` to
`$TMPDIR/heldout2-audit-pypinyin/bench/` with a symbolic link `projects` to
`macro-benchmark-heldout-2/projects`, and ran `check.py --benchmark-dir
<that> --skeleton pypinyin` (no ledger, so no default). The skeleton has 703
sites (666 call, 3 decorator, 34 op) and 10 value sites. I numbered the
site lines from 0 in skeleton order and drew
`random.Random(20261111).sample(range(703), 70)`. One value site was drawn
(`runner.py:126:20`); I added the other 9. Calls dominate the skeleton
because the explicit sites are 95% of it, so I did not draw by kind; the
34 op sites are all checked in step 2. I wrote the callees of each site
before I opened any file of the writer
(`$TMPDIR/heldout2-audit-pypinyin/blind-answers.md`; the table is copied
below).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Drawn (67 call, 3 op; 1 value site) | 70 | 70 | 0 |
| Value sites added (8 call, 1 decorator) | 9 | 9 | 0 |
| **Total** | **79** | **79** | **0** |

Before the comparison I had noted the same three open points that the
writer lists as judgements 1, 4 and 5, with the same answers.

**Blind answers** (callees; rejected candidates in parentheses):

| Site | Callees |
|---|---|
| tone_sandhi 53:30, 67:53, 106:36 | `<builtin>.str.join`; `<builtin>.str.replace`; `<builtin>.len` |
| tone_sandhi 150:24, converter 255:19, standard 90:25 (op) | none (`PrefixSet.__contains__`: str, dict, set) |
| converter 67:27, 195:22 | `<builtin>.list.extend`; `<builtin>.isinstance` |
| converter 271:43 | `DefaultConverter.convert_style` |
| converter 318:26 | `<builtin>.callable` (`compat.callable_check`) |
| core 27:38, 28:30, 51:28, 97:41, 134:18 | `<builtin>.dict.items`; `_tone_convert.tone2_to_tone`; `<builtin>.dict.update`; `re.Pattern.match`; `itertools.chain` |
| core 166:34 | `Pinyin.post_seg` |
| core 210:44 | `DefaultConverter.handle_nopinyin` (`core.handle_nopinyin`) |
| core 279:39 | `UltimateConverter.__init__` (`DefaultConverter.__init__`) |
| phonetic_symbol 53:72; pinyin_dict 9:26 | `<builtin>.dict.items`; `os.path.join` |
| runner 66:31, 89:28, 135:26, 138:22 | `<builtin>.dict.keys`; `io.TextIOWrapper.isatty`; `<builtin>.isinstance`; `<builtin>.print` |
| runner 98:24 | `runner.get_parser` (`toneconvert.get_parser`) |
| runner 126:20 (value) | `core.pinyin`, `core.slug` |
| simpleseg 44:26; standard 41:27, 97:29, 100:39 | `<builtin>.enumerate`; `<builtin>.dict.keys`; `<builtin>.str.startswith`; `<builtin>.len` |
| standard 122:21 | `re.Pattern.sub`, `standard.convert_uv.<lambda1>` |
| standard 157:24, 158:25 | `standard.convert_uv`; `standard.convert_iou` |
| _constants 91:22; bopomofo 17:16, 21:16, 31:16; braille_mainland 27, 34, 37, 40, 41, 43, 47, 54, 60 (:16); gwoyeu 31:16 | `re.compile` (14 sites) |
| _tone_convert 71:22, 108:28, 398:18, 444:45, 495:23 | `_tone_convert.tone2_to_tone`; `<builtin>.str.replace`; `<builtin>.dict.get`; `<builtin>.str.replace`; `re.Pattern.sub` |
| _tone_convert 262:29 | `_tone_convert.to_finals_tone3` (`FinalsConverter.to_finals_tone3`) |
| _tone_rule 34:36, 58:49; _utils 54:28 | `<builtin>.str.index`; `<builtin>.len`; `<builtin>.len` |
| bopomofo 57:33, 69:28 | `re.Pattern.sub` (the replacement is a template string) |
| finals 21:25 | `_tone_convert.to_finals` (`FinalsConverter.to_finals`) |
| gwoyeu 77:9 | `style.register` (`GwoyeuConverter.to_gwoyeu`: stored, not called) |
| initials 12:24 | `<builtin>.dict.get` |
| wadegiles 439:20 | `<builtin>.list.sort`, `wadegiles.<lambda1>` |
| wadegiles 524:37 (`<lambda4>`), 528:41, 532:29 | `<builtin>.len`; `_utils.replace_symbol_to_no_symbol`; `wadegiles._fixed_result` |
| toneconvert 29:20, 98:29 | `<builtin>.str.join`; `argparse.ArgumentParser.parse_args` |
| toneconvert 77:23 | `functools.partial` (all 5 `convert` candidates: stored, not called) |
| toneconvert 99:14 | `functools.partial.__call__`, `toneconvert.convert` |
| utils 32:32 | `<builtin>.list.append` |
| converter 319:26 (value) | none: `errors` is a client callback (stub: bare `Callable`) |
| core 91:32, 98:49, 102:44 (value) | `Pinyin.seg` (`simpleseg.seg`) |
| core 164:38 (value) | `simpleseg.seg` |
| style 26:32 (value) | the 18 registered functions |
| style 55:10 (value, decorator) | `functools.partial.__call__` |
| style 57:24 (value) | `style.initials.convert` |
| toneconvert 48:21 (value) | `_tone_convert.to_normal`, `to_tone`, `to_tone2`, `to_tone3` |

## Step 2: exhaustive checks

**Dispatch (B1).** Every row is identical to the ledger.

| Site | Receivers | Callees |
|---|---|---|
| `self._converter.convert` `core.py:107` | `DefaultConverter`, `UltimateConverter` (inherits), `Converter` (judgement 4) | `DefaultConverter.convert`, `Converter.convert` |
| `self.post_pinyin` `converter.py:56`; `self.post_convert_style` `:115` | `DefaultConverter`, `UltimateConverter` | the method of each class |
| 12 other `self.*` calls in `DefaultConverter` (`:54, 60, 64, 105, 112, 176, 183, 187, 259, 271, 278, 299`) | same; no package override | the `DefaultConverter` method |
| `super(UltimateConverter, self).*` `:349, 356, 376` | `UltimateConverter` | `DefaultConverter.__init__`, `.post_convert_style`, `.post_pinyin` |
| `_v2UConverter()...` `:362`, `_neutralToneWith5Converter()...` `:368`, `_toneSandhiConverter()...` `:382` | a new private converter | the mixin method; the constructor gives `DefaultConverter.__init__` |
| `super(<Mixin>, self).*` `uv.py:39`, `neutral_tone.py:51`, `tone_sandhi.py:22` | the private converter (a bare mixin raises `AttributeError`) | the `DefaultConverter` method |
| `self._third_tone`, `_bu`, `_yi` `tone_sandhi.py:27-29` | `_toneSandhiConverter` | its own methods |
| `Pinyin`: `self.seg`, `pre_seg`, `get_seg`, `post_seg`, `pinyin` | `Pinyin` (no package subclass) | its own methods; `self.get_seg()(hans)` is `simpleseg.seg` |
| `word in self._prefix_set` `mmseg.py:33`; `self._prefix_set.train` `:81`; `seg_instance.train` `:133` | `PrefixSet` (docstring, stub); `Seg` | `PrefixSet.__contains__`; `PrefixSet.train`; `Seg.train` |
| `self._pre_convert`, `to_bopomofo`, `to_cyrillic`, `to_normal`, `to_tone2`; `converter.to_tone3` `_tone_convert.py:400` | the style converter class (no package subclass) | its own method |

Value roles: `_registry` (18 functions, `style/__init__.py:26`; tests and
docs register only client functions, `tests/test_style.py:12, 32, 47`,
`docs/usage.rst:155`), the `@register` wrapper (`initials.convert`), runner
`func` (`pinyin`, `slug`), `ACTIONS` (4 functions), `args.func` (the
partial of `toneconvert.py:77`), `errors` (client only: docs and tests pass
lambdas and a client class). All as in the ledger.

**Default rejection.** `PrefixSet.__contains__` decides 33 `in` sites. I
checked each container: 17 str, 5 dict (`PHRASES_DICT` three times,
`PINYIN_DICT`, `_registry`), 4 set (three of `standard.py` and
`PrefixSet`'s own `self._set`), 4 list (`_FINALS` three times, `new_lst`),
and 3 tuple (`compat.py:14` and the class tuples `NUMBER_TONE`,
`NUMBER_AT_END`). None is a `PrefixSet`. Correct.

**Functions that no site calls** (15 functions; no module has a caller,
because an import adds no edge). The
public API (`core.lazy_pinyin`, `load_single_dict`, `load_phrases_dict`,
`to_fixed`, `handle_nopinyin`, `single_pinyin`, `phrase_pinyin`,
`_tone_convert.to_initials`, `tone3_to_tone`, `tone_to_normal`), the
`@register` wrapper (the public name `style.initials.convert` is the
wrapper; nothing in the package calls it), `_utils.has_finals`,
`utils._replace_tone2_style_dict_to_default`, `runner.NullWriter.write`
(judgement 8), and `compat.callable_check` (F2). A search of the package
found no caller of any of them. Each keeps the edges of its body (rule A),
except under F2.

**Special methods.** `PrefixSet.__contains__` (one accepted site) and the
six `__init__` methods. Every class instantiation is right: the seven
style converter classes and `NullWriter` (no edge, `object.__init__`), the
three private converters (`DefaultConverter.__init__`); `PinyinNotFoundException` names
`<builtin>.Exception.__init__` (the trace alias of
`<builtin>.BaseException.__init__`). No property, `__getattr__`,
`__iter__`, `__call__` or `__set_name__` exists in the package.

**Rejections and notes.** I read all 70 rejection lines, the exclusion and
all 39 notes. Each reason holds.

**Outside callees.** 65 names. Each matches the trace's canonical name or
an alias, or the conventions (`<builtin>.hasattr`, `logging.disable`, and
the two Python 2 names of judgement 1, which the trace cannot see).

**Rejected trace edges.** All 5 come from the test classes
`MyConverter`, `HerConverter`, `TheyConverter`
(`tests/contrib/test_neutral_tone.py:13-23`, `test_tone_sandhi.py:13`,
`test_uv.py:10`). They stay rejected (judgement 5).

**Edges from reading only.** All 23 can happen: the `__main__` blocks of
`__main__.py`, `runner.py` and `toneconvert.py` (3), the 14 edges of
`runner.main` (the tests call only its parser, `tests/test_cmd.py:22, 32`),
`toneconvert.main -> <builtin>.list.append` (stdin is empty in the tests),
the wrapper -> `initials.convert`, `_replace_tone2_style_dict_to_default`,
`Converter.convert` (judgement 4), the Python 2 `str.encode` (judgement 1),
and `callable_check -> hasattr` (F2: the one that cannot happen on a
supported version).

## README and tools

- The README does not say how to name callees of Python-2-only code
  (judgement 1), nor whether a function defined only in a fallback that no
  supported version takes keeps its body edges (judgement 2).
- The README does not say that `.pyi` stubs count as annotations for B2
  and B4; only the cachetools audit shows it (judgement 3).
- Rule A lists the reasons to reject a trace edge. A dispatch that a
  client class's MRO decides (judgement 5) fits "a value that a client
  supplied" only through B1; one sentence in rule A would make it explicit.
- `check.py` does not mark `args.func(args)` (`toneconvert.py:99`) as a
  value site, because `func` is set by `set_defaults(func=...)`, not by an
  assignment. The writer added a note. No change needed.
- The skeleton and report tools worked as the README describes.

## Interpreter metadata follow-up (2026-11-16)

Current declared language support is Python 2.7 and Python >=3.4,<4, not every
version accepted by setup.py's installer bound. CHANGELOG.rst:413-414 drops
the guarantee for 2.6/3.3. CPython, PyPy and explicitly supported IronPython
remain in scope (README.rst:15; CHANGELOG.rst:542; compat.py:12-17).

The SUPPORT_UCS4 notes now distinguish implementations. CPython 3.3+ has the
wide outcome. Pinned IronPython 3.4.2 returns .NET UTF-16 string Length from
Builtin.len and StringOps.__len__, so the U+20000 literal has length two and
constants.py:58 takes the narrow branch. Both existing re.compile relations
remain. The evidence supplement proves no new or removed pairs for the two
pinned IronPython releases. This is a metadata correction only; earlier
records remain unchanged and no target code was executed for this supplement.

## Same-function placement clarification (2026-11-16)

Original M1 is an allowed normalization, not a baseline metadata defect.
The callback at core.py:46:25 was already valid under README ruling 12;
the added list46:21 witness preserves its graph pair. Original M2-M4 remain
metadata corrections. The language-scope and Unicode-width fixes above are
two additional baseline groups, distinct from M1-M4. Thus pypinyin has five
baseline metadata correction groups and one allowed normalization.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).

## Fourth complete source-first audit (2026-11-16)

All 494 pairs, 1,643 source sites and 181 bodies were reviewed. No graph
change: 181 nodes, 494 pairs, 750 site-target relations. One baseline
metadata group corrects the stale Python 3.3 witness in the version note
at tools/toneconvert.py:71; admitted older witnesses are 2.7 and 3.4-3.6.
The explicit global supported-Python2 exception retains encode/decode;
a temporary auditor scope restriction was corrected separately and is
not a baseline finding. Normal/-O/-OO adds no pair. Earlier audit bytes
above remain intact.

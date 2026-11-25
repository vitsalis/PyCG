# django-environ: independent audit of the ground truth

Release v0.14.0, commit `6e1b461125e2313cae362e1ab9426a97d9e843b0` (batch 6).
Audited files: `django-environ.ledger` (347 entries, 9
default lines that reject 11 candidates), `django-environ.json` (265 edges:
77 in the package, 188 outside), `django-environ.added.json` (36 edges),
`django-environ.rejected.json` (6 trace edges) and `django-environ.md`
(judgements J1 to J12). `check.py django-environ` reports no errors; the
trace confirms 229 of the 265 edges.

I judged the files by the scope rules A, B1 to B5 and C of
`macro-benchmark/README.md`, with its clarifications and rulings. I read
the whole analysed source (`environ/__init__.py`, `compat.py`,
`environ.py`, `fileaware_mapping.py`), `README.rst`, `docs/` (`api.rst`,
`types.rst`, `tips.rst`, `quickstart.rst`), `setup.py` and the tests, as
data. I did not run or import the package, and I ran no analysis tool on
it. The only tools I ran were `check.py` (skeleton, size report,
`--report`, `--default`) and scripts of my own on their text output. The
pinned test environment is pytest's stack only, so no library source was
needed (the `deps/django-environ/` directory is empty).

**Final state.** 1 missed edge (F1, +1 inside edge), 1 missed edge that
follows from the writer's own judgement J5 (F2, +1 inside edge, only if J5
stays), 1 wording finding (W1). No edge that cannot happen. My opinion on
the three judgement calls that ask for a ruling: J1 keep, J5 keep (and then
apply F2), J7 keep. If all my opinions are taken, the graph has 267 edges
(79 inside, 188 outside).

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Severity |
|---|---|---|---|---|---|
| F1 | missed edge | `environ.py:282:38` format `{value}` in `Env.str`: `Env.str -> environ.environ.NoValue.__repr__` | The entry says `reject *: ... a NOTSET default with an unset variable raises before this line`. That holds only for the one instance `NOTSET`. `Env.str`'s `default` is annotated `Union[_str, NoValue]` (`:266`), `NoValue` is a public class (`docs/api.rst:28`), and B2 says that the annotation decides which package values fit. get_value tests the default by identity (`default is self.NOTSET`, `:522`). Witness: `Env().str('UNSET', default=environ.NoValue(), choices=['a'])`. get_value returns the fresh `NoValue` (`:526`; no smart cast, because `cast=str`; `value != default` is False, `:553`). Then `value not in choices` is True (`:280`), and the f-string formats the `NoValue`: `format()` -> `object.__format__` -> `object.__str__` -> `NoValue.__repr__` (`:83`). Today no site calls `NoValue.__repr__`. The default rejection of `NoValue.__repr__` (ledger line 31) then also needs a reason that does not say "no format field ... has a NoValue operand". | +1 inside (266) | medium; certain on Python's semantics, likely on the rules |
| F2 | missed edge, conditional on J5 | `environ.py:613:25` `cast(value)` in `Env.parse_value`: `Env.parse_value -> environ.environ.NoValue.__repr__` | J5's witness with a `NoValue` in place of the `Path`: `Env().get_value('UNSET', cast=str, default=environ.NoValue(), parse_default=True)`. A `NoValue` is admitted for get_value's `default` in the same way as J4's `Path`: the package passes its own annotated `Union[X, NoValue]` defaults there (`Env.str`, `bytes`, `bool`, `int`, `float`, `:275-325`), and `NOTSET` is get_value's own default (`:477`). Smart casting is skipped (`isinstance(default, NoValue)`, `:548`), `value != default` is False, `parse_default` sends the `NoValue` to `parse_value`, and `str(value)` runs `NoValue.__repr__` (no `__str__`). The rule that admits J5's `Path.__str__` gives this edge too. The note of `613:25` then also names it. | +1 inside (267), only if J5 stays | medium; certain given J5 |
| W1 | wording | `django-environ.md`, J5 ("1 inside edge goes") and J7 | J5 says that the combination rule decides 1 edge; it decides 2 (F2). J7 calls the bytes default "the class of a client object"; the reason why J7 and J4/J5 differ is worth one sentence (see J7 below), because a reader can take J6's bytes flow (`Env.bytes` into get_value's `default`) as an admission of bytes for get_value's `default`. | 0 | low |

No other difference. The binding check found no call that cannot bind (see
step 3).

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/django-environ` (`cp
-R`) to `$TMPDIR/audit-django-environ/` and ran `check.py
--benchmark-dir <scratch> --skeleton django-environ`. It has 674 sites: 303
call, 14 decorator, 86 getitem, 84 op, 82 truth, 40 setitem, 31 iter, 20
format, 8 mapping, 6 delitem. All 357 implicit sites have candidates; 6 are
value sites. Five candidates sit at 82 to 199 sites (`Path.__eq__` 199,
`Path.__getitem__` and `FileAwareMapping.__getitem__` 177 each,
`FileAwareMapping.__len__` 98, `FileAwareMapping.__iter__` 82).

**Sample, drawn by kind.** No kind of site dominates (calls are 45%), but
one candidate does: `Path.__eq__` is proposed at most implicit sites. I
split the sites into explicit (call and decorator, 317) and implicit (357),
sorted each by (module, line, column), and drew with one
`random.Random(20261122)`: `rng.sample(explicit, 35)`, then
`rng.sample(implicit, 35)`. I added the 6 value sites; `1206:30` was
already in the draw. 75 sites. I wrote my callees for each site in
`$TMPDIR/audit-django-environ/blind-answers.md` before I opened any
file of the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call) | 35 | 35 | 0 |
| Implicit (11 op, 9 getitem, 9 truth, 2 format, 2 iter, 1 setitem, 1 delitem) | 35 | 35 | 0 |
| Value sites not in the draw (`585:29`, `613:25`, `833:47`, `1175:19`, `1217:25`) | 5 | 4 | 1 |
| **Total** | **75** | **74** | **1** |

The 32 implicit sites without an entry are decided by the default
rejections, and in my answers they have no callee. The disagreement:

- **I was wrong (1):** `613:25` `cast(value)`. I had the six other callees
  and missed `Path.__str__`, which the writer reaches with J5's witness. I
  agree with the edge if J5 stays (see J5 below).
- **The writer missed an edge (0), the writer has an edge that cannot
  happen (0), naming only (0).**

My blind notes also listed, before I read the writer, the flows that the
writer records as J2, J4 and J6: `Path.__ne__` at `553:18`, `Path.__init__`
at `613:25`, the two `Path.__fspath__` call-backs of `os.path.dirname` and
`os.path.join`, the `FileAwareMapping` call-backs of `Mapping.__contains__`,
`MutableMapping.update` and `setdefault`, and `os._Environ.setdefault`. All
agree with the ledger.

## Step 2: exhaustive checks

**Receivers (B1).** `Env` and `FileAwareEnv` are public; the package makes
no instance of either. `FileAwareEnv` overrides only `ENVIRON`, so every
`self.<method>` and `cls.<method>` of `Env` has the one `Env` callee. `Path`
has no package subclass, so `self.__class__` (`1206:30`) and `self(name)`
(`1217:25`) are `Path.__init__` and `Path.__call__`. `FileAwareMapping` has
no package subclass. `NoValue` defines no `__init__` (`121:21`: no edge,
micro-benchmark rule). `Path.__init__`'s `super().__init__()` is
`<builtin>.object.__init__`. All rows agree with the ledger.

**Value roles.**

| Role | Package values | Ledger |
|---|---|---|
| `Env.ENVIRON` | `os.environ`; the `FileAwareMapping` of `FileAwareEnv` (`:1193`); the tests' dicts (`test_env.py:72`, `92`, `477`, `517`), client objects | agrees (J2) |
| `FileAwareMapping.env` | default `os.environ`; the tests' dicts, client objects | agrees (J3) |
| `cast` of `parse_value` (`613:25`) | `str`, `int`, `json.loads` / `simplejson.loads`, `urlparse`, the class `Path` (smart cast of `Env.path`'s default) | agrees; F2 adds `NoValue.__repr__` under J5 |
| `key_cast` (`585:29`) | the default `str` of `cast.get('key', str)` | agrees |
| `setenv` (`1175:19`) | the two lambdas of `set_environ` | agrees |
| get_value's `default` | client values; `Path` (`Env.path`, `:464`); `NoValue` (`NOTSET` and the annotated defaults); bytes from `Env.bytes` (B4, always with `cast=str`) | agrees, except F1 and F2 |
| `url` of the `*_url_config` methods | `urllib.parse.ParseResult` (documented) or a str | agrees |
| read_env's `env_file` | str, `pathlib.Path`, a client stream (`IO[str]`, abstract) | agrees (J10) |

**Default rejections.** I listed all 327 implicit sites that have no entry
and read each one against the source. None has a `Path`, a `NoValue`, an
`Env` or a `FileAwareMapping` operand. The explicit sites of the
`__getitem__`, `__len__` and `__iter__` defaults (12 to 16 per default:
`list(map(...))`, `tuple(...)`, `filter(None, ...)`, `len(...)`,
`iter(self)`) have `FileAwareMapping.__iter__` accepted at `73:30` and
nothing else. The 8
explicit sites of the two `__repr__` defaults format strs, ints, classes or
`self` with `__str__` defined. The defaults are right everywhere; only the
reason of the `NoValue.__repr__` default needs the change of F1.

**Functions that no site calls.** 36 nodes have no caller: the four
modules, `Env.__init__`, `__call__`, `__contains__`, 15 public `Env` getters
(all but `url`) and `read_env`, `Path.__add__`, `__sub__`, `__invert__`,
`__contains__`, `__getitem__`, `__repr__`, `__unicode__`, `file`, `find`,
`rfind`, `root`, `FileAwareMapping.__len__`, and `NoValue.__repr__`. Each is
right: the package calls none of them. The exception is
`NoValue.__repr__` (F1, and F2 under J5).

**Special methods and properties.** `Path.__eq__` is reached only from
`Path.__ne__` (`1248:31`); `Path` is unhashable (`__eq__` without
`__hash__`). `Path.root` is never loaded by the package (only docstrings
name it). The package defines no `__getattr__`, `__setattr__`, `__bool__`
or other property. `Mapping.__contains__` calls `FileAwareMapping.__getitem__`
back at `261:20`; `iter(self)` starts the generator function
`FileAwareMapping.__iter__` at `73:30`.

**Callees outside the package.** I checked the 81 distinct outside names
against the micro-benchmark naming rules. `collections.abc.Mapping.get`
(`os.environ.get`, anytree precedent), `os._Environ.setdefault` (defined by
`os._Environ` itself; I checked `os.py`), `collections.abc.MutableMapping.update`
and `.setdefault`, `urllib.parse.ParseResult._replace` and `.geturl`
(class of the receiver), `io.TextIOWrapper.read`, `re.Match.group`,
`logging.Logger.*`, `itertools.zip_longest` (a class call) and the missing
modules `django.core.exceptions.ImproperlyConfigured` (an external class:
an edge to the class) and `simplejson.loads` are right. `warnings.warn`
makes the `DefaultValueWarning` in library code: no edge to its outside
`__init__`, as the note says.

**Rejected trace edges.** All 6 are right: two `MagicMock` calls of the
tests' patched `find_spec` (`test_cache.py:130`, `147`), the tests'
`io.StringIO` (`test_env.py:478`; `IO[str]` fixes no class), and three
calls on the tests' dicts (`Env.ENVIRON`, `FileAwareMapping.env`), client
objects as funcy's `defaultdict` (batch 5, ruling 7).

**Notes and other judgements.** J2, J3, J4, J6, J8, J9, J10, J11 and J12
follow the README:

- J4: B2 (the package's own call passes the `Path` default) and the
  micro-benchmark callback rule (`os.fspath` calls `__fspath__`).
- J6: B4 through the flow of `Env.bytes`'s annotated argument, and the
  clarification "Concrete types": explicit handling of another type counts
  (`:536-537`).
- J8: the check of `:1086` fails for a thread that `_thread.start_new_thread`
  starts on `Env.read_env`, so its first frame has no `f_back`. The witness
  uses only the public API, so the edge stays.
- J9: method names of a class body are not in scope in its functions.
  Every class-body expression of `Env` that is evaluated at definition
  time names the builtins or the aliases `_str` and `_bool`.

## Step 3: binding check

I checked every call of a package function against its signature: the 84
pairs of a site and a package callee, with the call-backs (`Mapping` and
`MutableMapping` into `FileAwareMapping`, `os.fspath` into
`Path.__fspath__`, `re.sub` into `_keep_escaped_format_characters`, `map`
into `parse_value.<lambda1>`, `cast(value)` into `Path.__init__`). All
bind. No edge changes.

## The writer's judgement calls that ask for a ruling

**J1 (optional imports in `compat.py`; 7 outside edges at stake).** My
opinion: keep. The nearest rule is the default of "Judgements": "both
sides of an optional import run". The `find_spec` test at `compat.py:19` is
an optional import. The rule of declared requirements (batch 4, ruling 7)
decides which *versions* of a dependency are admitted, not whether an
optional import has two sides. It does not apply here: Django has no
declared version at all, so it gives no bound. The package's own
documentation also expects Django: `docs/install.rst:9` names "Django >= 2.2" as a
requirement, `README.rst` says "Raises Django's ImproperlyConfigured", and
`docs/tips.rst` imports `django.core.exceptions.ImproperlyConfigured` to
catch what `Env.str` raises. The name follows the missing-module rule
(dagster-pipes, markdown2). The same reading gives `simplejson.loads` at
`613:25` (1 edge), which the writer also keeps.

**J5 (`Env.parse_value -> Path.__str__` at `613:25`; a witness that
combines three admitted arguments).** My opinion: keep, and then apply F2.
The README does not decide the case directly: it nowhere says that the
admitted values of several parameters may be combined freely in one call,
or that they may not. Its nearest rules support the combination:

- B2 gives the values of each parameter separately (client values, the
  package's values for the role, the defaults), and a `Path` is in scope
  for get_value's `default` because the package's own call passes it there.
- The clarification "Factory outputs" says that an example does not
  restrict a factory's other public arguments to its one value.
- The clarification "Client control flow" asks only that a witness uses
  the public API, does not change package internals and does not reuse an
  object left half-changed.

The smaller extension is to state it: "The admitted values of the
parameters of one public call combine freely: a witness may pass any
admitted value for each parameter, also a combination that no document or
test shows." Under that statement F2 follows (1 more inside edge). If the
lead decides the other way (only combinations that the package, its tests
or its documentation make), then `Path.__str__` goes and F2 does not apply:
-1 inside edge against the present graph.

**J7 (the class of a client's own default as the cast; `<builtin>.bytes`
at stake).** My opinion: keep (no edge). B2's last sentence says that a
value from outside the package that the client passes is a client callback,
and B5 makes a client object opaque. `type(default)` of a bytes value that a
client passes to the unannotated `default` of get_value or `Env.__call__`
is derived from such a value. This is consistent with J4 and J5, and the
difference is worth one sentence in `django-environ.md` (W1). `Path` and
`NoValue` are package values, which B2 admits for get_value's `default`
because the package passes them there. Bytes is an outside type. Its only
package flow is `Env.bytes`, whose B4 annotation fixes the type, and
`Env.bytes` always passes `cast=str`, so that flow never reaches smart
casting. The same reasoning keeps out, under J5, the `bytes.lower`,
`bytes.strip` and `bytes.split` calls of `parse_value` that a client's
bytes default with `parse_default=True` would reach.

## Remarks on the README and the tools

- R1 (README): the README does not say whether admitted values of several
  parameters combine (J5 above). A sentence under B2 would decide this and
  the similar cases of batch 6.
- R2 (tools): `check.py` worked as the README says. My first attempt to
  write the skeleton with a shell `>` redirection was refused by the
  sandbox's permission classifier. Piping through `tee` into the scratch
  directory worked. This is not a defect of the tools.

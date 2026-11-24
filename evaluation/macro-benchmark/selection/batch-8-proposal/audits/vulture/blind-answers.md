# vulture: blind answers (seed 20261124)

Written from the source at `b0f67ba` (`$SHARED/macro-benchmark/projects/vulture`),
the README's rules, the micro-benchmark README and the CPython and PyPy
sources of `deps/` only, before any file of the writer was opened.

## Skeleton and draw

The skeleton was made without a ledger in a scratch copy
(`check.py --benchmark-dir <scratch> --skeleton vulture`): 23 modules, 97
functions, 1100 sites (350 call, 10 decorator, 627 getattr, 47 format, 35
getitem, 31 op); 926 with candidates; 12 value sites. Candidates at 50 or
more sites: `Whitelist.__getattr__` 631, `Item.__eq__` 70, `Item.__repr__`
59, `Item.__hash__` 55.

Sites are numbered by (module in skeleton order, line, column). Attribute
loads dominate (627 of 1100, each with the one candidate
`Whitelist.__getattr__`), so the draw is split by kind with one
`random.Random(20261124)`: `rng.sample(explicit, 50)`, then
`rng.sample(getattr, 10)`, then `rng.sample(other_implicit, 10)` (op,
getitem, format); then the 8 value sites the draw did not take (4 were
drawn). 78 sites. `draw.py` and `sample.txt` are beside this file.

## Facts the answers rely on

| Fact | Source |
|---|---|
| Python `>=3.9`; classifiers CPython and PyPy, 3.9 to 3.14 | `pyproject.toml:11`, `:23-30` |
| Platforms: CI on macOS, Linux and Windows | `.github/workflows/main.yml:18` |
| `Path()` gives a `PosixPath` or a `WindowsPath` | pathlib |
| `ast.NodeVisitor.visit_Constant` exists on CPython 3.9 to 3.13 and PyPy 3.9 to 3.11, not on 3.14 and 3.15; it looks up `visit_Num` etc. (absent on `Vulture`) and returns `self.generic_visit(node)` | `deps/cpython/3.13.18/Lib/ast.py:434-453`; `3.9.25/Lib/ast.py:421`; `pypy3.11-v7.3.23/lib-python/3/ast.py:430`; none in `3.14.10`, `3.15.2` |
| The only value of `Reachability._report` that the package makes: `partial(self._define, collection=self.unreachable_code, confidence=100)` | `core.py:220-225` |
| The `ignore` values of `_define`: `_ignore_import` (416), `_ignore_variable` (463), `_ignore_class` (560), `_ignore_method` (590), `_ignore_function` (594), and none (the partial, `_define` default) | `core.py` |
| `_match`'s `case`: False from `_is_test_file` (61) and `exclude_path` (276), True by default from `ignored` (439), `visit_ClassDef` (552), `visit_FunctionDef` (584) | `core.py` |
| `Whitelist` has only `__getattr__`; its one instance is `whitelist_node_visitor` in `ast_whitelist.py:4`, through `from whitelist_utils import Whitelist` | `whitelists/whitelist_utils.py:20-30`, `whitelists/ast_whitelist.py:1-4` |
| The whitelists are made to be executed (docstring of `Whitelist`), and the package's own test runs each one as a script with `cwd=REPO` (`tests/test_script.py:34-37`): `sys.path[0]` is then `vulture/whitelists/`, so `whitelist_utils` imports | `whitelist_utils.py:24-25` |

Judgement (mine, for the comparison): `vulture.whitelists.ast_whitelist`
runs as the script that its docstring and the package's own test run, so
each `whitelist_node_visitor.visit_X` load calls `Whitelist.__getattr__`
(67 sites, one edge `vulture.whitelists.ast_whitelist ->
vulture.whitelists.whitelist_utils.Whitelist.__getattr__`). Imported as
`vulture.whitelists.ast_whitelist`, line 1 would raise
`ModuleNotFoundError`; the rule on an import of a module "that the checkout
lacks" (README "Judgements") does not apply, because the checkout has
`whitelist_utils.py` where the script's import finds it. Every other
attribute load in the package is on a module, an AST node, a package
object without `__getattr__`, or a library object: `Whitelist.__getattr__`
rejected.

## Answers

`->` a callee; `reject` a candidate with the reason. Outside callees are
named by the micro-benchmark rules.

### Explicit sites (50)

| # | Site | Callees | Rejected |
|---|---|---|---|
| 1 | `__main__.py:3:5` `main()` | `vulture.core.main` | |
| 3 | `config.py:40:33` `data.items()` | `<builtin>.dict.items` (a TOML table from `tomllib.load` / tomli, or `cli_args`; a non-dict `tool.vulture` fails at `.items` before a call) | |
| 27 | `config.py:102:29` `exclude.split(",")` | `<builtin>.str.split` (argparse calls `csv` on argument strings; defaults are `missing`, not strings, so not converted) | |
| 32 | `config.py:108:24` `parser.add_argument("paths", ...)` | `argparse.ArgumentParser.add_argument` | |
| 49 | `config.py:163:24` `parser.add_argument("--config", type=str, ...)` | `argparse.ArgumentParser.add_argument` | |
| 60 | `config.py:196:29` `_parse_args(argv)` | `vulture.config._parse_args` | |
| 72 | `config.py:210:37` `str(toml_path)` | `<builtin>.str` | `Item.__repr__`: a `PosixPath` / `WindowsPath` |
| 74 | `config.py:215:18` `config.update(cli_config)` | `<builtin>.dict.update` | |
| 184 | `core.py:184:45` `other._tuple()` | `vulture.core.Item._tuple` (package comparisons are between Items: the `set()` of `_get_unused_items`) | |
| 185 | `core.py:187:20` `hash(self._tuple())` | `<builtin>.hash` | `Item.__hash__`: the tuple holds a Path, an int and a str |
| 187 | `core.py:187:32` `self._tuple()` | `vulture.core.Item._tuple` | |
| 195 | `core.py:204:40` `get_list("import")` | `vulture.core.Vulture.__init__.get_list` | |
| 203 | `core.py:215:29` `Path()` | `pathlib.Path` | |
| 213 | `core.py:230:42` `noqa.parse_noqa(self.code)` | `vulture.noqa.parse_noqa` | |
| 285 | `core.py:307:30` `self._log("Included whitelist:", path)` | `vulture.core.Vulture._log` | |
| 314 | `core.py:359:42` `item.get_whitelist_string()` | `vulture.core.Item.get_whitelist_string` | |
| 319 | `core.py:367:6` `@property` | `<builtin>.property` | |
| 323 | `core.py:371:6` `@property` | `<builtin>.property` | |
| 327 | `core.py:375:6` `@property` | `<builtin>.property` | |
| 332 | `core.py:381:33` `_get_unused_items(...)` | `vulture.core._get_unused_items` | |
| 336 | `core.py:385:33` `_get_unused_items(...)` | `vulture.core._get_unused_items` | |
| 353 | `core.py:403:22` `print(x.encode(), file=file)` | `<builtin>.print` | `Item.__repr__`: the argument is bytes |
| 366 | `core.py:416:25` `self._define(..., ignore=_ignore_import)` | `vulture.core.Vulture._define` | `_ignore_import`: data for `_define`, which calls it at 438:35 (`_define.ignored`) |
| 382 | `core.py:445:51` `lines.get_first_line_number(first_node)` | `vulture.lines.get_first_line_number` | |
| 409 | `core.py:481:24` `isinstance(node.ctx, ast.Load)` | `<builtin>.isinstance` | |
| 428 | `core.py:495:46` `re.findall(...)` | `re.findall` | |
| 466 | `core.py:514:56` `self._is_locals_call(kw.value)` | `vulture.core.Vulture._is_locals_call` | |
| 482 | `core.py:534:26` `re.sub(...)` | `re.sub` | |
| 595 | `core.py:632:26` `getattr(self, method, None)` | `<builtin>.getattr` | |
| 611 | `core.py:649:23` `self.visit(ast.parse(...))` | `vulture.core.Vulture.visit` | `Reachability.visit`: the receiver is a Vulture |
| 621 | `core.py:660:28` `isinstance(value, ast.AST)` | `<builtin>.isinstance` | |
| 624 | `core.py:661:27` `self.visit(value)` | `vulture.core.Vulture.visit` | `Reachability.visit`: the receiver is a Vulture |
| 642 | `core.py:678:23` `vulture.report(...)` | `vulture.core.Vulture.report` | |
| 675 | `reachability.py:9:42` `set()` | `<builtin>.set` | `Item.__eq__`, `Item.__hash__`: an empty set |
| 700 | `reachability.py:30:55` | `vulture.reachability.Reachability._can_fall_through_statements_analysis` | |
| 713 | `reachability.py:36:42` | `vulture.reachability.Reachability._handle_reachability_try` | |
| 729 | `reachability.py:59:33` `self._report(...)` (value) | `functools.partial.__call__`, `vulture.core.Vulture._define` (the partial of `core.py:220`; binds with `collection`, `confidence` and the keywords) | |
| 751 | `reachability.py:86:77` | `vulture.reachability.Reachability._can_fall_through_statements_analysis` | |
| 763 | `reachability.py:102:29` `self._report(...)` (value) | `functools.partial.__call__`, `vulture.core.Vulture._define` | |
| 780 | `reachability.py:133:30` `isinstance(node, ast.IfExp)` | `<builtin>.isinstance` | |
| 794 | `reachability.py:147:25` `self._report(...)` (value) | `functools.partial.__call__`, `vulture.core.Vulture._define` | |
| 805 | `reachability.py:159:29` `self._report(...)` (value) | `functools.partial.__call__`, `vulture.core.Vulture._define` | |
| 816 | `reachability.py:171:6` `@staticmethod` | `<builtin>.staticmethod` | |
| 827 | `reachability.py:193:44` `ast.iter_fields(stmt)` | `ast.iter_fields` | |
| 849 | `reachability.py:226:42` | `vulture.reachability.Reachability._mark_as_no_fall_through` | |
| 879 | `utils.py:69:18` `isinstance(decorator, ast.Call)` | `<builtin>.isinstance` | |
| 889 | `utils.py:76:21` `parts.append(decorator.id)` | `<builtin>.list.append` | `LoggingList.append`: `parts` is the list display of line 72 |
| 922 | `utils.py:122:18` `print(f'...')` | `<builtin>.print` | `Item.__repr__`: the argument is a str |
| 927 | `utils.py:123:14` `super()` | `<builtin>.super` | |
| 948 | `argparse_whitelist.py:6:39` `argparse.ArgumentDefaultsHelpFormatter("prog")` | `argparse.ArgumentDefaultsHelpFormatter` | |

### Attribute loads (10; the one candidate is `Whitelist.__getattr__`)

| # | Site | Decision |
|---|---|---|
| 427 | `core.py:495:39` `re.findall` | reject: a module |
| 456 | `core.py:511:23` `utils.is_ast_string` | reject: a module |
| 653 | `noqa.py:13:8` `re.IGNORECASE` | reject: a module |
| 813 | `reachability.py:169:14` `self._can_fall_through_statements_analysis` | reject: a Reachability |
| 815 | `reachability.py:169:57` `node.body` | reject: an AST node |
| 862 | `utils.py:39:60` `node.op` | reject: an AST node |
| 946 | `argparse_whitelist.py:5:48` `..._fill_text` | reject: an argparse formatter |
| 960 | `ast_whitelist.py:15:24` `whitelist_node_visitor.visit_BoolOp` | `-> Whitelist.__getattr__` (the judgement above) |
| 997 | `ast_whitelist.py:52:24` `whitelist_node_visitor.visit_Set` | `-> Whitelist.__getattr__` |
| 1096 | `unittest_whitelist.py:16:11` `mock.Mock.side_effect` | reject: a class attribute of `unittest.mock.Mock` |

### Other implicit sites (10)

| # | Site | Decision |
|---|---|---|
| 108 | `core.py:71:19` op `target.id == "__all__"` | reject `Item.__eq__`: a str |
| 133 | `core.py:146:56` format `{name}` | reject `Item.__repr__`: the package passes str names |
| 140 | `core.py:156:47` op `self.size == 1` | reject `Item.__eq__`: an int |
| 141 | `core.py:157:31` format `{self.size:d}` | reject `Item.__repr__`: an int |
| 252 | `core.py:269:29` op `char in pattern` | reject `Item.__eq__`, `__hash__`: str in str |
| 446 | `core.py:503:38` getitem `node.args[1]` | reject `Item.__eq__`, `__hash__`: a list, int key |
| 638 | `core.py:676:53` getitem `config["exclude"]` | reject `Item.__eq__`, `__hash__`: a dict, str key |
| 799 | `reachability.py:152:31` getitem `node.body[-1]` | reject `Item.__eq__`, `__hash__`: a list, int key |
| 899 | `utils.py:94:28` op `path.suffix == ".pyc"` | reject `Item.__eq__`: a str |
| 913 | `utils.py:101:31` format `{path}` | reject `Item.__repr__`: a Path |

### Value sites not drawn (8)

| # | Site | Callees |
|---|---|---|
| 96 | `core.py:57:20` `func(name, pattern)` | `fnmatch.fnmatch` (case False), `fnmatch.fnmatchcase` (case True) |
| 372 | `core.py:438:35` `ignore(self.filename, name)` | `vulture.core._ignore_import`, `_ignore_variable`, `_ignore_class`, `_ignore_method`, `_ignore_function` (None short-circuits) |
| 605 | `core.py:638:20` `visitor(node)` | the 12 `Vulture.visit_*`: `visit_arg`, `visit_AsyncFunctionDef`, `visit_Attribute`, `visit_BinOp`, `visit_Call`, `visit_ClassDef`, `visit_FunctionDef`, `visit_Import`, `visit_ImportFrom`, `visit_Name`, `visit_Assign`, `visit_MatchClass` (3.10 and later); and, for a `Constant` node on CPython 3.9 to 3.13 and PyPy, `ast.NodeVisitor.visit_Constant`, which calls back `vulture.core.Vulture.generic_visit` |
| 738 | `reachability.py:72:25` `self._report(...)` | `functools.partial.__call__`, `vulture.core.Vulture._define` |
| 757 | `reachability.py:94:29` | the same |
| 778 | `reachability.py:129:25` | the same |
| 789 | `reachability.py:139:25` | the same |
| 840 | `reachability.py:209:25` | the same |

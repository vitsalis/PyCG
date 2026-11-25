# flit-core: blind answers (84 sites, seed 20261124)

Written from the source (`flit_core/flit_core/` at eeaf9e7), the rules of
`macro-benchmark/README.md`, the micro-benchmark naming rules, the
batch 1 to 7 precedents and the trace, before any file of the writer was
opened.

Skeleton made without the ledger in a scratch copy
(`check.py --benchmark-dir <scratch> --skeleton flit-core`): 1086 sites,
952 explicit (941 `call`, 11 `decorator`) and 134 implicit (112
`format`, 22 `getattr`); 14 value sites. The explicit sites dominate
(88%), so the draw is split as tinytag's: 50 explicit and 20 implicit
sites from one `random.Random(20261124)` (explicit first), then the
value sites that the draw did not take: none of the 14 was drawn, so
all 14 are added (`draw.py`, `sample.txt`).

## Working assumptions

| Point | Assumption | Evidence |
|---|---|---|
| Runtime | CPython 3.8 and later, no PyPy | `pyproject.toml` `requires-python = '>=3.8'`, no implementation classifier; CI 3.8 to 3.14 |
| Platforms | Linux and Windows | no OS classifier; test jobs on `ubuntu-latest` and `windows-latest` (`.github/workflows/test.yml`) |
| TOML parser | `tomllib` on 3.11 and later, the vendored `flit_core.vendor.tomli` on 3.8 to 3.10; the inner fallback `import tomli` needs the vendored copy deleted (a change of package internals): not considered | `config.py:10-18` |
| `Path(...)` | callee `pathlib.Path`; methods of its instances `pathlib.PosixPath.*` and `pathlib.WindowsPath.*` | README "Outside names"; textdistance, pyfiglet, path |
| `log` | `logging.Logger` (`logging.getLogger(__name__)`) | each module's line `log = ...` |
| `@contextmanager` functions | a call runs `contextlib.contextmanager.helper`, which calls the generator function back | argcomplete `mute_stderr`, dagster-pipes |
| `@lru_cache` function | a call runs `functools._lru_cache_wrapper.__call__`, which calls the function on a miss (CPython only) | configargparse `is_quoted` |
| `VCSError.__str__`, `EntryPointsConflict.__str__` | candidates at every `format` and `str()` site; a `VCSError` is never made in flit_core and an `EntryPointsConflict` only by `LoadedConfig.add_scripts`; neither is formatted by any drawn site | `common.py:118-124`, `config.py:78-81`, `:233-238` |

## Answers

Numbers are the site numbers of `sample.txt`. "Reject __str__" means
`reject flit_core.common.VCSError.__str__,
flit_core.config.EntryPointsConflict.__str__`.

| # | Site | Callees | Decisions and reasons |
|---|---|---|---|
| 2 | buildapi 18:19 `Path('pyproject.toml')` | `pathlib.Path` | |
| 4 | buildapi 32:20 `Module(info.module, Path.cwd())` | `flit_core.common.Module.__init__` | binds (name, directory) |
| 30 | buildapi 79:43 `Path(wheel_directory)` | `pathlib.Path` | |
| 49 | common 55:37 `", ".join(map(str, sorted(existing)))` | `<builtin>.str.join` | `str` called back by join through the map is a builtin: no edge |
| 66 | common 103:35 `sorted(files)` | `<builtin>.sorted` | files: names from `os.walk` (str) |
| 72 | common 124:18 format `{self.msg}` | none | reject __str__: `msg` is the client's message passed to the public `VCSError`; a package exception there is B3 (any object) |
| 73 | common 124:30 format `{self.directory}` | none | reject __str__: as 72 |
| 84 | common 164:22 `isinstance(target, ast.Name)` | `<builtin>.isinstance` | |
| 89 | common 187:53 getattr `target.file` | `flit_core.common.Module.file` | target is a `Module` (callers: `get_info_from_module` from `make_metadata`); client objects opaque |
| 90 | common 188:26 `_module_load_ctx()` | `contextlib.contextmanager.helper`, `flit_core.common._module_load_ctx` | `@contextmanager` at 127: helper calls the generator function back |
| 166 | common 445:64 `self._normalise_field_name(...)` | `flit_core.common.Metadata._normalise_field_name` | self is a `Metadata`; no package subclass |
| 171 | common 450:21 `fp.write(f'License: ...')` | `io.TextIOWrapper.write`, `io.StringIO.write` | package streams: `open(..., 'w', encoding='utf-8')` (buildapi 60), `io.StringIO()` (sdist 257, wheel `_write_to_zip` 152); a client stream is opaque |
| 201 | common 507:75 `re.sub(...).lower()` | `<builtin>.str.lower` | `re.sub` of the `str` name returns a str |
| 202 | common 508:25 `check_version(version)` | `flit_core.common.check_version` | inside `assert`: runs without `-O` |
| 204 | common 510:32 format `{version}` | none | reject __str__: version is a str (annotation; `check_version` returned it equal) |
| 215 | config 75:28 `prep_toml_config(d, path)` | `flit_core.config.prep_toml_config` | |
| 226 | config 119:39 format `{loaded_cfg.module}` | none | reject __str__: a str or a TOML value of `[tool.flit.module] name` |
| 311 | config 319:48 `path_is_within_directory(file, project_dir)` | `flit_core.common.path_is_within_directory` | |
| 315 | config 325:29 `files.append(...)` | `<builtin>.list.append` | files = [] at 311 |
| 319 | config 328:82 format `{ex.args[0]}` | none | reject __str__: args[0] is the str message of a `ValueError` from glob or `relative_to`, or of the `ConfigError` of 320 |
| 320 | config 332:30 `ConfigError(...)` | `<builtin>.ValueError.__init__` | `ConfigError(ValueError)` defines no `__init__` |
| 352 | config 382:14 format `{name}` | none | reject __str__: str (split of the annotated str) |
| 353 | config 382:22 format `{annotation}` | none | reject __str__: str |
| 359 | config 393:34 format `{proj['name']}` | none | reject __str__: checked str at 391 |
| 368 | config 412:39 `lc.referenced_files.append(readme)` | `<builtin>.list.append` | `LoadedConfig.__init__` sets [] |
| 401 | config 488:46 format `{license_tbl['file']}` | none | reject __str__: a TOML value (str; `osp.normpath` at 481 refuses others) |
| 437 | config 556:32 `project_urls.append(...)` | `<builtin>.list.append` | list at 554 |
| 439 | config 556:44 format `{url}` | none | reject __str__: a TOML value |
| 511 | config 692:59 format `{unrec_keys}` | none | reject __str__: a set of str |
| 519 | config 704:35 format `{group_name}` | none | reject __str__: 'author' or 'maintainer'; any other object is B3 |
| 522 | config 708:25 `names.append(person['name'])` | `<builtin>.list.append` | |
| 537 | config 755:57 `invalid_msg.format(s=s, reason=reason)` | `<builtin>.str.format` | reject __str__: `s` and `reason` are str |
| 552 | config 775:29 `parts.append(part)` | `<builtin>.list.append` | |
| 555 | config 781:62 `normalise_license_exception(part)` | `flit_core.config.normalise_license_exception` | |
| 569 | config 810:24 `re.fullmatch(...)` | `re.fullmatch` | |
| 574 | config 828:18 format `{normalised_id}` | none | reject __str__: str from `licenses` |
| 596 | sdist 107:49 `_normalize_for_match(d)` | `flit_core.sdist._normalize_for_match` | |
| 612 | sdist 153:19 `cls(...)` (value) | `flit_core.sdist.SdistBuilder.__init__` | note: cls of the classmethod is `SdistBuilder` (buildapi 91); no package subclass; nine arguments bind |
| 638 | sdist 199:41 `osp.join(dirpath, d)` | `os.path.join` | |
| 653 | sdist 224:24 `str(target_dir)` | `<builtin>.str` | reject __str__: target_dir is the `Path` of buildapi 91 or a client value |
| 676 | sdist 257:33 `io.StringIO()` | `io.StringIO` | |
| 684 | sdist 262:23 `tf.addfile(ti, io.BytesIO(pkg_info))` | `tarfile.TarFile.addfile` | tf = `tarfile.TarFile(...)` at 232 |
| 699 | tomli._parser 31:47 `frozenset("\"'")` | `<builtin>.frozenset` | |
| 705 | tomli._parser 64:17 `loads(s, parse_float=parse_float)` | `flit_core.vendor.tomli._parser.loads` | |
| 722 | tomli._parser 159:37 `cont[k]["flags"].add(flag)` | `<builtin>.set.add` | the flags dicts hold `set()` or `{flag}` |
| 756 | tomli._parser 308:21 `out.flags.is_(key, Flags.FROZEN)` | `flit_core.vendor.tomli._parser.Flags.is_` | out = `Output(NestedDict(), Flags())` of `loads` |
| 758 | tomli._parser 309:75 format `{key}` | none | reject __str__: a tuple of str |
| 763 | tomli._parser 319:26 `src.startswith("]]", pos)` | `<builtin>.str.startswith` | src: str (`loads(s: str)`, `s.replace`) |
| 768 | tomli._parser 333:60 format `{abs_key_parent}` | none | reject __str__: a tuple of str |
| 793 | tomli._parser 415:41 `skip_comments_and_array_ws(src, pos)` | `flit_core.vendor.tomli._parser.skip_comments_and_array_ws` | |
| 796 | tomli._parser 425:26 `src.startswith("]", pos)` | `<builtin>.str.startswith` | |
| 814 | tomli._parser 476:35 `suffixed_err(...)` | `flit_core.vendor.tomli._parser.suffixed_err` | a `\ ` escape followed by text in a multi-line string |
| 827 | tomli._parser 503:27 `suffixed_err(...)` | `flit_core.vendor.tomli._parser.suffixed_err` | e.g. `\uD800` |
| 837 | tomli._parser 570:47 `parse_escapes(src, pos)` (value) | `flit_core.vendor.tomli._parser.parse_basic_str_escape`, `flit_core.vendor.tomli._parser.parse_basic_str_escape_multiline` | note: the local of 550/553, by `multiline`; both reached (one-line and multi-line basic strings) |
| 848 | tomli._parser 611:45 `match_to_datetime(datetime_match)` | `flit_core.vendor.tomli._re.match_to_datetime` | |
| 859 | tomli._parser 637:36 `parse_float(first_three)` (value) | `<builtin>.float` | note: the default `float` of `loads`/`load`; flit_core passes none; a client's callable is a client callback |
| 860 | tomli._parser 640:36 `parse_float(first_four)` (value) | `<builtin>.float` | as 859 |
| 885 | tomli._re 71:41 `cached_tz(...)` | `functools._lru_cache_wrapper.__call__`, `flit_core.vendor.tomli._re.cached_tz` | `@lru_cache(maxsize=None)` at 81; the wrapper calls `cached_tz` on a miss |
| 887 | tomli._re 81:2 `@lru_cache(maxsize=None)` (value) | `functools.lru_cache.decorating_function` | note: the value that `lru_cache(maxsize=None)` returns; it wraps `cached_tz` without calling it |
| 889 | tomli._re 84:20 `timezone(timedelta(...))` | `datetime.timezone` | |
| 901 | tomli._re 100:27 `parse_float(match.group())` (value) | `<builtin>.float` | note: as 859 (`match_to_number` gets `parse_float` from `parse_value` 624) |
| 906 | versionno 32:32 `re.compile(...)` | `re.compile` | |
| 913 | versionno 93:12 `add(...)` (value) | `<builtin>.list.append` | note: `add = components.append` (89), components = [] |
| 916 | versionno 94:8 `add(...)` (value) | `<builtin>.list.append` | as 913 |
| 922 | versionno 99:46 `str(int(pre_n))` | `<builtin>.str` | reject __str__: an int |
| 924 | versionno 100:12 `add(pre_l + pre_n)` (value) | `<builtin>.list.append` | as 913 |
| 926 | versionno 104:12 `add(...)` (value) | `<builtin>.list.append` | as 913 |
| 927 | versionno 104:26 `str(int(post_n1))` | `<builtin>.str` | reject __str__: an int |
| 930 | versionno 106:53 `int(post_n2)` | `<builtin>.int` | |
| 931 | versionno 107:12 `add(...)` (value) | `<builtin>.list.append` | as 913 |
| 937 | versionno 112:12 `add('.dev' + dev_n)` (value) | `<builtin>.list.append` | as 913 |
| 945 | versionno 119:12 `add('+' + ...)` (value) | `<builtin>.list.append` | as 913 |
| 956 | wheel 54:17 `log.info(...)` | `logging.Logger.info` | |
| 961 | wheel 82:6 `@classmethod` | `<builtin>.classmethod` | |
| 965 | wheel 90:19 `cls(...)` (value) | `flit_core.wheel.WheelBuilder.__init__` | note: cls is `WheelBuilder` (`make_wheel_in` 231); no package subclass; six arguments bind |
| 973 | wheel 105:18 `log.debug(...)` | `logging.Logger.debug` | |
| 1014 | wheel 173:48 `self.module.iter_files()` | `flit_core.common.Module.iter_files` | a generator function; self.module is a `Module` |
| 1016 | wheel 175:27 `self._add_file(full_path, rel_path)` | `flit_core.wheel.WheelBuilder._add_file` | |
| 1023 | wheel 184:39 `os.path.relpath(...)` | `os.path.relpath` | |
| 1033 | wheel 195:53 format `{self.dist_info}` | none | reject __str__: the property returns a str |
| 1037 | wheel 197:35 format `{self.dist_info}` | none | reject __str__: as 1033 |
| 1051 | wheel 209:49 format `{hash}` | none | reject __str__: the str digest of `records` |
| 1061 | wheel 228:39 `tempfile.mkstemp(...)` | `tempfile.mkstemp` | |
| 1069 | wheel 240:43 getattr `wb.wheel_filename` | `flit_core.wheel.WheelBuilder.wheel_filename` | wb is the `WheelBuilder` of 231 |

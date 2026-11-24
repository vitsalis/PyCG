# nodeenv: blind answers of the audit (seed 20261124)

Written from the source (`nodeenv.py` at `cb7fc97`), `setup.py`, `tox.ini`,
`README.rst`, `CHANGES`, `.github/workflows/tests.yml`, the dependency
sources (shtab 1.13.0, CPython `Lib/`) and the rules of
`macro-benchmark/README.md`, before any file of the writer was opened. The
trace (`dynamic/nodeenv.json`) was read for names only.

## Skeleton and draw

The skeleton made without a ledger in a scratch copy has 598 sites, all
explicit (595 call, 3 decorator; no implicit site has a candidate: the
package has two classes, `Config` and `PrintCompletionAction`), 76 value
sites. No kind dominates against another, so the draw is one stratum:
`rng.sample(explicit, 70)` with `random.Random(20261124)`, then every value
site not drawn (64; 12 value sites were drawn). 134 sites. `draw.py`
(arguments: the skeleton and `check.py --report` of the skeleton) prints
`sample.txt`.

## Facts the answers rely on

| Fact | Evidence |
|---|---|
| CPython 3.10 to 3.14 only | `setup.py:44` `python_requires='>=3.10'`, classifiers 3.10 to 3.14 and `Implementation :: CPython` |
| Linux, macOS, Windows, Cygwin and MSYS are supported | `tests.yml` matrix (ubuntu, macos, windows), `CHANGES:332` "Support for Cygwin", `CHANGES:255` "Added support for MSYS2", `README.rst:443` |
| `join` is `os.path.join`, `abspath` is `os.path.abspath` | `nodeenv.py:44-45`; named by the imported path |
| `logger` is a `logging.Logger` | `nodeenv.py:424`, `create_logger` returns `logging.getLogger("nodeenv")` |
| Every `logging.StreamHandler` emits through the package's `create_logger.emit` | `nodeenv.py:407` assigns it to `logging.StreamHandler.emit`; the package's handler `ch` is a `StreamHandler` on the default `sys.stderr` (`nodeenv.py:410`, `420`) |
| A `logger.info`, `.warning`, `.error`, `.critical` call reaches `emit` (callback of the logging call, B5); `logger.debug` never does | the level of the `nodeenv` logger is `INFO` (`nodeenv.py:399`) and nothing in the package, its tests or its documentation lowers it; the handler's level is `DEBUG` |
| `emit`'s receiver is the package's handler: `self.format` is `logging.StreamHandler.format`, `self.stream.write` is `io.TextIOWrapper.write`, `self.flush` is `logging.StreamHandler.flush` | not in the sample; the receivers of pytest's capture handlers are client objects |
| The operators that `_comparator_constraints` produces are `>=`, `<`, `<=`, `>`; never `=` | `nodeenv.py:262-297`; `match_node_range`'s documented input is "the parsed alternatives" (B3: a hand-built range with `=` is a value the package never produces) |
| A `tarfile_open(...)` call goes through `contextlib.contextmanager.helper`, which calls the generator function `tarfile_open` | `nodeenv.py:896`; the micro-benchmark rule (`main -> main.managed`) |
| `tarfile.open` returns a `tarfile.TarFile` | `tarfile.open = TarFile.open`, a classmethod called on `TarFile` |
| `os.environ.copy()` returns a `dict` | CPython `Lib/os.py`, `_Environ.copy` returns `dict(self)` |
| `os.environ.get` is `collections.abc.Mapping.get` | README "Callees outside the package" (anytree precedent) |
| shtab is installed (extra `completion`, in the trace environment): its names are real paths | `setup.py:42`, `requirements/nodeenv.installed.txt` |
| shtab's `complete` reads the parser's actions and calls no package code | `shtab/__init__.py` (no call of an action) |

## Answers

Format: `line:col kind  text` / callees (`->`) / decisions on the
skeleton's candidates / note. Callees outside the package are named by the
micro-benchmark rules.

### Drawn (70)

1. `49:28` `platform.system()` -> `platform.system`.
2. `92:6` `@classmethod` -> `<builtin>.classmethod`.
3. `136:61` `v_file.readline().strip()` -> `<builtin>.str.strip` (text-mode
   file, `readline` returns `str`).
4. `144:14` `print(...)` in `Config._dump` -> `<builtin>.print`.
5. `144:37` value `"\n    ".join(...)` -> `<builtin>.str.join`. Value site
   by name only (`join` is a module name); the receiver is a literal.
6. `168:29` `env.split(':')` -> `<builtin>.str.split` (the package passes
   `os.environ['PATH']`, a `str`; no other type is documented or handled).
7. `228:35` `_EXACT_VERSION_RE.match(version_str)` -> `re.Pattern.match`
   (3.10 and later only: no `_sre.SRE_Pattern`).
8. `328:19` `len(tokens)` -> `<builtin>.len`.
9. `335:40` `_parse_comparator(token)` -> `nodeenv._parse_comparator`
   (binds one argument).
10. `341:31` `constraints.extend(group)` -> `<builtin>.list.extend`.
11. `442:25` `parser.error(...)` -> `argparse.ArgumentParser.error`
    (argparse passes the parser that holds the action; the `except
    ImportError` side of an optional import runs).
12. `513:28` `parser.add_argument('--load-average', ...)` ->
    `argparse.ArgumentParser.add_argument` (non-Windows branch runs).
13. `594:24` `parser.add_argument('--npm', ...)` ->
    `argparse.ArgumentParser.add_argument`.
14. `607:24` `parser.add_argument('--isolate-npm', ...)` ->
    `argparse.ArgumentParser.add_argument`.
15. `619:24` `parser.add_argument('--clean-src', ...)` ->
    `argparse.ArgumentParser.add_argument`.
16. `675:29` `parser.parse_args()` -> `argparse.ArgumentParser.parse_args`,
    `nodeenv.PrintCompletionAction.__call__` (argparse calls the action of
    `--print-completion` back); reject `nodeenv.parse_args`: the receiver
    is an `ArgumentParser`.
17. `714:13` `os.chmod(filename, mode_0755)` -> `os.chmod`.
18. `725:22` `isinstance(content, bytes)` -> `<builtin>.isinstance`.
19. `728:21` value `logger.debug(...)` -> `logging.Logger.debug`; no
    `emit` (level `INFO`).
20. `736:23` `f.read()` (`open(dest, 'rb')`) -> `io.BufferedReader.read`.
21. `761:22` `open(dest, 'wb')` -> `<builtin>.open`.
22. `797:23` `env.update(extra_env)` -> `<builtin>.dict.update`
    (`os.environ.copy()` is a `dict`).
23. `803:32` `subprocess.Popen(...)` -> `subprocess.Popen`.
24. `820:50` `line.decode('utf8').rstrip()` -> `<builtin>.str.rstrip`.
25. `849:37` `host_gnu_type.startswith('x86_64-')` ->
    `<builtin>.str.startswith`.
26. `926:25` `sys.exit(1)` -> `sys.exit`.
27. `970:32` `dict(continued=True)` -> `<builtin>.dict`.
28. `978:40` `operator.methodcaller('getmembers')` ->
    `operator.methodcaller`.
29. `988:24` `re.match(rexp_string, member_name(member))` -> `re.match`.
30. `1009:23` `logger.warning(...)` -> `logging.Logger.warning`,
    `nodeenv.create_logger.emit` (the `except ImportError` side runs).
31. `1031:31` `urllib2.urlopen(req, context=context, timeout=...)` ->
    `urllib.request.urlopen`; reject `nodeenv.urlopen`: the module
    `urllib.request` is the receiver.
32. `1052:37` `unquote(parts.password or '')` -> `urllib.parse.unquote`.
33. `1081:37` value `', '.join(proxies)` -> `<builtin>.str.join`.
34. `1098:30` `os.path.islink(s)` -> `os.path.islink`.
35. `1116:14` `mkdir(dest)` -> `nodeenv.mkdir` (Cygwin branch; Cygwin is
    supported).
36. `1143:15` `len(value)` -> `<builtin>.len`.
37. `1161:25` value `logger.debug(...)` -> `logging.Logger.debug`.
38. `1185:16` `logger.info('.', extra=...)` -> `logging.Logger.info`,
    `nodeenv.create_logger.emit`.
39. `1227:25` `logger.error(...)` -> `logging.Logger.error`,
    `nodeenv.create_logger.emit`.
40. `1260:30` `errors.append((url, e))` -> `<builtin>.list.append`.
41. `1320:20` value `join(env_dir, 'Scripts')` -> `os.path.join`.
42. `1329:22` `os.path.exists(join(...))` -> `os.path.exists`.
43. `1333:22` `tarfile_open(fileobj=npm_contents)` ->
    `contextlib.contextmanager.helper`, `nodeenv.tarfile_open` (the
    decorator's helper calls the generator function).
44. `1335:28` `tarf.extractall(npm_src_dir, filter="data")` ->
    `tarfile.TarFile.extractall` (3.12 and later branch).
45. `1347:20` `shutil.copy(...)` -> `shutil.copy` (Cygwin branch).
46. `1349:24` `shutil.copytree(...)` -> `shutil.copytree`; reject
    `nodeenv.copytree`: the receiver is the module `shutil`.
47. `1362:42` `package.strip()` -> `<builtin>.str.strip` (lines of a
    text-mode file).
48. `1371:27` `dict(continued=True)` -> `<builtin>.dict`.
49. `1378:28` `_quote(activate_path)` -> `shlex.quote`.
50. `1425:25` `f.read()` (`'rb'`) -> `io.BufferedReader.read`.
51. `1464:70` value `os.path.abspath(env_dir)` -> `os.path.abspath`.
52. `1471:25` value `join(bin_dir, name)` -> `os.path.join`.
53. `1482:50` value `os.path.abspath(env_dir)` -> `os.path.abspath`.
54. `1485:34` `content.replace('__MOD_NAME__', mod_dir)` ->
    `<builtin>.str.replace`.
55. `1488:50` value `os.path.abspath(bin_dir)` -> `os.path.abspath`
    (Cygwin branch).
56. `1528:23` `os.symlink("node", shim_nodejs)` -> `os.symlink`.
57. `1537:23` value `join(env_dir, 'Scripts', 'predeactivate.ps1')` ->
    `os.path.join`.
58. `1552:21` `sys.exit(2)` -> `sys.exit`.
59. `1553:27` value `join(env_dir, 'src')` -> `os.path.join`.
60. `1557:14` `mkdir(join(env_dir, 'bin'))` -> `nodeenv.mkdir`.
61. `1574:25` `install_packages(env_dir, args)` -> `nodeenv.install_packages`.
62. `1597:54` `len(versions)` -> `<builtin>.len`.
63. `1600:30` value `'\t'.join(chunk)` -> `<builtin>.str.join`.
64. `1646:34` `_get_last_node_version()` -> `nodeenv._get_last_node_version`.
65. `1681:46` `max(matched)` -> `<builtin>.max`.
66. `1698:28` `os.environ.get('VIRTUAL_ENV')` -> `collections.abc.Mapping.get`.
67. `1757:44` `split_url_auth(src_base_url)` -> `nodeenv.split_url_auth`.
68. `1772:28` `logger.info(...)` -> `logging.Logger.info`,
    `nodeenv.create_logger.emit`.
69. `1783:65` `_is_exact_version(args.node)` -> `nodeenv._is_exact_version`.
70. `2403:9` `main()` -> `nodeenv.main` (the `__main__` block runs).

### Value sites not drawn (64)

71. `167:20` `':'.join(...)` -> `<builtin>.str.join`.
72. `353:27` `_OPERATORS[op](version, other)` -> `operator.ge`,
    `operator.gt`, `operator.le`, `operator.lt`; not `operator.eq` (the
    package never produces `=`; B3).
73. `375:19` `join(env_dir, ...)` -> `os.path.join`.
74. `376:20` `join(bin_dir, ...)` -> `os.path.join`.
75. `464:29` `shtab.complete(parser, values)` -> `shtab.complete` (value
    site by name: `action.complete` is assigned).
76. `704:21` `logger.debug(...)` -> `logging.Logger.debug`.
77. `706:21` `logger.debug('done.')` -> `logging.Logger.debug`.
78. `708:21` `logger.debug(...)` -> `logging.Logger.debug`.
79. `732:21` `logger.debug('done.')` -> `logging.Logger.debug`.
80. `738:25` `logger.debug(...)` -> `logging.Logger.debug`.
81. `784:24` `' '.join(cmd_parts)` -> `<builtin>.str.join`.
82. `785:17` `logger.debug(...)` -> `logging.Logger.debug`.
83. `788:23` `' '.join(cmd)` -> `<builtin>.str.join`.
84. `987:34` `members(archive)` -> `operator.methodcaller.__call__` (the
    `namelist` or `getmembers` that it calls is library code).
85. `988:49` `member_name(member)` -> `nodeenv.download_node_src.<lambda1>`
    (Windows, Cygwin, MSYS), `operator.attrgetter.__call__` (elsewhere).
86. `1090:25` `os.path.join(src, item)` -> `os.path.join`.
87. `1091:25` `os.path.join(dst, item)` -> `os.path.join`.
88. `1112:20` `join(env_dir, 'Scripts')` -> `os.path.join`.
89. `1115:20` `join(env_dir, 'bin')` -> `os.path.join`.
90. `1118:23` `join(env_dir, 'bin', 'node')` -> `os.path.join`.
91. `1124:18` `join(src_dir, src_folder)` -> `os.path.join`.
92. `1128:28` `join(env_dir, 'bin', filename)` -> `os.path.join`.
93. `1163:35` `join(src_dir, 'tmpbin')` -> `os.path.join`.
94. `1164:36` `join(node_tmpbin_dir, 'python')` -> `os.path.join`.
95. `1233:22` `abspath(env_dir)` -> `os.path.abspath`.
96. `1234:24` `join(src_dir, ...)` -> `os.path.join`.
97. `1290:28` `join(env_dir, 'bin', 'activate')` -> `os.path.join`.
98. to 115. `1321:29`, `1326:27`, `1327:23`, `1329:27`, `1330:23`,
    `1332:23`, `1339:19`, `1340:25`, `1341:21`, `1342:21`, `1343:21`,
    `1344:21`, `1347:25`, `1348:25`, `1349:29`, `1350:29`, `1351:25`,
    `1352:25` (18 sites of `install_npm_win`) -> `os.path.join` each.
116. `1372:25` `join(env_dir, 'bin', 'activate')` -> `os.path.join`.
117. to 124. `1443:23`, `1444:25`, `1445:27`, `1452:23`, `1453:25`,
    `1454:27`, `1463:57`, `1521:33` (`install_activate`) -> `os.path.join`
    each.
125. `1535:23` `join(...)` -> `os.path.join`.
126. `1541:23` `join(...)` -> `os.path.join`.
127. `1553:22` `abspath(join(env_dir, 'src'))` -> `os.path.abspath`.
128. `1557:19` `join(env_dir, 'bin')` -> `os.path.join`.
129. `1558:19` `join(env_dir, 'lib')` -> `os.path.join`.
130. `1559:19` `join(env_dir, 'lib', 'node_modules')` -> `os.path.join`.
131. `1572:17` `instfunc(env_dir, src_dir, args)` -> `nodeenv.install_npm`,
    `nodeenv.install_npm_win` (both bind three arguments; the platform
    decides).
132. `1626:17` `logger.debug(...)` -> `logging.Logger.debug`.
133. `1681:20` `'.'.join(...)` -> `<builtin>.str.join`.
134. `1767:48` `join(get_env_dir(args), 'bin')` -> `os.path.join`.

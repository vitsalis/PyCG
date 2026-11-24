# whitenoise: judgements of the ground truth

Release 6.12.0 (commit `1e3a30b`). Analysed source: `src/whitenoise/` (root
`src`): 12 modules, 82 functions (2 lambdas), 17 classes. `pyproject.toml`
sets `requires-python = ">=3.10"`, so the supported versions are 3.10 and
later. The package has no required dependency. The extra `brotli` adds
brotli. `middleware.py`, `storage.py` and `runserver_nostatic` import Django,
which the package does not declare; its classifiers name Django 4.2 to 6.0.

The fourth complete audit (2026-11-16) retains all 94 nodes and 327 pairs.
The pinned release explicitly declares CPython and Python >=3.10; no
alternative interpreter support was found. The final classifier is not an
upper bound. Under the working normal/-O/-OO union, all targets remain the
same: runtime source has no assert, __debug__ condition or own-docstring
lookup. This configuration union remains an unanswered working assumption.
The audit covers all 1,097 source sites, including 734 omitted implicit sites.

The ledger is `whitenoise.ledger`; the graph `whitenoise.json` is generated
from it. The rejected trace edges are in `whitenoise.rejected.json`.

**Django source.** The Django names and behaviour come from the Django 6.0.2
wheel that the test environment pins
(`django-6.0.2-py3-none-any.whl`, SHA-256
`610dd3b13d15ec3f1e1d257caedd751db8033c5ad8ea0e2d1219a8acf446ecc6`, the
copy that the security scan downloaded). It was read as a zip, never
imported or run. Files read: `http/response.py`,
`contrib/staticfiles/storage.py`, `contrib/staticfiles/finders.py`,
`contrib/staticfiles/apps.py`,
`contrib/staticfiles/management/commands/runserver.py`,
`core/management/base.py`, `core/management/commands/runserver.py`,
`core/handlers/base.py`, `core/files/storage/handler.py` and
`filesystem.py`, `utils/functional.py`, `utils/deconstruct.py`,
`conf/global_settings.py`. The later whole-benchmark audit also checked
the relevant Django 4.2 and 5.2 storage sources.

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) reviewed this
project under the same global rules as every other project. Its source-site
evidence is in whitenoise-review.json (audit record `2026-11-15/whitenoise-review.json`).

| Original edges | Removed | Added | Corrected edges |
|---:|---:|---:|---:|
| 323 | 0 | 4 | 327 |

- A `WhiteNoise` wrapper can directly wrap another `WhiteNoise`: both fit
  the documented WSGI application role.
- The unannotated public helpers `update_files_dictionary` and
  `make_helpful_exception` can receive bytes paths. Their library calls
  produce bytes that enter `bytes.replace` and `bytes.lstrip` before
  raising `TypeError`. The documented or annotated str path roles do not
  acquire bytes callees.
- A client `dry_run` value can change its truth value. The outer
  `post_process` loop can therefore enter Django hashing and call the
  package's `hashed_name` override.

## Architecture, as the ledger uses it

- `WhiteNoise` (`base.py`) is a WSGI application. `add_files` scans a
  directory and stores in `self.files` a `StaticFile` or a `Redirect`
  (`responders.py`) per URL. With `autorefresh`, `find_file` makes them per
  request. `serve` calls `get_response` of the stored object.
- `WhiteNoiseMiddleware` (`middleware.py`) subclasses `WhiteNoise`. It
  overrides `__init__`, `__call__`, `serve`, `candidate_paths_for_url` and
  `immutable_file_test`.
- `Compressor` (`compress.py`) writes `.gz` and `.br` files. `main` runs it
  over a directory with a `ThreadPoolExecutor`.
- `CompressedStaticFilesStorage` and `CompressedManifestStaticFilesStorage`
  (`storage.py`) subclass Django's `StaticFilesStorage` and
  `ManifestStaticFilesStorage`. Django's `collectstatic` calls their
  `post_process`.
- `runserver_nostatic/management/commands/runserver.py` picks the next
  runserver `Command` class when the module is imported, and subclasses it.

## Scope rules

`macro-benchmark/README.md` ("Scope rules") states the rules. This section
shows how the ledger applies them.

**A. Edges are per function.** Every function keeps the out-edges of its
body. Seven functions have no package caller (see the last section).

**B1. Receivers.**
- `self.serve(...)` in `WhiteNoise.__call__` (`base.py:84:30`): `self` is a
  `WhiteNoise`. `WhiteNoiseMiddleware` overrides `__call__` and never calls
  `WhiteNoise.__call__` on itself, so `WhiteNoiseMiddleware.serve` is
  rejected. In `WhiteNoiseMiddleware.__call__` (`middleware.py:122:30`)
  `WhiteNoise.serve` is rejected for the same reason.
- `self.candidate_paths_for_url(url)` in `find_file` (`base.py:140:49`):
  the middleware inherits `find_file` and calls it, so both methods are
  callees.
- `self.immutable_file_test(...)` in `add_cache_headers`
  (`base.py:233:36`): see "Value sites".
- `self.create_compressor(...)` (`storage.py:34:49`, `144:49`): the two
  storage classes do not derive from each other, so each site has only its
  own class's method.

**B2. Arguments and stored values.** Module-level functions and classes
and their methods are on public paths (rule C). Their parameters admit
client objects, package values for the role, and package defaults. The
private `_compress_path` functions and sorting-key lambda receive values
from their package callers. The regex lambda is exposed through the
documented `immutable_file_test` instance attribute and accepts arguments
for that predicate role; its captured regex comes from the constructor.
- `SlicedFile(fileobj, ...)`: the package passes the `io.BufferedReader`
  that `StaticFile.get_response` opens (`responders.py:86`, `111`). So
  `fileobj.seek`, `self.fileobj.read` and `self.fileobj.close` are
  `io.BufferedReader` methods, and `SlicedFile.read` and `SlicedFile.close`
  are rejected at those sites. The test passes a `BytesIO`
  (`test_responders.py:18`): a client object, rejected in the trace.
- `get_range_not_satisfiable_response(file_handle, ...)`
  (`responders.py:147:30`): `get_range_response` calls it (line 109)
  before it wraps the handle (line 111), so `file_handle` is the raw
  `io.BufferedReader` and `SlicedFile.close` is rejected.
- `Compressor(log=print)`: `print` is the package default of `log`. See
  "Value sites".

**B4. Concrete outside types.**
- The WSGI environ is a builtin dict (PEP 3333), as bottle's ground truth
  decides: `environ.get` is `<builtin>.dict.get` (`base.py:76:44`, `92:39`).
  So is Django's `request.META` (Django's documentation: "a dictionary"),
  which reaches `StaticFile.get_response`, `is_not_modified` and
  `get_path_and_headers` as `request_headers`.
- `PATH_INFO` and `HTTP_RANGE` are strs (PEP 3333): `<builtin>.str.encode`
  (`string_utils.py:8:28`), `<builtin>.str.strip` (`responders.py:128:50`).
- `extra_types` is typed `dict[str, str] | None`: `<builtin>.dict.update`
  (`media_types.py:12:34`).
- `parser` in `Command.add_arguments` is the `CommandParser` that Django's
  `BaseCommand.create_parser` makes (`core/management/base.py:308`, `375`):
  `django.core.management.base.CommandParser.get_default` and
  `set_defaults` (`runserver.py:49:30`, `50:32`). See judgement 1.

**B5. Client objects are opaque.** A client-defined WSGI application
(`base.py:82:36`) is opaque. A directly nested `WhiteNoise` is instead a
package value in the documented WSGI application role, so that site calls
`WhiteNoise.__call__`. The server's `start_response` (`90:23`) and
`wsgi.file_wrapper` (`93:32`), the client's `add_headers_function`
(`216:38`) and `immutable_file_test` function (`233:36`), and the
`get_response` handler that Django passes to the middleware
(`middleware.py:123:33`) remain opaque.

**C. Public.** The modules, module-level functions and classes, and
their methods have public paths. `middleware.__all__` lists only
`WhiteNoiseMiddleware`, but `__all__` does not decide rule C, so
`WhiteNoiseFileResponse` is public too. The two nested `_compress_path`
functions and the sorting-key lambda are private callbacks. The regex
lambda is accessible through the documented `immutable_file_test`
instance attribute, as `test_immutable_file_test_accepts_regex` shows;
its parameters retain that predicate role.

## Judgement calls

These are cases that the README does not decide in so many words. Each is
decided by the nearest rule; the lead may rule on them.

1. **Objects that Django passes to the package** (`middleware.py:123:33`,
   `runserver.py:49:30`, `50:32`, `responders.py` through
   `middleware.py:127:44`). By the nearest precedent (bottle: the server's
   environ is a dict by PEP 3333; its `start_response` is a client
   callable), a callable that the framework passes is a client callable,
   and an object whose type the framework's documented API fixes is named
   by that type. So `get_response` has no callee and the trace edge
   `WhiteNoiseMiddleware.__call__ ->
   django.core.handlers.exception.convert_exception_to_response.inner` is
   rejected; `request.META` is a dict; `parser` is a `CommandParser`.
2. **Library defaults behind the client's settings** (`middleware.py:139:45`,
   `197:43`; `runserver.py:48:30`). The package calls Django, and Django
   picks the object from the client's settings. The ledger names the
   objects that Django's own defaults or the package's documented setup
   give, and treats any other class that a setting names as client
   configuration (B5):
   - `finder.list(None)` (`139:45`): `STATICFILES_FINDERS` defaults to
     `FileSystemFinder` and `AppDirectoriesFinder`
     (`conf/global_settings.py:630-633`). `DefaultStorageFinder` is
     commented out there: not named.
   - `storage.path(path)` (`150:51`): the default finders yield
     `FileSystemStorage` objects: `django.core.files.storage.FileSystemStorage.path`.
   - `staticfiles_storage.url(name)` (`197:43`): the package's two storage
     classes (the documented backends, `docs/django.rst:90`, `100`),
     Django's default `StaticFilesStorage`, and the `ManifestStaticFilesStorage`
     backend explicitly shown in the troubleshooting instructions. The
     latter uses the already listed outside `ManifestStaticFilesStorage.url`
     name and adds no package override callback.
   - `super().add_arguments(parser)` (`runserver.py:48:30`): the
     documented setup puts `django.contrib.staticfiles` below the app
     (`docs/django.rst:220-225`), and `django.core` is the package's own
     fallback (`runserver.py:40`). Both runserver commands are named. A
     third-party runserver (Channels) is client configuration.
3. **The lazy staticfiles storage** (`middleware.py:197:40`).
   `staticfiles_storage` is Django's `ConfiguredStorage`, a `LazyObject`.
   Its first attribute load runs `_setup`, which makes the storage of
   `STORAGES["staticfiles"]` (`storages[...]`, `create_storage`,
   `storage_cls(**options)`). With the documented
   `CompressedManifestStaticFilesStorage`, its `__init__` runs. In a fresh
   process the middleware's own `__init__` makes the first load: `add_files`
   -> `get_static_file` -> `add_cache_headers` -> `immutable_file_test` ->
   `get_static_url`, for any file whose name has two dots (a hashed name,
   or `jquery.min.js`). By the fresh-process rule (sqlparse's
   `_TokenType.__getattr__`), `get_static_url ->
   CompressedManifestStaticFilesStorage.__init__` is an edge, at the
   attribute load. The tests run `collectstatic` first, so the trace does
   not have it. The site has no candidate by name; the entry was added by
   hand from `--without-candidates`.
4. **`hashed_name` called back through `url`** (`middleware.py:197:43`).
   For `CompressedManifestStaticFilesStorage` with `DEBUG` false,
   `HashedFilesMixin.url` calls `ManifestFilesMixin.stored_name`. With
   `manifest_strict` false (`WHITENOISE_MANIFEST_STRICT = False`,
   `docs/django.rst:491`; set in `storage.py:72-74`) and a name that the
   manifest lacks, `stored_name` calls `self.hashed_name`: the package
   override. If the file does not exist, `HashedFilesMixin.hashed_name`
   raises `ValueError`, which `get_static_url` catches; if it exists,
   `hashed_name` returns the hashed name and `url` returns a URL. The edge
   holds in both cases. Edge from reading only.
5. **Callbacks from Django's `post_process` generator**
   (`storage.py:98:45`). `super().post_process(...)` (`78:37`) only makes a
   generator. `post_process_with_compression` iterates it (`98:45`); the
   generator's body (`HashedFilesMixin.post_process`, `_post_process`,
   `_stored_name`) calls `self.hashed_name`, the package override. The
   callee is placed at the iteration site (the callback rule: the package
   scope whose action made the library code run). The trace has the edge.
   When `post_process` iterates the generator itself (`84:45`), an ordinary
   true `dry_run` stops Django hashing. A client object may instead test
   true at the outer check and false inside Django. That admitted input
   reaches `hashed_name`, so `84:45` also has the callback edge.
6. **`set_headers` called back by `FileResponse`** (`middleware.py:129:47`).
   `WhiteNoiseFileResponse` has no `__init__`; Django's
   `FileResponse.__init__` runs and, through the `streaming_content` setter,
   `_set_streaming_content` calls `self.set_headers(filelike)` when the
   content has `read` (`http/response.py:565-575`). The callee is named
   `django.http.FileResponse.__init__`, through the class that the module
   imports. The trace has both edges.
7. **Threads of a `ThreadPoolExecutor`** (`compress.py:186:40`,
   `storage.py:47:32`, `157:32`). `submit` starts the pool's worker
   threads, which call the submitted function. By the callback rule for
   threads, the function is a callee of the `submit` site:
   `Compressor.compress` and the two `_compress_path` functions. The trace
   misses these calls (T1: threads that a library starts). Each storage's
   generator expression runs inside `as_completed`; its calls belong to the
   enclosing function, at their own sites.
8. **Optional import** (`compress.py:10-15`): both sides run. With brotli
   installed (the extra), `compress_brotli` calls `brotli.compress`
   (`113:31`); `Compressor.compress` calls it only when `brotli_installed`
   is true.
9. **`if __name__ == "__main__":`** (`compress.py:197-198`): module code of
   `whitenoise.compress` (`python -m whitenoise.compress`):
   `<builtin>.SystemExit` and `main`.
10. **Version branches and annotations.** No branch tests the Python or
    Django version. Every module has `from __future__ import annotations`,
    so no annotation is a site. `finders.find` renamed its second parameter
    in Django 5.2 (`all` to `find_all`); the package passes one argument, so
    the call is the same on every version.

## Audit outcome and rulings (earlier audit)

The independent audit is `whitenoise.audit.md`. It re-derived 84 sites
blind (70 seeded and all 15 value sites); all 84 agree. The exhaustive
checks found no missing edge and no edge that cannot happen: the graph
stays at 323 edges. Three wording findings were applied: W1 (the ledger
notes at `middleware.py:139:45`, `197:40` and `197:43` now point to
judgements 2, 3 and 4), W2 (judgement 4: `hashed_name` raises only when the
file is missing) and W3 (the note at `middleware.py:129:47` also names the
302 and 416 responses without a file).

The lead's rulings (both as decided above; no edge changes):

- **L1** (judgement 1). A server or framework that calls the package is a
  client. A callable that it passes is a client callback: `get_response`
  has no callee, and the trace edge to
  `convert_exception_to_response.inner` stays rejected. An object whose
  type its documented API fixes is named by that type (B4): `request.META`
  is a dict, and the `parser` of `add_arguments` is Django's
  `CommandParser`.
- **L2** (judgement 2). When library code picks an object from the
  client's configuration, the library's defaults and the configurations
  that the package documents are in scope; any other configured class is
  client code.

## Default rejections and exclusions

None. No candidate is proposed at 50 or more sites (the size report lists
none), and no exclusion was needed.

## Value sites

15 sites, each with a note in the ledger.

| Site | Callees | Where the values come from |
|---|---|---|
| `base.py:82:36` `self.application(...)` | `WhiteNoise.__call__` | a directly nested WhiteNoise in the documented WSGI role; client-defined applications remain opaque (B2, B5) |
| `base.py:88:44`, `middleware.py:127:44` `static_file.get_response(...)` | `Redirect.get_response`, `StaticFile.get_response` | the values of `self.files` and of `find_file` |
| `base.py:90:23` `start_response(...)` | none | the server's callable (B5) |
| `base.py:93:32` `file_wrapper(...)` | `wsgiref.util.FileWrapper` | the package default; the server's `wsgi.file_wrapper` is opaque |
| `base.py:216:38` `self.add_headers_function(...)` | none | the client's function; a bare `Callable` annotation |
| `base.py:233:36` `self.immutable_file_test(...)` | `WhiteNoise.immutable_file_test`, `WhiteNoiseMiddleware.immutable_file_test`, `WhiteNoise.__init__.<lambda1>` | the class method of `self`, or the regex lambda of line 64 |
| `compress.py:123:21`, `127:21` `self.log(...)` | `Compressor.log`, `<builtin>.print` | the method when `quiet`, else the default `print` |
| `middleware.py:123:33` `self.get_response(...)` | none | Django's next handler (judgement 1) |
| `middleware.py:150:51` `storage.path(...)` | `django.core.files.storage.FileSystemStorage.path` | the default finders' storages (judgement 2) |
| `responders.py:274:40` `stat_function(...)` | `os.stat`, `<builtin>.dict.__getitem__` | `FileEntry.__init__`, line 262 |
| `storage.py:38:34` `self.path(...)` | `django.contrib.staticfiles.storage.StaticFilesStorage.path` | inherited by `CompressedStaticFilesStorage` |
| `storage.py:134:36`, `148:34` `self.path(...)` | `django.contrib.staticfiles.storage.ManifestStaticFilesStorage.path` | inherited by `CompressedManifestStaticFilesStorage` |

## Naming

- Methods that a package class inherits from Django are named through the
  base class that the package names: `ManifestStaticFilesStorage.path`,
  `.url`, `.clean_name`, `.hashed_name`, `.post_process`, `.__init__`;
  `StaticFilesStorage.path`, `.url`. The trace names them where they are
  defined (`HashedFilesMixin`, `ManifestFilesMixin`); the checker accepts
  both.
- `super().close()` in `SlicedFile` is `io.BufferedIOBase.close` (the trace:
  `_io._IOBase.close`).
- The exceptions without a package `__init__`: `<builtin>.Exception.__init__`
  for the classes of `responders.py`, `<builtin>.ValueError.__init__` for
  `storage.MissingFileError`.
- `os.scandir` entries: `os.DirEntry.is_dir`, `os.DirEntry.stat`.
- `argparse` methods through the receiver class:
  `argparse.ArgumentParser.add_argument`.

## Rejected trace edges

| Caller | Callee | Why |
|---|---|---|
| `WhiteNoise.__call__` | `wsgiref.simple_server.demo_app` | the tests' WSGI application |
| `WhiteNoise.serve` | `wsgiref.handlers.BaseHandler.start_response` | the tests' server's `start_response` |
| `WhiteNoiseMiddleware.__call__` | `django.core.handlers.exception.convert_exception_to_response.inner` | Django's `get_response` (judgement 1) |
| `SlicedFile.__init__` | `_io.BytesIO.seek` | the test's `BytesIO` |
| `SlicedFile.close` | `_io.BytesIO.close` | the test's `BytesIO` |

## Functions that no site calls

- Called only by a WSGI server or by Django (7):
  `WhiteNoiseMiddleware.__init__`, `WhiteNoiseMiddleware.__call__`,
  `SlicedFile.read` and `SlicedFile.close` (the server or Django's response
  reads and closes the file), `Command.add_arguments`, and the two
  `post_process` methods (`collectstatic`).
- All 82 functions ran in the tests.

## Statistics

| | Count |
|---|---|
| Sites | 360 (344 call, 15 decorator, 1 getattr) |
| Sites with candidates / value sites | 108 / 15 |
| Ledger entries | 363 |
| Callee lines / rejection lines / exclusion lines / notes | 379 / 19 / 0 / 56 |
| Default rejections | 0 |
| Nodes | 94 |
| Edges | 327: 99 in the package, 228 to 121 callees outside |
| Edges that the trace confirms | 308 of 327 (94.2%) |
| Edges only from reading | 19 |
| Trace edges rejected | 5 (of 313) |
| Functions that the tests run | 82 of 82 |

The 19 edges from reading only include the four additions above and these
15 earlier edges: the T1 thread callbacks (`main ->
Compressor.compress`, the two `-> _compress_path`); `get_static_url ->`
`CompressedManifestStaticFilesStorage.__init__`, `.hashed_name` and
`StaticFilesStorage.url` (judgements 2 to 4); `Command.add_arguments ->`
django.core's runserver `add_arguments`; `is_compressed_effectively ->
<builtin>.print`; `add_cache_headers -> WhiteNoise.__init__.<lambda1>`;
`whitenoise.compress -> <builtin>.SystemExit` and `-> main`;
`WhiteNoise.redirect -> <builtin>.ValueError`;
`StaticFile.parse_byte_range -> <builtin>.ValueError`;
`CompressedManifestStaticFilesStorage.post_process ->
make_helpful_exception`; `WhiteNoise.find_file -> <builtin>.str.endswith`
(`136:52`: the tests always set an index file).

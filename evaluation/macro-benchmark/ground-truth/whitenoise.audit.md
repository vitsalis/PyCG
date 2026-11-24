# whitenoise: independent audit of the ground truth

Release 6.12.0, commit `1e3a30bc9e6b82c79a03d35532a7ba72715918df` (held-out
set 4). Audited files, as commit `b278715` left them: `whitenoise.ledger`
(362 entries, 375 callee lines, 19 rejection lines of which 2 are
`reject *`, 0 exclusions, 53 notes), `whitenoise.json` (94 nodes, 323 edges:
97 in the package, 226 outside, 119 distinct outside callees),
`whitenoise.rejected.json` (5 edges) and `whitenoise.md`. `check.py
whitenoise` reports no errors. The trace confirms 308 edges; 15 come from
reading only. `--report` lists 0 trace edges that no site accounts for.

I judged the files by the README's conventions and scope rules (A, B1 to B5,
C) and by the lead's rulings on sets 3 and 4. I read the package source,
`docs/base.rst`, `docs/django.rst`, `docs/flask.rst` and the tests as data.
For Django I read the pinned wheel `django-6.0.2-py3-none-any.whl` (SHA-256
`610dd3b13d15ec3f1e1d257caedd751db8033c5ad8ea0e2d1219a8acf446ecc6`, equal to
the pin of `requirements/whitenoise.txt`) as a zip: `http/response.py`,
`contrib/staticfiles/storage.py`, `contrib/staticfiles/finders.py`,
`conf/global_settings.py`, `core/management/base.py`. I ran nothing of the
package or of Django, and no static analysis tool.

**Result.** No missing edge and no edge that cannot happen. The audit
changes 0 edges (323 stay). Three findings change wording only (W1 to W3).
Two judgement calls of the writer rest on rules that the README does not
state; I agree with both and propose a ruling (L1, L2). Two README remarks
(R1, R2).

## Findings

| Id | Kind | Site | Evidence | Edges | Decision |
|---|---|---|---|---|---|
| W1 | wording (low): stale cross-references | ledger notes at `middleware.py` 139:45, 197:40, 197:43 | The note at 139:45 says "see whitenoise.md, judgement 6"; the finders are judgement 2 (`whitenoise.md:126-137`). The notes at 197:40 and 197:43 say "judgement 7"; the lazy storage is judgement 3 and the `hashed_name` call back is judgement 4 (`whitenoise.md:146-168`). Judgement 7 is the thread pools. | 0 | open |
| W2 | wording (low): one case stated as the only one | `whitenoise.md` judgement 4 (`middleware.py:197:43`) | "`HashedFilesMixin.hashed_name` then raises `ValueError`, which `get_static_url` catches." It raises only if the file does not exist (`django/contrib/staticfiles/storage.py:144-147`). If the file exists but the manifest lacks its name, `hashed_name` opens it and returns the hashed name, and `url` returns a URL. The edge holds in both cases. | 0 | open |
| W3 | wording (low): incomplete list | ledger note at `middleware.py:129:47` | "For () (a HEAD request, a 304 or a 405 response) it is not called". A 302 (`Redirect`, `responders.py:239`) and a 416 (`responders.py:148-152`) also have `file=None`. The edge holds. | 0 | open |
| L1 | judgement that needs a ruling (no change) | judgement 1: `middleware.py:123:33`, `runserver.py:49:30`, `50:32`; `request.META` at `responders.py:89:43`, `211:44`, `226:46` | The README states the bottle precedent only in `bottle.md` (B4, B5): the WSGI environ is a dict by PEP 3333; the server's `start_response` is a client callable. The writer extends it to Django: the `get_response` handler that `BaseHandler.load_middleware` passes is a client callable, `request.META` is a dict (Django's documentation), and `parser` is the `CommandParser` that `BaseCommand.create_parser` makes (`core/management/base.py:302-308`). Note: that method's docstring says "``ArgumentParser``"; the object is a `CommandParser`, which inherits `get_default` and `set_defaults` from `argparse.ArgumentParser`, so the name by receiver class is right under either reading, and the trace confirms both edges. I agree. | 0 (1 rejected trace edge stays rejected) | proposed: state in B5 that a server or framework that calls the package is a client; a callable it passes is a client callback; an object whose type its documented API fixes is named by that type (B4) |
| L2 | judgement that needs a ruling (no change) | judgement 2: `middleware.py:139:45`, `150:51`, `197:43`; `runserver.py:48:30` | Django picks these objects from the client's settings. The writer names Django's defaults (`STATICFILES_FINDERS`, `conf/global_settings.py:630-633`; `STORAGES`, `:274-280`) and the package's documented setup (`docs/django.rst:87-100`, `:220-225`, and the fallback `runserver.py:40`), and treats any other configured class as client configuration. Only 3 edges rest on Django's defaults alone (`FileSystemFinder.list`, `AppDirectoriesFinder.list`, `FileSystemStorage.path`); the trace confirms all 3, and their callees are not client values (the test settings name no finder), so rule A keeps them in any case. I agree. | 0 | proposed: when library code picks an object from the client's configuration, the library's defaults and the configurations that the package documents are in scope; any other configured class is client code |
| R1 | README remark | "Limits of the site finder" | Two package callees sit at implicit sites that the skeleton leaves out, and the writer found both with `--without-candidates`: the first attribute load of Django's lazy `staticfiles_storage` runs `CompressedManifestStaticFilesStorage.__init__` (`middleware.py:197:40`); iterating the generator of Django's `post_process` runs the package's `hashed_name` (`storage.py:98:45`). The README names the lazy `map` and `filter` only. A sentence on lazy library objects (a `LazyObject` set up at its first attribute load, a library generator that calls package overrides when iterated) would point the next writer to these sites. | 0 | open |
| R2 | README remark | `macro-benchmark/README.md:598`; `macro-benchmark-heldout-4/projects.toml` header | The README says the set has "no ground truth yet"; the header of `projects.toml` says "It has no ground truth and no trace yet". Both are stale. | 0 | open |

## Step 1: blind re-derivation

**Skeleton without the ledger.** A scratch directory with a copy of
`projects.toml` and a `projects` link to `macro-benchmark-heldout-4/projects`;
`check.py --benchmark-dir <scratch> --skeleton whitenoise`: 360 sites (344
call, 15 decorator, 1 getattr), 15 value sites. I numbered the sites from 0
in (module, line, column) order and drew
`random.Random(20261111).sample(range(360), 70)`. One value site (#15,
`base.py:90:23`) was in the draw, so I added the other 14: 84 sites. No kind
dominates the skeleton (the site finder proposes candidates at only one
implicit site), so I did not draw by kind.

I wrote the callees of all 84 sites from the source, the documentation, the
tests and the Django wheel, before I opened any file of the writer. The file
of blind answers is evidence:
`$TMPDIR/heldout4-audit-whitenoise/blind.md` (with `draw.py`, `sample.txt`
and `skeleton.ledger` next to it). Before the comparison I had also derived
the four call backs through Django that the skeleton cannot show (the lazy
storage `__init__`, `hashed_name` through `url`, `set_headers` through
`FileResponse.__init__`, `hashed_name` at the iteration of Django's
`post_process` generator), and the three judgements of the writer on the
environ, the default finders and Django's `get_response`.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Seeded, not value sites | 69 | 69 | 0 |
| Value sites (1 seeded, 14 added) | 15 | 15 | 0 |
| **Total** | **84** | **84** | **0** |

Disagreements by class: writer missed an edge 0; writer edge that cannot
happen 0; naming only 0; auditor wrong 0.

## Step 2: exhaustive checks

**Dispatch (B1).** Every `self.m(...)` site over the hierarchy:
`WhiteNoiseMiddleware(WhiteNoise)` overrides `__init__`, `__call__`, `serve`,
`candidate_paths_for_url` and `immutable_file_test`; the two storage classes
do not derive from each other. Results equal to the ledger:
`base.py:84:30` and `middleware.py:122:30` each have only their own `serve`
(`WhiteNoise.__call__` runs only on a `WhiteNoise`); `base.py:140:49` has both
`candidate_paths_for_url` (the middleware inherits `find_file` and calls it at
`middleware.py:118`); `base.py:233:36` has both `immutable_file_test` methods
and the regex lambda; `storage.py:34:49` and `144:49` have only their own
`create_compressor`. All other self calls have one callee. The `super()`
sites are right: `middleware.py:75:25` and `160:48` reach `WhiteNoise`; the
storage `super()` calls and `SlicedFile.close` (`responders.py:66:22`) reach
Django or `io`.

**Value sites.** All 15 match my blind answers (table in `whitenoise.md`,
"Value sites"). The tests pass no package object as `application`,
`add_headers_function` or a callable `immutable_file_test`; `Compressor(log=
"test")` (`tests/test_compress.py:74`) is a client value that is never
called.

**Implicit sites without candidates** (737, `--report --without-candidates`).
I filtered them by kind (iter, with, mapping, class, setitem, delitem) and
read every getattr on a Django object. The package defines no `__iter__`,
`__enter__`, `__bool__`, `__len__`, `__eq__`, `__format__`, `__str__`,
`__repr__` or `__set_name__`. The only library code that calls package code
at an implicit site is at `storage.py:98:45` and `middleware.py:197:40`; both
entries are in the ledger. Iterating `finder.list(None)`, `get_finders()`,
`as_completed(...)` and the package generators calls no package function
(a resumed package generator is no edge). In a dry run, `storage.py:84:45`
iterates Django's generator, which returns at once
(`django/contrib/staticfiles/storage.py:290-291`): no callee, as the writer
says.

**Call backs through Django, checked in the wheel.**
`middleware.py:129:47`: `FileResponse.__init__` -> `StreamingHttpResponse`'s
`streaming_content` setter -> `FileResponse._set_streaming_content` ->
`self.set_headers(filelike)` when the content has `read`
(`http/response.py:454-458`, `496-497`, `565-575`). `middleware.py:197:43`:
`HashedFilesMixin.url` -> `_url` -> `ManifestFilesMixin.stored_name` ->
`self.hashed_name(name)` when `manifest_strict` is false and the manifest
lacks the name (`storage.py:170-205`, `517-527`); `WHITENOISE_MANIFEST_STRICT`
is documented (`docs/django.rst:491-508`) and set at `storage.py:72-74`.
`middleware.py:197:40`: in a fresh process the middleware's own `__init__`
makes the first load of `staticfiles_storage` (`add_files` ->
`get_static_file` -> `add_cache_headers` -> `immutable_file_test` ->
`get_static_url`, for a name whose `get_name_without_hash` differs);
Django's start-up only registers checks. `storage.py:98:45`:
`_post_process` calls `self.hashed_name` (`storage.py:356`, `391`) and
`_stored_name` through `url_converter` (`:422-432`). All four hold.

**Functions without a package caller.** The 8 of `whitenoise.md`
(`WhiteNoise.__call__`, `WhiteNoiseMiddleware.__init__` and `__call__`,
`SlicedFile.read` and `close`, `Command.add_arguments`, the two
`post_process`) are exactly the function nodes without a caller in the
graph. Each keeps the out-edges of its body (rule A). A server or Django's
response reads and closes a `SlicedFile`; a `__del__` that closes it is no
edge.

**Properties and special methods.** One property, `keep_only_hashed_files`,
loaded once (`storage.py:105:17`). The exception classes have no package
`__init__`: `<builtin>.Exception.__init__` (responders) and
`<builtin>.ValueError.__init__` (`storage.MissingFileError`) are right.

**Rejections and notes.** I read all 19 rejection lines and all 53 notes.
Every reason holds. Only W1 and W3 need new text.

**Outside callees.** All 119 names. Each is named by the receiver's class
or the path that the module imports (`posixpath.normpath`,
`posixpath.basename`, `django.http.FileResponse.__init__`), inherited Django
methods through the base that the package names, `os.DirEntry.is_dir` and
`.stat`, `io.BufferedReader` and `io.BufferedWriter` for `open` in binary
modes. The checker matches the 308 confirmed edges with the trace. The 6
outside edges from reading only are right: `<builtin>.ValueError` from
`redirect` (a client's `redirect` or `add_file_to_dictionary` arguments) and
from `parse_byte_range` (a range with other units), `<builtin>.SystemExit`
(`compress.py:198`), `<builtin>.print` (the default `log` of
`python -m whitenoise.compress`), `StaticFilesStorage.url` (also through the
documented `CompressedStaticFilesStorage`), and django.core's
`runserver.Command.add_arguments` (the package's fallback, `runserver.py:40`).

**The 15 edges from reading only.** All possible: the 3 thread call backs
(T1), the 3 `get_static_url` edges above, the 6 outside edges above,
`add_cache_headers -> WhiteNoise.__init__.<lambda1>` (a regex
`immutable_file_test`; the test calls the lambda directly,
`test_whitenoise.py:322-325`), `post_process -> make_helpful_exception`
(Django yields an exception, `storage.py:309-310`, `331`, `373`, `383`), and
`find_file -> <builtin>.str.endswith` (no index file; the tests always set
one).

**Rejected trace edges.** All 5 stay rejected: `demo_app` is the tests' WSGI
application (`test_whitenoise.py:55-56`); `BaseHandler.start_response` is the
tests' wsgiref server's; `convert_exception_to_response.inner` is Django's
`get_response` (L1); `_io.BytesIO.seek` and `.close` come from the test's
`BytesIO` (`test_responders.py:18-19`).

**The writer's judgement calls (`whitenoise.md`, 1 to 10).** 1 and 2: L1,
L2. 3 to 7: checked above; correct. 8 (optional brotli import), 9
(`__main__` block), 10 (no version branch; all modules have
`from __future__ import annotations`): correct. Neither the writer nor I read
Django 4.2 to 5.2, which the classifiers name; the brief fixes the pinned
6.0.2.

## Judgement

The ground truth is complete and precise: 84 of 84 blind sites agree, and
the exhaustive checks found no missing edge and no edge that cannot happen.
The writer resolved every call back through Django that the site finder
cannot see. Three notes need new text (W1 to W3). Two judgements apply
rules that the README does not state yet (L1, L2); the nearest rules support
the writer, and no edge depends on the ruling.


## Source-first exhaustive audit, round 3 (2026-11-16)

The auditor read all 12 scoped runtime files before opening the baseline and
froze the independent source model and hashed inventory. The inventory contains
82 functions and lambdas, 1097 scanner sites, and 359 explicit sites (344 calls
and 15 decorators). The global README was read first; its WhiteNoise examples
disclosed Django callback and configured-default rules.

The comparison checked all 327 baseline edges, all 379 site-target relations,
all 363 ledger entries, all 734 omitted scanner sites, every own-target argument
binding, and every zero-edge body. There are no default rejections. All five
rejected trace pairs remain client callbacks or client objects. No false
positive or missing edge was found. Historical audit text above is preserved.

Django base source confirms FileResponse's set_headers callback, the two
post_process iteration callbacks, and manifest storage's URL/constructor
callbacks. A FileResponse or FileWrapper constructor does not read the wrapped
SlicedFile merely by creating an iterator. Directly nested WhiteNoise wrappers
fit the documented WSGI application role. The Channels compatibility note
describes the extension point; it does not choose a Channels runserver class
in INSTALLED_APPS, so it adds no configured receiver beyond the documented
Django example and the package's core fallback. Imported os.path names retain
that path across platforms under the micro-benchmark naming rule.

This audit used static reading and AST/ledger infrastructure only. It did not
import or execute WhiteNoise, Django, their tests, or generated code, and did
not use PyCG or a trace as a semantic oracle. Structural, origin, and patch
replay checks are recorded in the round-3 review artifacts.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 complete source audit (2026-11-16)

A fresh auditor read all 12 runtime modules and froze the source model before
opening the baseline. Required global README examples and historical tables
were disclosed as prior exposure. Raw Django source was read independently;
no target, dependency, test or generated code was imported or executed.

All 327 baseline pairs (99 package, 228 outside), 379 site-target relations,
363 ledger entries and 734 omitted sites remain supported. The inventory has
1,097 sites, 344 calls and 15 decorators. All 94 nodes were reviewed,
including 15 zero-edge nodes. There are no default rejections or exclusions;
all 19 candidate-rejection lines and five rejected trace pairs were checked.

The frozen prose over-restricted the documented nested WSGI role and public
bytes-path helper inputs, missed the first lazy Django storage constructor,
and conflated package generator call ownership with callbacks from deferred
library code. Separate corrections retain the existing baseline targets.
They also correct a decorator-count typo and clarify B1 for the overridden
base __call__. None changes the frozen inventory or the graph.

The current judgement now states CPython >=3.10 and the working
normal/-O/-OO union. No source assertion or runtime docstring lookup changes
dispatch across those modes. Graph, ledger and both edge registers are
unchanged. Root runs the structural/origin gates after handoff; this audit
does not claim a semantic completeness theorem.

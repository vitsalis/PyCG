**1. The question.** When a public module privately re-exports an extension
type, should calls of its instances use the facade’s attribute, the type’s
`tp_name`, or the defining extension’s exported attribute? Here,
`functools._lru_cache_wrapper` is a private re-export of a type exported by
`_functools`, while the micro README explicitly illustrates instance calls
with `functools._lru_cache_wrapper.__call__`.

**2. The ruling.** **Reading A applies on the available inputs.** A private
re-export outside a public module’s `__all__` does not establish a public
class path. Where no public class alias exists, name an extension type
through the defining extension’s exported type attribute; use type-name
metadata only when that runtime provides no such attribute. Apply this
separately to each admitted runtime, retaining distinct implementations
but never two aliases for the same class on one runtime. Consequently,
CPython’s target is **`_functools._lru_cache_wrapper.__call__`**, while
PyPy’s Python closure remains `functools._lru_cache_wrapper.wrapper`.

The supplied CPython sources establish all three relevant facts:

| Fact | Evidence |
|---|---|
| `functools.__all__` excludes `_lru_cache_wrapper` | [3.10.22 `Lib/functools.py:12`](deps/cpython/3.10.22/Lib/functools.py:12) |
| `functools` imports the extension’s type, replacing its Python fallback | [3.10.22 `Lib/functools.py:642`](deps/cpython/3.10.22/Lib/functools.py:642); also 3.12.16:645 and 3.15.2:738 |
| `_functools` exports the type despite its facade-qualified type name | [3.10.22 `Modules/_functoolsmodule.c:1462`](deps/cpython/3.10.22/Modules/_functoolsmodule.c:1462), type name at :1419; [3.15.2 export at :1969](deps/cpython/3.15.2/Modules/_functoolsmodule.c:1969), type name at :1908 |

`PyModule_AddType` uses the type name’s final component for the attribute,
not its module prefix
([`Python/modsupport.c:704`](deps/cpython/3.10.22/Python/modsupport.c:704),
[`Objects/typeobject.c:487`](deps/cpython/3.10.22/Objects/typeobject.c:487)).

**Missing precedent:** “Rulings for the corrections of 2026-11-25” is absent
from both this checkout’s macro README and the supplied `b8-gt` checkout’s
macro README. This ruling is therefore provisional with respect to that
unavailable section; its text is needed to determine whether it introduces
a binding qualification.

**3. The edges.** For **every row below**, remove

`caller → functools._lru_cache_wrapper.__call__`

and add

`caller → _functools._lru_cache_wrapper.__call__`

at every listed site. These are **36 edge replacements across 40 sites in
13 packages**, with no net change in edge count. Source paths are relative
to `evaluation/macro-benchmark/projects/<package>/`; ledger references are
relative to `evaluation/macro-benchmark/ground-truth/`. Each pair also
occurs in the corresponding package’s ground-truth `.json`.

| Package | Caller | Source site(s) | Ledger evidence |
|---|---|---|---|
| configargparse | `configargparse.unquote_str` | `configargparse.py:599:17` | `configargparse.ledger:329` |
| configargparse | `configargparse.IniConfigParser.parse` | `configargparse.py:860:33` | `configargparse.ledger:458` |
| django-constance | `constance.migrations.0002_migrate_from_old_table._migrate_from_old_table` | `constance/migrations/0002_migrate_from_old_table.py:28:62` | `django-constance.ledger:1760` |
| einops | `einops.array_api.reduce` | `einops/array_api.py:17:48` | `einops.ledger:2401` |
| einops | `einops.array_api.pack` | `einops/array_api.py:53:60` | `einops.ledger:2430` |
| einops | `einops.array_api.unpack` | `einops/array_api.py:74:60` | `einops.ledger:2459` |
| einops | `einops.einops._apply_recipe` | `einops/einops.py:235:119` | `einops.ledger:2704` |
| einops | `einops.einops._apply_recipe_array_api` | `einops/einops.py:259:115` | `einops.ledger:2768` |
| einops | `einops.einops._prepare_recipes_for_all_dims` | `einops/einops.py:457:49` | `einops.ledger:2963` |
| einops | `einops.einops.reduce` | `einops/einops.py:539:48` | `einops.ledger:3004` |
| einops | `einops.einops.einsum` | `einops/einops.py:938:45` | `einops.ledger:3211` |
| einops | `einops.packing.pack` | `einops/packing.py:69:60` | `einops.ledger:3818` |
| einops | `einops.packing.unpack` | `einops/packing.py:138:60` | `einops.ledger:3879` |
| fastjsonschema | `fastjsonschema.ref_resolver.normalize` | `fastjsonschema/ref_resolver.py:52:29` | `fastjsonschema.ledger:1891` |
| fastjsonschema | `fastjsonschema.ref_resolver.resolve_remote` | `fastjsonschema/ref_resolver.py:64:31` | `fastjsonschema.ledger:1900` |
| flit-core | `flit_core.vendor.tomli._re.match_to_datetime` | `flit_core/flit_core/vendor/tomli/_re.py:71:41` | `flit-core.ledger:1961` |
| itables | `itables.sample_pandas_dfs.generate_random_series` | `src/itables/sample_pandas_dfs.py:350:33` | `itables.ledger:2427` |
| m3u8 | `m3u8.load` | `m3u8/__init__.py:93:16` | `m3u8.ledger:40` |
| m3u8 | `m3u8.mixins.BasePathMixin.absolute_uri` | `m3u8/mixins.py:12:43`, `15:24` | `m3u8.ledger:153`, `160` |
| markdown2 | `markdown2.GFMItalicAndBoldProcessor.delimiter_left_or_right` | `lib/markdown2.py:2904:45` | `markdown2.ledger:2035` |
| markdown2 | `markdown2.GFMItalicAndBoldProcessor.body_crosses_span_borders` | `lib/markdown2.py:2953:47` | `markdown2.ledger:2066` |
| more-itertools | `more_itertools.recipes._strong_probable_prime` | `more_itertools/recipes.py:1211:25` | `more-itertools.ledger:7436` |
| nodeenv | `nodeenv.split_url_auth` | `nodeenv.py:1048:21` | `nodeenv.ledger:716` |
| pyflakes | `pyflakes.checker.Checker.__init__` | `pyflakes/checker.py:739:56` | `pyflakes.ledger:671` |
| pyflakes | `pyflakes.checker.Checker.handleDoctests` | `pyflakes/checker.py:1259:53` | `pyflakes.ledger:1211` |
| tablib | `tablib.formats._xlsx.XLSXFormat.dset_sheet` | `src/tablib/formats/_xlsx.py:165:44` | `tablib.ledger:3991` |
| tablib | `tablib.formats._xlsx.XLSXFormat._adapt_column_width` | `src/tablib/formats/_xlsx.py:218:58` | `tablib.ledger:4039` |
| validators | `validators.hostname._port_validator` | `src/validators/hostname.py:37:23`, `43:23` | `validators.ledger:725`, `738` |
| validators | `validators.hostname.hostname._matches_simple_hostname` | `src/validators/hostname.py:123:38` | `validators.ledger:789` |
| validators | `validators.i18n.fi.fi_business_id` | `src/validators/i18n/fi.py:57:41` | `validators.ledger:899` |
| validators | `validators.i18n.fi.fi_ssn` | `src/validators/i18n/fi.py:95:44` | `validators.ledger:914` |
| validators | `validators.i18n.fr.fr_ssn` | `src/validators/i18n/fr.py:96:36` | `validators.ledger:952` |
| validators | `validators.uri._telnet_url` | `src/validators/uri.py:54:57` | `validators.ledger:1160` |
| validators | `validators.url._validate_auth_segment` | `src/validators/url.py:81:31`, `83:31`, `85:27` | `validators.ledger:1234`, `1241`, `1248` |
| validators | `validators.url._validate_optionals` | `src/validators/url.py:142:46` | `validators.ledger:1294` |
| validators | `validators.url.url` | `src/validators/url.py:240:57` | `validators.ledger:1314` |

The seven existing `.wrapper` edges in configargparse, markdown2,
more-itertools and pyflakes remain unchanged. They name Python closures,
not aliases of the C type.

**4. Earlier rulings and limits.** This follows the
[batch-7 private-class re-export ruling](evaluation/macro-benchmark/README.md:2922)
and the
[batch-8 exported-type-attribute ruling](evaluation/macro-benchmark/selection/batch-8-proposal/rulings/b8-ruling-c-type-names-1.md:5).
It applies their general rules to this conflict without narrowing either.
`_io._WindowsConsoleIO` remains correct for the same reason: its private
re-export in `io` supplies no public class alias. The difference in
`tp_name` spelling does not distinguish the cases, because batch 8 makes
the exported type attribute take precedence over that metadata.

**This ruling contradicts the micro README’s exact example at line 96.**
That example is global naming text, so the statement that “earlier usage
does not bind” cannot, by itself, dismiss it as a package judgement.
The example requires an explicit correction to conform to the applicable
private-re-export and C-type rulings.

Replace the “Calls of instances” bullet at
[micro README:94](evaluation/micro-benchmark/README.md:94)
with:

> **Calls of instances**: Calling an instance of a class outside the
> snippet calls `<class path>.__call__`, also when the class is private
> (`_functools._lru_cache_wrapper.__call__`,
> `typing._GenericAlias.__call__`). When no public class alias exists,
> a private re-export outside a public module’s `__all__` uses the
> defining module’s class path. For an extension type, use its exported
> type attribute before falling back to its type name. For an instance
> of a snippet class that inherits `__call__`, see Inherited methods
> (`contextlib.ContextDecorator.__call__`).

The macro README’s examples at lines 823 and 1936 need the same prefix
correction. The sole micro snippet whose expected graph contains the name
is
[`decorators/functools_cache/callgraph.json`](evaluation/micro-benchmark/snippets/decorators/functools_cache/callgraph.json:4);
this ruling makes no decision about that graph.

Apply this only to naming already-admitted calls. It does not admit new
receivers, create implicit outside edges, rename Python closures, or
replace public aliases such as `functools.partial`.

No files were changed, no package was run or imported, and no analysis-tool
output was consulted.
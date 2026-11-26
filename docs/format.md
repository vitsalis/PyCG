# Output format

PyCG writes one JSON document. It replaces the simple format, the FASTEN
format and the assignment-graph dump. The document is deterministic: the
same input gives the same bytes on every run and every supported Python
version. Object keys are sorted, lists are sorted as stated below, and the
text is compact (`json.dumps(..., sort_keys=True, separators=(",", ":"))`).

```json
{
  "format": "pycg/1",
  "tool": {"name": "pycg", "version": "1.0.0", "typeshed": "<commit>", "cap": 5000},
  "package": {"name": "pkg", "version": "2.1.0"},
  "modules": {
    "pkg.mod": {"file": "pkg/mod.py", "kind": "source", "status": "analysed"},
    "pkg.broken": {"file": "pkg/broken.py", "kind": "source", "status": "failed", "cause": "SyntaxError (line 3)"},
    "pkg._speedups": {"file": "pkg/_speedups.cpython-312-darwin.so", "kind": "extension"}
  },
  "definitions": {
    "pkg.mod": {"kind": "module", "module": "pkg.mod", "lines": [1, 40]},
    "pkg.mod.C": {"kind": "class", "module": "pkg.mod", "lines": [8, 30], "mro": ["pkg.mod.C", "pkg.base.B", "<builtin>.object"]},
    "pkg.mod.C.m": {"kind": "function", "module": "pkg.mod", "lines": [10, 20]}
  },
  "exports": {"pkg.C": ["pkg.mod.C"]},
  "outside": {
    "requests.Response.json": {"known": "stub"},
    "foo.get.bar": {"known": "name"},
    "pkg._speedups.escape": {"known": "extension"}
  },
  "calls": {
    "pkg.mod.C.m": [
      {"line": 12, "col": 8, "end": [12, 30], "callees": ["pkg.util.f", "requests.Response.json"]},
      {"line": 14, "col": 13, "end": [14, 17], "callees": ["pkg.mod.C.__iter__"], "implicit": "iteration"},
      {"line": 17, "col": 12, "end": [17, 34], "callees": [], "unresolved": "computed name"}
    ]
  }
}
```

## Parts

**`format`** names this format and its version. A reader refuses a version
that it does not know (`pycg.formats.edges` raises `ValueError`).

**`tool`** is the version of PyCG, the typeshed commit of its stub data,
and the cap of the analysis: the most values that it keeps for one node
(`--cap`, 5,000 by default), or `null` if there was none. The result
depends on the cap (see the cause `saturated`).

**`package`** is the name and version of the analysed package, as given on
the command line (`--package-name`, `--package-version`); each is `null`
when not given. PyCG does not read installed metadata: the output does not
depend on the environment.

**`modules`** has every module of the analysed package: each Python source
file that the analysis reached under the package root, and each extension
module that an import of the package or an entry point reaches there. A
binary file that neither reaches is not listed: PyCG does not search the
root for them. An entry point outside the package root, a stub (`.pyi`,
which is not source), a directory, or the `__init__.py` of the root (which
is not a package) is not analysed; PyCG warns. A file is known by its path
as written, not by what it is on the disk: a symbolic link to `a.py`
named `b.py` is the module `b` too, as for Python.

Several files can hold one module name. One rule picks the module's file,
for imports and entry points alike, whatever the order in which they reach
the files: the package (`a/__init__.py`), then the module file (`a.py`),
then the extension binaries (`a.so`, `a.abi3.so`, ...), by name, and
last the files that only an entry point names, which no import finds (a
script `a` without a suffix, `a.pyw`, `a.b.py` for the module `a.b`), by
their path. Python picks the package before the module file too, and
imports neither the module file then nor a binary that is not the first;
it tries a binary before a module file, where PyCG analyses the source. A
directory without `__init__.py` (a namespace package) holds the name only
when no file of it does.

- `file` is relative to the package root, with `/` separators.
- `shadows`, when present, lists the other files of the module's name,
  which the rule does not pick (`"shadows": ["a.py"]` beside
  `a/__init__.py`), sorted, relative to the root. PyCG does not analyse
  them.
- `kind` is `source` or `extension`. An extension is a binary module file
  (`name.cpython-*.so`, `name.abi3.so`, `name.so`, `name.pyd`: the name,
  an optional tag, then `.so` or `.pyd`) that an import of the package
  reaches, where no package directory (`name/__init__.py`) and no source
  file (`name.py`) of that name is. PyCG reads the file's name only. The
  module is outside code, named by its dotted name, and an attribute of
  its package.
- A source module has a `status`, and a `cause` unless it is `analysed`:
  - `analysed`: the analysis built the whole module;
  - `failed`: the file cannot be decoded or parsed. The module has no
    definitions but itself (with lines `[0, 0]`) and no calls;
  - `partial`: the analysis stopped before a top-level statement that
    nests deeper than it follows (247 levels, `docs/design.md`), with the
    cause `DeepNesting (line 3)`, the line of that statement. The
    definitions and calls of the statements before it are kept, and the
    module may call less than its code does.

  Nothing is dropped silently. The cause of a failed module is the type
  of the error, with its line or byte where Python gives one
  (`SyntaxError (line 3)`, `UnicodeDecodeError (byte 17)`, `SyntaxError`,
  `RecursionError`): not its message, so that it is the same on every
  version of Python.

**`definitions`** has every module, class and function (lambdas included)
that the analysed source defines, by qualified name: its `kind`, its
`module`, its first and last line, and for a class its `mro` (the names of
its linearization, outside classes included). Code that the analysis
proves cannot run defines nothing.

- A module's lines are `[1, n]`, `n` its number of lines as Python numbers
  them (the file is read with universal newlines, and only a newline ends
  a line: a form feed does not, though `str.splitlines` breaks there);
  `[0, 0]` for an empty module. A function's or class's lines are
  those of its `ast` node: from its `def` or `class` line (not its
  decorators) to its last line.
- The `mro` is the C3 linearization over the bases that the analysis
  knows. An analysed class is listed with its own bases. A base outside
  the package (`ext.Base`, `<builtin>.dict`) is one entry, at its place in
  the order; its own bases are outside code and are not listed. So
  `class X(ext.Base, A)` gives `["pkg.X", "ext.Base", "pkg.A"]`, and
  `class E(Exception)` gives `["pkg.E", "<builtin>.Exception"]`. Only a
  linearization without an outside class ends with `<builtin>.object`. A
  class with several possible hierarchies lists each class at its first
  position. An unknown class lists itself only: one whose base or
  metaclass may be more values than the analysis keeps for one node, or
  has a base that is an unknown class (see the cause `saturated`); nothing
  about it is known, and a call of it, or of what its instances give, is
  unresolved with the cause `saturated`.
- Of two definitions of one name, a module comes before a function, a
  function before a class (the call graph has no class nodes), and then
  the first by module and position.

**`exports`** maps an access path to the definitions it reaches: for each
module of the package, each name bound at the end of the module's code that
holds a module, class or function whose qualified name is not that path
(the values that the module-level name may hold, flow-insensitively).
`pkg.C` reaches `pkg.mod.C` after `from .mod import C` in
`pkg/__init__.py`. The targets are a sorted list (a conditional import can
give two); a target outside the package is an outside name. With this
table, graphs of several packages are joined without importing anything.

**`outside`** has every callee that is not a definition of the package,
with how PyCG knows it:

- `stub`: a function or method that the stub data or PyCG's models of the
  builtins declare (a builtin, the standard library, a third-party library
  with a stub). A function is named by the path through which the code
  reaches it (`os.path.join`, `requests.get`), a method of an outside value
  by the public name of its class (`requests.Response.json`). A name that
  the models of the builtins give to analysed code that does not define it
  is `stub` too (`functools.partial.__call__`, which an analysed
  `functools.wraps` returns);
- `name`: a name built from the access path of a value without a type
  (`foo.get.bar`): it need not exist under that name;
- `extension`: a name in an extension module of the package, by the
  module's dotted name.

**`calls`** is the call graph. Each key is a caller (a module or a function
of `definitions`); its value lists the call sites in the caller's code,
sorted by `line`, `col`, `end` and then `implicit` (a site without it
first). Calls in a class body or a comprehension belong to the function or
module around it.

The definitions of one qualified name (two `def f` in one module, a
property's getter and setter, or a module and a function `pkg.retry`)
share the name's entry, as in the classic call graph: the sites of each
are listed, and none replaces another. A site in another module than the
definition that `definitions` lists for the name has `module`, the module
whose code holds it; such sites come after the others, by `module`.

- `line` and `col` are the start of the `ast` node of the expression or
  statement that makes the call, and `end` is its end, `[line, col]` (as
  `ast`: lines from 1, columns from 0). For an implicit call the node is
  the one that the construct acts on, as the list below says. Two sites
  can start at one position (`f(x)(y)` and `a.b().c()` hold a call inside
  a call); their ends tell them apart. The calls of one node and one
  construct are one site, with their callees merged: a `for` loop's
  `__iter__` and `__next__` are one `iteration` site. Two exceptions to
  the position. A link of a comparison chain spans its left and right
  operands, which no `ast` node does (`a < b` and `b < c` in `a < b < c`;
  a comparison of one link is its whole expression). The accessor that a
  class's own attribute hook calls (`__setattr__` calls a property's
  setter) is an `attribute` site of the hook, at its `def` (the whole
  function), since Python's code that the hook's body runs makes that
  call.
- `callees` is the sorted list of what the site can call: definitions and
  outside names. A package function that library code calls back is a
  callee of the site that made the library call (`map(f, xs)`). So are the
  implicit calls that a builtin makes while it runs: `list(x)` iterates
  `x`, `str(x)` calls `__str__`, `len(x)` calls `__len__`, `getattr(o,
  "p")` runs a property, `sorted(xs, key=k)` calls `k` and `__lt__`, and
  `f(*xs)` iterates `xs`. Where the construct written at the same node
  iterates too (`for x in list(c)`), the analysis makes one call for both,
  listed as `iteration`. Any other construct written at the node of a call
  expression keeps its word (`with f():` is `with`, `if f():` is `truth`,
  `{f(): v}` is `dict`).
- Implicit calls to outside code are not listed: the call graph reports
  outside callees for call expressions only. A call expression whose
  callee is known but calls nothing that the call graph reports (a class
  whose `__init__` is `object`'s, a method of an abstract outside class) is
  not listed either.
- `implicit`, when present, says that the call is not written as a call and
  names the construct (the list is below). A site without it is a call
  expression.
- `unresolved`, when present, says why a call expression has no callee at
  all: the site is unknown, not unreachable. The causes are below.

The edges of the classic call graph are `caller -> callee` for each callee
of each site. A caller with no call site is in `definitions` and not in
`calls`.

### Implicit constructs

A closed list. Each word names a language construct; the start and the
end are those of the node in parentheses.

| `implicit` | The construct and what it calls |
|---|---|
| `attribute` | A load or store of an attribute, by `.` (the attribute expression), `from m import x` (the name) or a sub-pattern of a class pattern (the sub-pattern): a property's getter or setter, `__get__`, `__set__`, `__getattribute__`, `__setattr__`, `__getattr__`, a module's `__getattr__` |
| `await` | `await`, `async with` and `async for` (the expression): `__await__` |
| `class` | A class statement (the statement): the metaclass's `__prepare__`, `__new__` and `__init__`, `__init_subclass__`, `__set_name__` |
| `decorator` | A decorator (its expression): the decorator, with the function or class |
| `delete` | `del x.a` and `del x[k]` (the target): a property's deleter, `__delete__`, `__delattr__`, `__delitem__` |
| `dict` | A key that enters a set or dict or is looked up there: a set or dict display or comprehension, a subscript of a dict, a builtin that stores or looks up keys (the display, the key or element, the subscript, or the call): `__hash__` of the key, `__eq__` of the stored keys |
| `format` | An f-string field, `"%s" % x` and the fields of a literal `"{}".format(x)` (the field, the operation, or the call): `__format__`, `__str__`, `__repr__` |
| `iteration` | `for`, comprehensions, unpacking, `yield from`, `*` in a display, `xs += ys` and slice assignment on a list (the iterated expression, the operation, or the subscript): `__iter__`, `__next__`, `__getitem__` of the sequence protocol, `__aiter__`, `__anext__` |
| `match` | A sequence pattern of `match` (the pattern): `__len__` |
| `operator` | A unary, binary or augmented operator, a comparison, `in` and `not in`, and a value pattern of `match` (the operation; a link of a comparison, from its left operand to its right one; or the pattern): the special method of the operator, `__eq__` of the compared elements of `in`, `__eq__` and the ordering method of the elements of compared containers. `is` and `is not` call nothing |
| `raise` | `raise C` (the raised expression): `__new__` and `__init__` of the instance it creates |
| `subscript` | A subscript, and an item that a sequence or mapping pattern reads (the subscript, or the pattern): `__getitem__`, `__setitem__`, `__missing__`, `__class_getitem__`, the factory of a `defaultdict` |
| `truth` | A condition (`if`, `while`, `assert`, a conditional expression, a comprehension's `if`, a guard), `not`, the operands of `and` and `or` but the last, the result of a comparison link that the chain goes on from, of `in` and of a value pattern (the tested expression; the `not` expression; the link; the pattern): `__bool__`, `__len__` |
| `with` | `with` and `async with` (the context expression): `__enter__`, `__exit__`, `__aenter__`, `__aexit__` |

### Causes of an unresolved site

A closed list:

- `no value`: the called expression holds no value that the analysis
  knows (a parameter that no analysed code passes, a name that nothing
  binds);
- `computed name`: the called value is an attribute looked up with a name
  that is not a constant (`getattr(obj, name)()`), whose names the
  analysis does not know (the name may hold a value other than a str
  constant, or more str constants than the analysis follows);
- `outside value`: the called expression holds only a value of outside
  code that has no name: an access path longer than the bound of names
  (`lib.a.b.c()`), what a call of outside code without stubs returns
  (`lib.f()()`, `lib.f().run()`, also through `getattr` with a name that
  the analysis knows), or a value whose type is not known;
- `saturated`: the called expression may hold more values than the
  analysis keeps for one node (the cap, 5,000 by default, `tool.cap`; see
  *Saturation* in `docs/design.md`), so it holds a value about which
  nothing is known.

The cause is that of the called expression itself. Saturation of another
node can leave a call with another cause: a parameter whose only call was
through a saturated value has `no value`, and an attribute looked up by a
computed name whose candidates were lost with the instances of a class has
`computed name`. So `saturated` marks the sites where the cap applied
directly, not every site that it affected.

## Reading the document

`pycg.formats.edges(document)` returns the classic map from each node to
the sorted names it calls.

The viewer (`pycg-view graph.json -o graph.html`) writes one self-contained
HTML page, which works offline. It reads format `pycg/1` and refuses any
other. The page shows the callers and callees of a node with their sites,
implicit constructs, outside callees and unresolved sites, and a module map
that counts the edges between each pair of modules. It counts an edge once
for each caller and callee in each module whose code holds a site of it (a
site's `module`, or else the module of its caller), and puts an
`extension` name in the extension module whose name is the longest prefix
of it. A site in another module than its caller's shows that module's file. The filters hide outside
callees, implicit sites or unresolved sites everywhere on the page; the
counts in the header are those of the whole document. The page holds the
document in a `<script type="application/json">` block with each `<`
written as `\u003c`: in JSON a `<` is always inside a string, where the
escape means the same character, so no name in the document can end the
block. Every name comes from the analysed code, so the page puts text in
as text nodes only. A site is labelled `line:col`, with its end when the
caller has another site that starts at the same place, and after the file
of its module when that is not the module of the listed definition.

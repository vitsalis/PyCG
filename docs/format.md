# Output format

PyCG writes one JSON document in the format `pycg/1`. The document is
deterministic: object keys are sorted, the text is compact (no whitespace
between tokens) and ASCII, with every other character, a lone surrogate
included, escaped as `\uXXXX`. A reader refuses a `format` it does not know.

## Example

`pkg/__init__.py`:

```python
from .shapes import Square
```

`pkg/shapes.py`:

```python
import os


class Square:
    def __init__(self, side):
        self.side = side

    def __bool__(self):
        return self.side > 0

    def area(self):
        return self.side * self.side


def report(path, hook):
    square = Square(2)
    if square:
        hook(os.path.join(path, "area"), square.area())
```

`pycg --package . --package-name pkg --package-version 1.0 pkg/__init__.py
pkg/shapes.py` writes this document, pretty-printed here for reading:

```json
{
  "calls": {
    "pkg.shapes.report": [
      {"callees": ["pkg.shapes.Square.__init__"], "col": 13, "end": [16, 22], "line": 16},
      {"callees": ["pkg.shapes.Square.__bool__"], "col": 7, "end": [17, 13], "implicit": "truth", "line": 17},
      {"callees": [], "col": 8, "end": [18, 55], "line": 18, "unresolved": "no value"},
      {"callees": ["os.path.join"], "col": 13, "end": [18, 39], "line": 18},
      {"callees": ["pkg.shapes.Square.area"], "col": 41, "end": [18, 54], "line": 18}
    ]
  },
  "definitions": {
    "pkg": {"kind": "module", "lines": [1, 1], "module": "pkg"},
    "pkg.shapes": {"kind": "module", "lines": [1, 18], "module": "pkg.shapes"},
    "pkg.shapes.Square": {"kind": "class", "lines": [4, 12], "module": "pkg.shapes", "mro": ["pkg.shapes.Square", "<builtin>.object"]},
    "pkg.shapes.Square.__bool__": {"kind": "function", "lines": [8, 9], "module": "pkg.shapes"},
    "pkg.shapes.Square.__init__": {"kind": "function", "lines": [5, 6], "module": "pkg.shapes"},
    "pkg.shapes.Square.area": {"kind": "function", "lines": [11, 12], "module": "pkg.shapes"},
    "pkg.shapes.report": {"kind": "function", "lines": [15, 18], "module": "pkg.shapes"}
  },
  "exports": {
    "pkg.Square": ["pkg.shapes.Square"],
    "pkg.shapes.os": ["os"]
  },
  "format": "pycg/1",
  "modules": {
    "pkg": {"file": "pkg/__init__.py", "kind": "source", "status": "analysed"},
    "pkg.shapes": {"file": "pkg/shapes.py", "kind": "source", "status": "analysed"}
  },
  "outside": {
    "os.path.join": {"known": "stub"}
  },
  "package": {"name": "pkg", "version": "1.0"},
  "tool": {"cap": 1000, "name": "pycg", "typeshed": "98ab14707e0d52deabd05161328f4cfce3869d34", "version": "2.0.0"}
}
```

## Top-level keys

| Key | Type | Meaning |
|---|---|---|
| `format` | string | `pycg/1` |
| `tool` | object | The tool that wrote the document |
| `package` | object | The analysed package, as given on the command line |
| `modules` | object | Module name to module, for every module of the package |
| `definitions` | object | Qualified name to definition |
| `exports` | object | Access path to the sorted definitions or outside names it reaches |
| `outside` | object | Each callee that is not a definition, to how PyCG knows it |
| `calls` | object | Caller (a module or function of `definitions`) to its call sites |

## `tool` and `package`

| Field | Type | Meaning |
|---|---|---|
| `tool.name` | string | `pycg` |
| `tool.version` | string | The version of PyCG |
| `tool.typeshed` | string | The typeshed commit of the stub data |
| `tool.cap` | integer or null | The most values kept for one node (`--cap`, 1,000 by default); `null` for `--cap none` |
| `package.name` | string or null | `--package-name`; `null` when not given |
| `package.version` | string or null | `--package-version`; `null` when not given |

## `modules`

Every source file that the analysis reached under the package root, and
every extension module that an import or an entry point reaches there.

| Field | Type | Meaning |
|---|---|---|
| `file` | string | The path as written, relative to the package root, with `/` separators |
| `kind` | string | `source`, or `extension`: a binary `name.so`, `name.<tag>.so` or `name.pyd`, of which PyCG reads only the name |
| `status` | string | Source only: `analysed`, `partial` or `failed` |
| `cause` | string | Source only, unless `analysed`: why the module is not whole |
| `shadows` | list of strings | When present: the other files of the module's name, sorted, which PyCG does not analyse |

The file of a module name is the package (`a/__init__.py`), else `a.py`,
else the first extension binary by name, else the first file that only an
entry point names, by path. A namespace package holds a name only when no
file does.

| `status` | Meaning | `cause` |
|---|---|---|
| `analysed` | The whole module is analysed | None |
| `partial` | The analysis stopped before a top-level statement nested deeper than 247 levels ([Bounds](design.md#bounds)); what came before is kept | `DeepNesting (line N)` |
| `failed` | The file cannot be read, decoded or parsed; the module defines only itself, with lines `[0, 0]`, and calls nothing | The error type, below |

The cause of a failed module is the type of the error, with `(line N)` or
`(byte N)` where Python gives one: `SyntaxError`, `IndentationError`,
`TabError`, `RecursionError`, `MemoryError` (the source is too complex for
Python's parser), `UnicodeDecodeError (byte N)`, `unsupported encoding
<codec>`, `FileNotFoundError`, `PermissionError`, `IsADirectoryError`,
`NotADirectoryError` or `OSError`.

## `definitions`

Every module, class and function (lambdas included) that the analysed
source defines, except in code that the analysis proves cannot run.

| Field | Type | Meaning |
|---|---|---|
| `kind` | string | `module`, `class` or `function` |
| `module` | string | The module that defines it |
| `lines` | [integer, integer] | First and last line: of a function or class, from its `def` or `class` line (not its decorators) to its end; of a module, `[1, n]` as Python numbers lines, `[0, 0]` when empty |
| `mro` | list of strings | Class only: its C3 linearization over the bases that the analysis knows |

- An outside base (`ext.Base`, `<builtin>.dict`) is one entry at its place;
  its own bases are not listed. Only an `mro` without an outside class ends
  with `<builtin>.object`.
- A class with several possible hierarchies lists each class at its first
  position.
- An unknown class (its base or metaclass saturated, or a base unknown)
  lists only itself; a call of it or through its instances is unresolved
  with `saturated`.
- Of the definitions of one name, the one listed is a module, else a
  function, else a class, and of those the first by module and position.

## `exports`

For each module of the package, each name bound at the end of its code to
a module, class or function whose qualified name is not that path, mapped
to the sorted names it may hold (flow-insensitively). Graphs of several
packages join on this table.

## `outside`

| `known` | Meaning |
|---|---|
| `stub` | Declared by the stub data or the models of the builtins: a function by the path the code reaches it through (`os.path.join`), a method by its class's public name (`requests.Response.json`), or a name the models give to analysed code (`functools.partial.__call__`) |
| `name` | Built from the access path of a value without a type (`foo.get.bar`); it need not exist |
| `extension` | A name in an extension module of the package |

## `calls`

A caller's sites are sorted by `module` (a site without it first), `line`,
`col`, `end`, then `implicit` (a site without it first). A caller with no
site is not listed.

| Field | Type | Meaning |
|---|---|---|
| `line`, `col` | integer | Start of the `ast` node that makes the call (lines from 1, columns from 0) |
| `end` | [integer, integer] | End of that node, `[line, col]` |
| `callees` | list of strings | The sorted definitions and outside names the site can call |
| `implicit` | string | When present: the call is not written as a call; the construct, below |
| `unresolved` | string | When present: the site is a call expression with no callee; the cause, below |
| `module` | string | When present: the module whose code holds the site, if not the caller's |

- Calls in a class body or a comprehension belong to the enclosing function
  or module. The definitions of one name (two `def f`, a property's getter
  and setter) share its entry.
- The calls of one node and one construct are one site; two sites can
  start at one position (`f(x)(y)`).
- A link of a comparison chain spans its two operands (`b < c` in
  `a < b < c`). The accessor that a class's own attribute hook runs is an
  `attribute` site of the hook, at its whole `def`.
- The implicit calls a builtin makes (`list(x)`, `map(f, xs)`,
  `sorted(xs, key=k)`, `f(*xs)`) are callees of its call. A construct
  written at the node of a call keeps its word (`with f():` is `with`;
  `for x in list(c)` is one `iteration` site).
- Outside callees are listed only for call expressions and decorators. A
  call expression that calls nothing listed (a class whose `__init__` is
  `object`'s) is not a site.
- The classic call graph has a node for each definition that is not a class
  and each outside name, and an edge to each callee of each site.

### `implicit`

| Construct | Node | What it calls |
|---|---|---|
| `attribute` | An attribute load or store, the name of `from m import x`, a class pattern's sub-pattern | A property's getter or setter, `__get__`, `__set__`, `__getattribute__`, `__setattr__`, `__getattr__`, a module's `__getattr__` |
| `await` | `await`, `async with`, `async for` | `__await__` |
| `class` | A class statement | The metaclass's `__prepare__`, `__new__` and `__init__`, `__init_subclass__`, `__set_name__` |
| `decorator` | A decorator expression | The decorator, with the function or class |
| `delete` | The target of `del x.a` or `del x[k]` | A property's deleter, `__delete__`, `__delattr__`, `__delitem__` |
| `dict` | A set or dict display or comprehension, a dict subscript, a builtin that stores or looks up keys | `__hash__` of the key, `__eq__` of the stored keys |
| `format` | An f-string field, `"%s" % x`, a literal `"{}".format(x)` | `__format__`, `__str__`, `__repr__` |
| `iteration` | `for`, a comprehension, unpacking, `yield from`, `*` in a display, `xs += ys` or slice assignment on a list | `__iter__`, `__next__`, `__getitem__`, `__aiter__`, `__anext__` |
| `match` | A sequence pattern | `__len__` |
| `operator` | A unary, binary or augmented operator, a comparison link, `in`, `not in`, a value pattern | The operator's special method; `__eq__` and the ordering methods of compared elements (`is` calls nothing) |
| `raise` | The expression of `raise C` | `__new__` and `__init__` of the instance |
| `subscript` | A subscript, an item that a sequence or mapping pattern reads | `__getitem__`, `__setitem__`, `__missing__`, `__class_getitem__`, a `defaultdict`'s factory |
| `truth` | A condition (`if`, `while`, `assert`, a conditional expression, a comprehension's `if`, a guard), `not`, each operand of `and` and `or` but the last, a comparison link the chain goes on from, `in`, a value pattern | `__bool__`, `__len__` |
| `with` | The context expression of `with` or `async with` | `__enter__`, `__exit__`, `__aenter__`, `__aexit__` |

### `unresolved`

| Cause | The called expression holds |
|---|---|
| `no value` | No value that the analysis knows (a parameter no analysed code passes, a name nothing binds) |
| `computed name` | An attribute looked up by a name the analysis does not know (`getattr(obj, name)()`) |
| `outside value` | Only an unnamed outside value: a path longer than the bound of names, what an outside call without stubs returns, a value of unknown type |
| `saturated` | More values than the cap (`tool.cap`, see [Bounds](design.md#bounds)) |

`saturated` marks only the sites where the cap applied directly; a site
that saturation elsewhere affected can have another cause.

# Micro-benchmark

Small Python programs, each with a hand-written call graph that is the ground
truth for call graph generators.

## Case layout

```
snippets/<category>/<case>/
├── main.py          # Entry point, run as a script in the case directory
├── *.py, pkg/       # Other modules of the program (optional)
├── README.md        # The language feature that the case tests
└── callgraph.json   # Ground truth
```

Every `main.py` runs to completion without input and without an uncaught
exception. `callgraph.json` is a JSON object. Each key is a node and its value
is the list of nodes that it calls:

```json
{
    "main": ["main.func", "<builtin>.len"],
    "main.func": [],
    "<builtin>.len": []
}
```

## Ground-truth conventions

### Nodes

Nodes are modules, functions and lambdas. Classes, class bodies,
comprehensions and generator expressions are not nodes. The keys are:

- every module of the case that runs, including `main`;
- every function and lambda defined in those modules, called or not;
- every callee, including builtins and external names.

### Names

| Entity | Name | Example |
|--------|------|---------|
| Module top level | Path relative to the case directory, dotted. A package `__init__.py` is the package name. | `main`, `pkg.mod`, `pkg` |
| Function, method, class | Enclosing names joined with dots, no `<locals>` | `main.MyClass.func`, `main.outer.inner` |
| Lambda | `<lambdaN>`, numbered from 1 by the position (line, column) of the `lambda` keyword within the enclosing function, class or module | `main.<lambda2>`, `main.func.<lambda1>` |
| Builtin function or class | `<builtin>.` and the name in `builtins` | `<builtin>.len`, `<builtin>.range` |
| Method of a builtin type | `<builtin>.<type>.<method>` | `<builtin>.str.join`, `<builtin>.dict.items` |
| Name outside the snippet | Dotted path from an importable module | `os.path.join`, `threading.Thread.start`, `ext.Cls.fun` |

A name of a callee outside the snippet is a dotted path that resolves to the
function that runs. Several paths can resolve to one function
(`<builtin>.Exception.__init__` is `<builtin>.BaseException.__init__`,
`os.path.join` is `posixpath.join`). The ground truth uses the path as the
snippet reaches it:

- **Functions of a module**: The path that the snippet imports
  (`os.path.join`, not `posixpath.join`).
- **Methods**: The public import path of the class of the instance, then the
  method (`threading.Thread.start`, `logging.Logger.info`,
  `<builtin>.str.join`).
- **Inherited methods**: Named through the class that the snippet names
  (`<builtin>.Exception.__init__` for `class E(Exception)`,
  `threading.Thread.start` for a snippet subclass of `Thread` that does not
  override `start`).
- **Missing modules**: The access path (`ext.Cls.fun`). The module `ext` in
  `external/*` does not exist.

### Edges

An edge `A -> B` exists when code of `A` calls `B` at least once while
`main.py` runs.

- **Snippet functions**: Every invocation counts, also implicit ones (`__init__`
  on instantiation, `__iter__` and `__next__` in a `for` loop, decorators,
  `__enter__` in a `with` statement).
- **Builtins and names outside the snippet**: Only call expressions count. A
  `with` statement on a file adds no `__enter__` edge (an explicit
  `f.__enter__()` does), `d[k] = v` adds no `__setitem__` edge, and
  `raise StopIteration` without parentheses adds no edge.
- **Scopes without a node**: Calls in a class body, comprehension or generator
  expression belong to the enclosing function or module. Calls in a string
  passed to `eval` or `exec` belong to the scope that calls `eval` or `exec`.
- **Callbacks**: A snippet function that builtin or library code calls belongs
  to the scope that called that code (`list(map(f, xs))` in `main` gives
  `main -> main.f`).
- **Generators and coroutines**: The edge comes from the scope that calls the
  generator function, not from the scope that iterates over the generator.
- **Instantiation of a snippet class**: A call `Cls()` and a `raise Cls`
  without parentheses both instantiate the class. The edge goes to the first
  `__init__` in the MRO of the class. If the snippet defines it, the edge is
  `mod.Cls.__init__`. If it is `object.__init__`, there is no edge. Otherwise
  the edge names it through the nearest class of the MRO that is outside the
  snippet: `<builtin>.Exception.__init__`, `collections.UserList.__init__`,
  `ext.parent.__init__`.
- **Instantiation of a builtin or external class**: An explicit call gives an
  edge to the class (`<builtin>.StopIteration`, `ext.Cls`).
- **Imports**: An import adds no edge. Calls at the top level of the imported
  module are edges of that module's node.

## Validation

```sh
python micro-benchmark/validate.py                                # Every case
python micro-benchmark/validate.py micro-benchmark/snippets/a/b  # One case
```

This command:

1. Runs `main.py` of each case in a separate Python process, with the case
   directory as working directory and as `sys.path[0]` (isolated mode, no
   bytecode files, 30 s timeout).
2. Records the calls with `sys.monitoring` and names them with the conventions
   above. A module that the snippet imports and that does not exist (e.g.,
   `ext` in `external/*`) is replaced by a stub that records calls by their
   dotted name.
3. Matches each call to code outside the snippet with an expected callee of
   the same caller whose name resolves to the same function. Names resolve
   through `builtins` and through modules that are already imported, so
   resolving imports nothing. A call that no expected name matches is shown
   under the name of the module and class that define the function (e.g.,
   `posixpath.join`). A stub name does not resolve and must be equal.
4. Compares the result with `callgraph.json` and prints each problem. The exit
   status is 1 if any case has a problem.

| Problem | Meaning |
|---------|---------|
| `snippet did not finish` | Uncaught exception, non-zero exit status, or timeout |
| `missing edge` | The run made the call and `callgraph.json` does not have it |
| `unobserved edge` | `callgraph.json` has the call and the run did not make it |
| `missing node` | A module, function or callee of the run is not a key |
| `unexpected node` | A key is not a module, function or callee of the run |

`tests/test_benchmark_validator.py` runs the validator on the whole benchmark.
The validator needs Python 3.14 or later and is tested on Python 3.15.

### Limits

The validator cannot observe or name these calls. A case that depends on them
needs a manual check.

- A generator function that builtin code or the interpreter calls (e.g.,
  `__iter__` written as a generator).
- An inherited `__init__` from outside the snippet, when builtin code
  instantiates the class (`map(Cls, xs)`), or when the operand of `raise` is
  not a name or attribute chain (`raise classes[0]`). A snippet `__init__` is
  observed in both cases.
- Functions created at run time by `exec`, `eval` or generated code (e.g., the
  `__init__` of a dataclass).
- Implicit calls that happen at an unrelated point (e.g., `__del__` during
  garbage collection) belong to the frame that runs at that point. Calls in
  another thread get the caller `<unknown>`.
- The validator accepts any name that resolves to the callee. Whether the
  ground truth uses the canonical name is a review check.
- `from ext import *` on a stubbed module imports no names.
- A case module with the name of a module that the validator has already
  loaded (e.g., `json.py`) cannot be imported. The validator reports this case
  as `snippet did not finish`.
- The value scope of a `type X = ...` statement (PEP 695) gets a node as if it
  were a function.

## Adding a case

1. Create `snippets/<category>/<case>/` with `main.py`, the other modules of
   the program, and a `README.md` that states the feature under test.
2. Write the program with a single execution path: every call in the source
   runs at least once, and no input or environment changes the run.
3. Make sure that the program runs to completion without an uncaught
   exception.
4. Write `callgraph.json` by hand from Python semantics and the conventions
   above.
5. Run the validator on the case and fix the case until it reports `ok`:

   ```sh
   python micro-benchmark/validate.py micro-benchmark/snippets/<category>/<case>
   ```

> **Important**: Never derive ground truth from PyCG output. A ground truth
> copied from the tool under evaluation hides the errors that the benchmark
> must find.

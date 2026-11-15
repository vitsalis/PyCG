# Micro-benchmark

Small Python programs, each with a hand-written call graph that is the ground
truth for call graph generators.

## Case layout

```
snippets/<category>/<case>/
├── main.py          # Entry point, run as a script in the case directory
├── *.py, pkg/       # Other modules of the program (optional)
├── README.md        # The language feature that the case tests
├── requires-python  # Minimum Python version, e.g. 3.14 (optional)
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
comprehensions, generator expressions and annotation scopes are not nodes. The
keys are:

- every module of the case that runs, including `main`;
- every function and lambda defined in those modules, called or not;
- every callee, including builtins and external names.

Functions that get the same name (see Names) are one node: a function that is
defined again, a function defined in both branches of an `if`, the getter,
setter and deleter of a property, and the `@overload` signatures and the
implementation of a function.

A function that a string passed to `exec` defines, or that library code
generates (the `__init__` of a dataclass), has no node. It counts as code
outside the snippet (see Callbacks).

### Names

| Entity | Name | Example |
|--------|------|---------|
| Module top level | Path relative to the case directory, dotted. A package `__init__.py` is the package name. | `main`, `pkg.mod`, `pkg` |
| Function, method, class | Enclosing names joined with dots, no `<locals>` | `main.MyClass.func`, `main.outer.inner` |
| Lambda | `<lambdaN>`, numbered from 1 by the position (line, column) of the `lambda` keyword within the scope that evaluates it | `main.<lambda2>`, `main.func.<lambda1>` |
| Builtin function or class | `<builtin>.` and the name in `builtins` | `<builtin>.len`, `<builtin>.range` |
| Method of a type in `builtins` | `<builtin>.<type>.<method>` | `<builtin>.str.join`, `<builtin>.dict.items` |
| Name outside the snippet | Dotted path from an importable module | `os.path.join`, `threading.Thread.start`, `ext.Cls.fun` |

A function or lambda belongs to the scope that evaluates its definition, as in
`__qualname__`. A lambda in a default value belongs to the scope that evaluates
the default: in `run = lambda g=lambda: f(): g()` at module level, the inner
lambda is `main.<lambda2>`. Unlike `__qualname__`, a `def` under a `global`
declaration in the function `install` is `main.install.handler`.

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
- **Methods of other builtin types**: A type that is not in `builtins` is
  named by its public path (`types.GeneratorType.send`,
  `types.CoroutineType.__await__`).
- **Functions without an attribute path**: A closure or local function of
  library code has no attribute path from an importable module or class. It is
  named by where it is defined: the module, then the qualified name without
  `<locals>` (`contextlib.contextmanager.helper`,
  `functools.singledispatch.wrapper`, `dataclasses.dataclass.wrap`). This holds
  also when `functools.wraps` gives it the name of the function that it wraps.
  Every other callee follows the rules above, even if it is defined elsewhere
  (`collections.UserDict.update`, not `_collections_abc.MutableMapping.update`;
  `operator.add`, not `_operator.add`).
- **Calls of instances**: Calling an instance of a class outside the snippet
  calls `<class path>.__call__`, also when the class is private
  (`functools._lru_cache_wrapper.__call__`, `typing._GenericAlias.__call__`).
  For an instance of a snippet class that inherits `__call__`, see Inherited
  methods (`contextlib.ContextDecorator.__call__`).
- **Missing modules**: The access path (`ext.Cls.fun`). The module `ext` in
  `external/*` does not exist (see [Missing modules](#missing-modules)).

### Edges

An edge `A -> B` exists when code of `A` calls `B` at least once while
`main.py` runs.

- **Snippet functions**: Every invocation counts, also implicit ones (`__init__`
  on instantiation, `__iter__` and `__next__` in a `for` loop, decorators,
  `__enter__` in a `with` statement).
- **Builtins and names outside the snippet**: Only call expressions count. A
  `with` statement on a file adds no `__enter__` edge (an explicit
  `f.__enter__()` does), `d[k] = v` adds no `__setitem__` edge,
  `raise StopIteration` without parentheses adds no edge, and a failing
  `assert` adds no `<builtin>.AssertionError` edge. Implicit calls are not
  edges, also when builtin or library code makes them: a `for` loop over a
  snippet subclass of `Sequence` adds no `Sequence.__iter__` edge, an f-string
  adds no `object.__format__` edge, and builtin or library code that
  instantiates a snippet class adds no edge to an `__init__` from outside the
  snippet.
- **Scopes without a node**: Calls in a class body, comprehension or generator
  expression belong to the enclosing function or module. Calls in an
  annotation scope belong to the scope that defines it, wherever it is
  evaluated. Annotation scopes are lazily evaluated annotations (PEP 649), the
  value of a `type X = ...` statement, and the bounds, constraints and
  defaults of type parameters. Calls in a string passed to `eval` or `exec`
  belong to the scope that calls `eval` or `exec`.
- **Callbacks**: A snippet function that builtin or library code calls belongs
  to the snippet scope whose call made that code run (`list(map(f, xs))` in
  `main` gives `main -> main.f`, and a snippet `__getitem__` that
  `Mapping.get` calls belongs to the scope that calls `get`). A callback that
  runs later follows the same rule: the target or `run` method of a thread
  belongs to the scope that calls `start()`, and an event loop callback
  (`loop.call_soon(f)`) belongs to the scope that calls `asyncio.run`.
- **Generators and coroutines**: The edge comes from the scope that calls the
  generator or coroutine function, not from the scope that iterates over or
  awaits the result. If builtin or library code calls the function, see
  Callbacks (`main -> main.managed` for `with managed():` on a function
  decorated with `contextlib.contextmanager`).
- **Instantiation of a snippet class**: A call `Cls()` and a `raise Cls`
  without parentheses both instantiate the class. The edge goes to the first
  `__init__` in the MRO of the class. If the snippet defines it, the edge is
  `mod.Cls.__init__`. If it is `object.__init__`, there is no edge. Otherwise
  the edge names it through the nearest class of the MRO that is outside the
  snippet: `<builtin>.Exception.__init__`, `collections.UserList.__init__`,
  `ext.parent.__init__`. This rule assumes that the metaclass does not
  override `__call__`. If it does, the edge to `__init__` exists only if
  `__init__` runs (`Status("active")` on an `enum.Enum` subclass looks up a
  member and does not call `__init__`).
- **Instantiation of a builtin or external class**: An explicit call gives an
  edge to the class (`<builtin>.StopIteration`, `ext.Cls`).
- **Imports**: An import adds no edge. Calls at the top level of the imported
  module are edges of that module's node.

### Missing modules

A module that the snippet imports and that does not exist (`ext` in
`external/*`) behaves as a stub module. Each name in it is a stub, named by its
access path:

- An attribute of a stub, or of an instance of a stub, is the stub with the
  longer path (`ext.Cls.fun`).
- Calling a stub, or an instance of a stub, returns an instance of that stub.
  So `ext.client().get()` calls `ext.client` and then `ext.client.get`. A stub
  never calls its arguments and never raises.
- A stub is an exception class. The snippet can raise an instance and catch it
  with `except ext.Error`.
- In a `with` statement, a stub gives itself and lets exceptions through.
  Iteration over a stub gives no items.
- A snippet class that derives from a stub inherits `ext.Base.__init__` and
  `ext.Base.__init_subclass__`. For each name that a snippet class derived
  from the stub defines, `super().name` is the stub `ext.Base.name`, also in a
  classmethod and in a class hook.

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
   above. A module that the snippet imports and that does not exist is
   replaced by a stub module (see [Missing modules](#missing-modules)).
3. Matches each call to code outside the snippet with an expected callee of
   the same caller whose name resolves to the same function. Names resolve
   through `builtins` and through modules that are already imported, so
   resolving imports nothing. A call that no expected name matches is shown
   under the name of the module and class that define the function (e.g.,
   `posixpath.join`). A stub name does not resolve and must be equal.
4. Compares the result with `callgraph.json` and prints each problem. The exit
   status is 1 if any case has a problem.

A case whose `requires-python` names a newer version than the interpreter of
the validator is not run. The validator reports it as `skipped`.

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
  `__iter__` or `__await__` written as a generator). A coroutine function
  that they call (`__anext__` in `async for`, or through `anext`) is observed
  only if the coroutine starts in the scope that created it.
- An inherited `__init__` from outside the snippet, when the operand of
  `raise` is not a name or attribute chain (`raise classes[0]`), or when the
  `raise` is in a class body whose namespace (from `__prepare__`) is not a
  dict. A snippet `__init__` is observed.
- A call of a snippet generator or coroutine function whose arguments do not
  match its parameters raises `TypeError` before the function starts. The
  validator records such a call as an edge, because it records these
  functions at the call. A plain function that is called this way gives no
  edge.
- Calls of builtins and names outside the snippet in code that `compile` gets
  with a file name other than `"<string>"`. The validator handles that code as
  code outside the snippet, like a function that `exec` defines. It observes
  the snippet functions that the code calls.
- A call `any(<genexpr>)` in a string passed to `eval` or `exec`, and the same
  for `all` and `tuple` (from Python 3.15 also `list` and `set`). Python
  3.14+ compiles such a call into a loop without a call event. The validator
  recognises this loop only in a source file, where it can check the call in
  the source.
- Implicit calls that happen at an unrelated point (e.g., `__del__` during
  garbage collection) belong to the frame that runs at that point. Calls in a
  thread that `threading.Thread.start` did not start get the caller
  `<unknown>`.
- The validator accepts any name that resolves to the callee. Whether the
  ground truth uses the canonical name is a review check.
- `from ext import *` on a stubbed module imports no names. The attributes
  that `BaseException` and `type` define (`args`, `mro`) are not stubs. A class
  cannot derive from a stub and from a class with another metaclass (e.g.,
  `abc.ABC`, `enum.Enum`). The snippet classes that derive from a stub have
  one subclass of the stub, with the same name, as their shared base. A name
  that one of these classes defines is found on the others before their own
  `__getattr__`.
- A case module with the name of a module that the validator has already
  loaded (e.g., `json.py`) cannot be imported. The validator reports this case
  as `snippet did not finish`.

## Adding a case

1. Create `snippets/<category>/<case>/` with `main.py`, the other modules of
   the program, and a `README.md` that states the feature under test.
2. Write the program with a single execution path: no input or environment
   changes the run. The ground truth states what runs. To test precision, a
   case can contain code that never runs (a function that is never called, a
   branch that is never taken). The case `README.md` names that code.
3. Make sure that the program runs to completion without an uncaught
   exception.
4. If the program needs a Python version newer than 3.12, the oldest supported
   version, write that version (e.g., `3.14`) in a file `requires-python`. The
   test suite and the validator skip the case on older interpreters.
5. Write `callgraph.json` by hand from Python semantics and the conventions
   above.
6. Run the validator on the case and fix the case until it reports `ok`:

   ```sh
   python micro-benchmark/validate.py micro-benchmark/snippets/<category>/<case>
   ```

> **Important**: Never derive ground truth from PyCG output. A ground truth
> copied from the tool under evaluation hides the errors that the benchmark
> must find.

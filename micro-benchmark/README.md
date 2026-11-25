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

### How the validator observes calls

The child process registers each code object of a snippet module when the
module starts. It keeps the code objects alive, so that their ids stay
unique. It reads the snippet without running snippet code.

- **When a call is recorded**: A snippet function is recorded when its code
  starts (`PY_START`), so implicit calls and callbacks from builtins are
  seen too. A generator or coroutine function is recorded at its call
  (`CALL`): calling it creates a generator or coroutine and does not run the
  body. Every callee outside the snippet is recorded at its call.
- **Scopes without a node**: Generator expressions, `__annotate__`, `<generic
  parameters of ...>`, and the lazily evaluated scopes of `type X = ...`
  values and of type parameter bounds, constraints and defaults. These last
  are recognised by their only parameter, `.format`, a name that source code
  cannot use. A class body's names nest under it; its calls belong to the
  scope around it.
- **The caller**: The node of the nearest snippet frame, skipping library
  frames. In a thread without a snippet frame, it is the scope that called
  the thread's `start()`. Calls in a string passed to `eval` or `exec` belong
  to the snippet scope that runs it. `CALL` events in library code stay
  enabled: a call there can start a thread or call a snippet generator
  function (`contextlib.contextmanager`).
- **Threads**: The `CALL` event of `threading.Thread.start` comes before
  `start()` runs, which raises `RuntimeError` if `Thread.__init__` did not
  run or the thread is started already. The validator reads these checks
  statically (`_initialized`, `_started._flag`): properties such as
  `Thread.ident` can raise on such a thread.
- **`with`**: Python 3.14+ fetches `__enter__` and `__exit__` with
  `LOAD_SPECIAL` and calls `__enter__` right after it. It calls `__exit__`
  after loading `None` three times (`LOAD_CONST`, or from Python 3.15
  `LOAD_COMMON_CONSTANT`). These loads have the source position of the
  `with` item, like the `LOAD_SPECIAL`. An explicit call `item.__enter__()`
  can have that position too, but not these loads.
- **`assert`**: The `CALL` that creates the `AssertionError` of an `assert`
  has the source position of the instruction that loads `AssertionError`,
  which only an `assert` statement loads as a common constant.
- **`raise Cls`**: It creates an instance without a `CALL` event. On the
  `RAISE` event, the validator checks that the operand is a name or a chain
  of attributes (`raise E`, `raise A.B from None`) that evaluates to the
  class, by reading it again in the frame without side effects.
- **Inlined builtins**: For a call `name(<genexpr>)` of `any`, `all`, `tuple`
  and, from Python 3.15, `list` and `set`, Python 3.14+ compiles a check
  `name is builtin` (`LOAD_COMMON_CONSTANT`, `IS_OP 0`, `POP_JUMP_IF_FALSE`
  to the real call) and a loop in place of the call. The check and the
  loop's `FOR_ITER` have the source position of the name. The validator
  finds these calls in the source file. The inlined builtin starts consuming
  its generator expression in the loop, after the argument is evaluated, so
  the call is recorded when the generator expression starts while its
  caller is at that `FOR_ITER`.
- **Coroutines without a call event**: The interpreter calls a coroutine
  method without a `CALL` event (`__anext__` in `async for`), and so does
  builtin code (`anext`). A coroutine records the file, line and function
  name of the frame that created it (`cr_origin`). If that is a line of the
  snippet code that awaits it, the edge belongs to the scope of that code.
  For a coroutine that a call expression there created, this gives the edge
  of the `CALL` event again. The tracking of origins is a setting per
  thread, so every event turns it on in its thread: a new thread gets an
  event (its first call) before it can create a coroutine.
- **Running no snippet code**: `isinstance()` reads `obj.__class__` when the
  real type does not match, which runs a `__class__` property of a snippet
  class (a lazy proxy), so the validator tests the real type. It recognises
  a snippet class by its `__module__` and reads no attribute of the module
  object: a snippet can replace a module in `sys.modules` with an object
  that runs code on access. Attributes are read with
  `inspect.getattr_static`. A namespace is read as a plain dict, and only if
  it is a dict: `dict.__getitem__` would still call a `__missing__` of a
  subclass, and a class body can have a mapping from `__prepare__` with
  snippet methods. The variables of a function are read through its frame.
  Only builtin descriptors are bound.
- **Names of outside callees**: A function outside the snippet is named from
  the module whose globals it uses and the qualified name of its code
  (`contextlib.contextmanager.helper`): wrappers made with `functools.wraps`
  carry the `__module__` and `__qualname__` of the function they wrap. That
  name is used only when no expected name resolves to the function.
  Different paths to one function give different objects (a bound method, a
  classmethod bound to its class, a method found on a subclass); all map to
  the one object stored in the namespace that defines it. A builtin method
  bound to a class or an instance is named by the first class in the lookup
  order (for a class: its MRO, then its metaclass's) whose descriptor gives
  this method when bound to the same object; two builtin methods are equal
  if they have the same self and the same C function. The first class that
  defines the name can be a snippet class that overrides the method
  (`super().__init_subclass__()` in an `__init_subclass__`).
- **Stubs**: The finder of missing modules is the last entry of
  `sys.meta_path`. It stubs a module that snippet code imports, but not a
  missing submodule of a real package (a real error) or a module that a
  library probes for. The classes behind the stubs have the `__module__`
  `validate`, not `__main__`, which in the child process is the snippet's
  module. A method of a stub has the `__module__` and `__qualname__` of its
  path (`ext.Cls.name`), which name the edge of its call; the methods of
  those classes themselves give no edge. The stub `__init_subclass__`
  ignores class keyword arguments: they are for the missing base class. A
  snippet class derives from the proxy of a stub in place of the stub: one
  subclass of the stub, with its name, that all snippet classes share, so
  the MRO and duplicate bases are as for a real base. For each name that a
  snippet class defines, the proxy holds the stub with the longer path, so
  `super().name` finds it. That is the object that attribute lookup on the
  stub gives, so the shared names change no attribute; names that the
  stub's own classes define are left out. The names are in place before
  `type.__new__` runs any class hook.

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

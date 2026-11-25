# Analysis design

PyCG computes the call graph of a Python package with a static analysis.
It never imports or runs the code. Part 1 gives the analysis in five ideas
and states what it does not do. Part 2 gives every rule in full, each with
its limits. Part 3 shows why the result does not depend on the solver's
order and why the solve ends, and lists the bounds.

Terms used throughout:

- **Analysed code**: the modules inside the package root. **Outside
  code**: everything else (the builtins, the standard library, other
  packages).
- **Node**: a place that holds a set of objects, its *points-to set* (a
  variable, an attribute, a container element, a return value).
- **Implicit call**: a call that the interpreter makes, not a call
  expression (`__iter__` of a `for` loop, an operator, a property getter).
- **Entry point**: a function that no analysed code calls (idea 4). The
  modules given on the command line are the *entry modules*.

# Part 1: The analysis in five ideas

```
entry modules
  ─► module discovery   follow the imports inside the package root
  ─► scopes             decide which scope binds each name
  ─► builder            walk each AST once: nodes and constraints
  ─► solver             worklist, then the fixpoint steps, until no change
  ─► call graph
```

The builder walks each module's AST once and emits nodes and constraints.
The solver propagates objects along the constraints until nothing changes.
It resolves calls during the solve and emits the call edges.

## 1. An assignment graph over objects named by where they are created

**Rule.** Every value is an object identified by the place that creates
it: a function by its definition, an instance by its class and the call
that creates it, a container by its display or call. Each node holds the
objects that may reach it. Assignments, argument passing and returns are
subset edges between nodes. A load, store or call on a node is a
constraint that acts on each object that reaches the node. A worklist
solver applies the constraints until nothing changes, once for the whole
program. A call edge exists where a call constraint meets a function.

```python
class A:
    def run(self):
        pass


def make():
    return A()  # Instance(A, make:4)


x = make()  # x ⊇ Return(make)
x.run()  # BoundMethod(Instance, A.run): edge main -> A.run
```

## 2. Local names by definition; code that cannot run is not analysed

**Rule.** A name that only the statements of its own scope bind is
followed by definition: each read gets the definitions that reach it, and
where paths meet, a join holds the definitions of each path. Code that
the syntax and the literal values of names prove cannot run is not walked:
its calls give no edges and its definitions do not exist. The heap
(attributes, container elements) is not followed by definition.

```python
x = f
if cond():
    x = g
x()  # the join of both paths: edges to f and g
x = h
DEBUG = False
if DEBUG:
    x()  # not walked: no edge to h
```

## 3. Outside code is typed from the typeshed stubs

**Rule.** The stubs of the builtins, the standard library and the
third-party libraries that typeshed describes are read as data. A call of
an outside function gives what its stub declares. A method of an outside
value is named by the public name of its class. No name is invented for a
value whose type the stubs give. Outside code is not assumed to call what
the analysed code gives it. Only the builtins of Python apply their
arguments: `map`, `sorted(key=...)`, and the special methods of their
protocol parameters (`len(x)` calls `x.__len__`). The other exceptions are
`re.sub` and `re.subn`, which call a callable replacement, and a table of
selected standard-library operations (`itertools`, `functools.reduce`,
`math.sumprod`, `heapq.nlargest`, ...), which iterate what they get: at
the call, or, for a lazy object, where analysed code advances it.

```python
m = re.match("a+", text)  # a re.Match
m.group()  # edge to re.Match.group
requests.get(url).json()  # edges to requests.get and requests.Response.json
Thread(target=work).start()  # edges to Thread and Thread.start, none to work
sorted(items, key=by_name)  # edge to by_name
```

## 4. Declared types supply what value flow cannot

**Rule.** A call edge exists only where analysed code makes the call.
Values that only outside callers could supply come from two declarations.
A function that no analysed code calls is an entry point: its receiver is
any instance of its class or of a subclass that inherits it, and its
parameters take their defaults. An annotation of a parameter, or of an
assignment, names what the parameter or the target may hold:
the instances of the class it names and of its subclasses. For an
abstract class of outside code, which no value of its own can be, the
subclasses are the analysed classes that derive from it
(`it: AsyncIterator[T]` holds the instances of the analysed async
iterators). For the protocols that the builtin types implement
(`Iterable`, `Sized`, ...), only those that derive from them through
abstract classes count: for a class that reaches one only through a
concrete class (a subclass of `list`), a client most likely passes a
builtin. A stub `x.pyi` that the package ships beside `x.py` gives the
annotations that the source leaves out, and the bases of its classes for
what an annotation names.

```python
class Shape:
    def area(self):
        return self.size()

    def size(self):
        pass


class Square(Shape):
    def size(self):
        pass


def report(shape: Shape):
    shape.area()  # shape is a Shape or a Square: edge to Shape.area
    # area calls Shape.size and Square.size
```

## 5. The result does not depend on the order of the solve, and the solve ends

**Rule.** Rules only add facts. A rule subscribes to a points-to set and
acts on each object that arrives, in any order. The few decisions that
read what a node holds (does a base hold anything, does a receiver hold
anything) run only at a fixpoint, in a fixed order, and they add facts
too. A class lookup waits until the class hierarchy is complete. A node
that would hold more objects than the cap (5,000 by default, a parameter
of the analysis) holds one saturated value instead, about which nothing is
known; the solve applies rules to a node's objects
only once propagation has filled it, in rounds, so which objects a node's
rules saw before it saturated does not depend on the order either. The
solve ends because every object and every call is keyed by finite things:
source positions, names from the source, and a bounded context (at most
three receivers, outside names at most two attributes past their root, three
for a member of an outside base class).
So `x = x.parent` on an outside value adds one name, and a class stored as
its own `__iter__` makes one instance per loop.

## What the analysis does not do

- **No flow-sensitive heap.** An attribute or container element holds
  every value ever stored there, so `d["k"] = a; d["k"] = b; d["k"]()`
  calls both.
- **No calling context.** A parameter holds what every caller passes, so a
  helper that forwards its arguments mixes the values of all its callers.
- **No model of what outside code calls.** A function given to outside
  code (a thread target, a callback) gets no edge from that code; if no
  analysed code calls it, it is an entry point and its body is analysed.
- **No code built at run time.** `eval`, `exec`, and attribute names
  computed from more than four strings are not followed, so the calls that
  they make give no edges.

# Part 2: Reference

The rules in full, under the five ideas and then by language feature.
Each rule is followed by its limits. A limit that a test pins names the
test.

A test of a limit asserts the edge that the analysis keeps although Python
makes no such call, so that a change which removes the edge, and with it
real calls of other programs, fails that test.

## Pipeline and modules

1. **Module discovery** (`program.py`, `imports.py`). Start from the entry
   modules and resolve each import against the package root on the file system.
   Modules inside the root are analysed; every other module is outside code. The
   package root is `--package`, or else the deepest directory that contains
   every entry module; module names are relative to it. A module that cannot be
   read or parsed is analysed as an empty module, and the output reports it as
   failed; the warnings that Python gives about the analysed code as it parses
   it (an invalid escape sequence) are not the analysis' concern and are
   silenced. An import that finds a binary module file under the root (an
   extension module) gives the outside module of that name. Of several files of
   one module name, one rule picks the module, for imports and entry points
   alike, whatever their order: the package, then the module file, then the
   binaries (`imports._candidates`), then the files that only entry points name
   (`a.pyw`, a script without a suffix), by path; the output lists the others as
   shadowed. The stub `x.pyi` beside a module file `x.py` is read for
   annotations and for the bases of its classes only (see *A module's own
   stub*); a stub is never a module. The other rules of imports are under
   *Imports*.
2. **Scopes** (`scopes.py`). A light pass over each AST decides which scope
   binds each name, by Python's rules computed from the AST (not from
   `symtable`, whose tables differ between versions), iteratively, so
   deeply nested code does not exhaust the Python stack. An annotation
   without a value (`x: int`) makes a name local but gives it no value, so
   a class body with only `x: int` has no attribute `x`. It names every scope
   and marks generator functions. It also records what the builder needs
   to follow names by definition: the names that other code rebinds, the
   names that each loop binds on its iterations, and the lazy imports
   whose names the module never reads.
3. **Builder** (`builder.py`, `expressions.py`, `flow.py`, `matching.py`,
   `patterns.py`, `annotations.py`). Walk each module's AST once, in
   statement order. Emit nodes and constraints, and carry the definitions
   of the names that it follows (idea 2). The builder never reads a
   points-to set. It walks constructs that it does not model, so the calls
   inside them are found; it does not walk code that cannot run. Long
   chains (`a + b + c + ...`, which nest on the left) are walked in a loop,
   so they do not exhaust the Python stack.
4. **Linking**. When all modules are built, make each module a field of its
   package (also the packages of an entry module that no import names,
   without analysing their source, as far as an import resolves them as
   packages: a module `ns.py` wins over a namespace directory `ns/`, so
   the entry `ns/a/b.py` is then not under `ns`) and copy the exported
   names of star-imported modules, transitively (see *Imports*).
5. **Solver** (`solver.py`, `semantics.py` and its parts). Propagate objects
   along the constraints with a worklist until nothing changes. Then run
   the fixpoint steps (see Part 3), which add what the solve cannot find
   alone, and solve again. Calls are resolved and call edges emitted here.
6. **Output** (`pycg.py`, `formats/document.py`).
   `CallGraphGenerator.document()` builds the document of
   `docs/format.md`. Every part is sorted, so the document does not depend
   on the order of the analysis. `output()` is its classic call graph
   (`pycg.formats.edges`). `output_points_to()` is the assignment graph,
   for tests only: each variable, field and return value with the sorted
   names of the objects that it may hold; a saturated node holds none that
   it can name.

   A built-in or frozen module of the running Python wins over any file of
   its name under the root, and so does a frozen submodule of a package that
   is not frozen: `importlib` is not frozen but `importlib.util` is, so
   `import importlib.util` runs a local `importlib/__init__.py` and then
   imports the frozen `importlib.util`. Submodules that are not frozen stay
   local, and a relative import of a frozen name (`from . import util` in
   that package) is local too. An import that fails still adds to the import
   graph the packages and modules that Python ran before it failed: for
   `import pkg.missing.sub`, Python runs `pkg/__init__.py` first, so `pkg`
   is analysed.

The AST is never walked again after the builder, and there is no cap on
iterations.

`semantics.py` holds `Analysis`, the program-wide state and the rules of
loads, stores and calls. Its parts are modules of their own: attribute
loads, stores and descriptors (`attributes.py`), class hierarchies,
lookups and metaclasses (`hierarchy.py`), argument binding
(`arguments.py`), containers, constants and iteration (`containers.py`),
special methods of statements and operators (`protocols.py`), the rules of
modelled builtins (`builtin_rules.py`), namespaces read by reflection
(`reflection.py`), outside values typed from the stubs
(`outside.py`, `stubs.py`), and the reading of annotations
(`annotations.py`). What the analysis knows of the builtins beyond the
stubs is one table, `builtin_models.py`.

## The assignment graph (idea 1)

### Objects

An object is identified by the place that creates it, never by the name it
is bound to. Objects compare by identity; the analysis interns the ones
that can be created more than once (modules, externals, instances, bound
methods). A creation site is `module:line:column#end_line:end_column`: the
end tells apart the constructs that start at the same place (`a.b.c`,
`(a + b) + c`), and the name of an object takes the part before `#`. A
program has many constants (pygments: 84k), so a `Const` has no fields
and computes its name when asked.

| Object | Identity | Notes |
|---|---|---|
| `Function` | definition site | `def`, `async def`, `lambda`. Knows its parameters and defaults, and for a generator function the nodes of what it yields and what is sent to it |
| `Class` | definition site | Knows the nodes of its base expressions; has one C3 MRO per hierarchy that its resolved bases allow, recomputed when a base expression gets a candidate; a node with every instance of it and of its subclasses |
| `Module` | dotted name | |
| `Instance` | class + creation site | The call (or `raise`) that creates it. One more instance per class, the *abstract instance*, stands for any object of the class, whoever made it (see idea 4) |
| `BoundMethod` | receiver + function | A function loaded through an instance, or through a class for a class method; also a method of outside code bound to its receiver |
| `Wrapper` | kind + call site | A `staticmethod`, `classmethod` or `property` object; its fields hold what it wraps |
| `Container` | kind + creation site | list, tuple, set, dict, generator expression (an async generator expression has kind `async_generator`), dict view, the containers of `collections` (see *Containers*); the `*args` and `**kwargs` of each function |
| `Const` | value, and whether it is the inexact alias | `str`, `bytes` and `int` literals (not `bool`) and f-strings without values; they select container fields |
| `Generator` | function, and whether it is the inexact alias | The result of calling a generator function; for an `async def`, an async generator (see *`async`*) |
| `Coroutine` | function, and whether it is the inexact alias | The result of calling a coroutine function (`async def` without `yield`); its methods are `types.CoroutineType.<name>` |
| `Super` | class + receiver | The result of `super()` |
| `BuiltinMethod` | receiver + method | A modelled method of a builtin type bound to its receiver (`xs.append`), named through its type (`types.GeneratorType.send`) |
| `ReturnsArgument` | library callable | What `functools.wraps(f)` or `dataclass(frozen=True)` returns: calling it returns its argument |
| `Closure` | closure name + result type | What `contextlib.contextmanager` or `functools.lru_cache(maxsize=n)` returns: a closure of the library, named where it is defined; calling it gives a value of its result type |
| `Fallback` | bound `__getattr__` | What a lookup gives for an attribute that no class defines; the load calls it |
| `Pattern` | prefix + suffix + case | A str built from a constant prefix and suffix and another value, and its `lower()` or `upper()` (see *Computed attribute names*) |
| `TypeForm` | site | A union `A \| B` or a subscript `X[A]` in an annotation or a type alias, with the nodes of its parts; only the reading of annotations acts on it |
| `External` | dotted name + steps past its root, and whether it is the class taken from an inexact value | A value of outside code reached by a path: modules, classes and functions, and for code without stubs any value. The steps bound the name (see *External names*); one external without a name stands for loads past the bound and for values of unknown type |
| `Typed` | stub class | An instance of an outside class that the stubs describe, named by the public name of the class (see *Typed outside values*) |
| `Saturated` | one per analysis | What a node holds once it would hold more objects than the cap: the objects that the analysis no longer tracks there; not an outside value (see *The solver*) |

### Nodes

- `Var(scope, name)`: a local name or a parameter. Scopes follow Python's
  rules: `global` and `nonlocal`, class bodies that nested scopes cannot
  see, comprehension scopes, `:=` targets, and private names (`__x` inside
  a class is `_Class__x`, without the leading underscores of the class
  name, also in attribute accesses and parameters, but
  not in keyword arguments). In a function inside a class, an unbound
  `__class__` is the class (Python's implicit cell, which `super()`
  without arguments uses). The cell of the innermost class wins over a
  variable `__class__` of an enclosing function; a `global __class__`
  declaration or a local binding of `__class__` in the method wins over
  the cell. A module-level name is `Field(module, name)`
  and a class-body name is `Field(class, name)`. The variable holds every
  value of the name; a read in statement order may get fewer (idea 2).
- A name that the module does not bind and that is a builtin (a name of
  the builtins stub, in any version and on any platform, but its private
  helpers and the classes that exist only in stubs, so that the result does
  not depend on the interpreter that runs the analysis; or a name that the
  interpreter gives every module and the stubs do not list, `__name__`,
  `__doc__`, `__spec__`, `__loader__`, `__package__`, `__debug__`) reads
  the module field (a star import may set it) and what `builtins.name`
  gives: `External(<builtin>.name)`, or for a variable of the stub a value
  of its type (`exit` is a `_sitebuiltins.Quitter`, so `exit(1)` calls
  `Quitter.__call__`; see *Typed outside values*). The module `builtins`
  is that namespace: `builtins.getattr` and `from builtins import getattr`
  give `External(<builtin>.getattr)`, which is a root, so the rules of
  modelled builtins apply to it.
- `Field(object, name)`: an attribute of an object.
- Container nodes: one field per constant index or key, `unknown` for the
  elements stored under other keys, and `keys` for the keys of a dict.
- `Return(function)`, `Yield(function)`, `Sent(function)`.
- `Temp(site)`: the value of an expression.

### Constraints

| Constraint | Source construct | Action when the points-to set of `x` gets object `o` |
|---|---|---|
| `dst ⊇ src` | assignment, argument passing, return | Add `o` to `dst` |
| `dst ⊇ x.attr` (load) | `x.attr` | Look up `attr` on `o` (*Loads*) and add the result to `dst` |
| `x.attr ⊇ src` (store) | `x.attr = v` | Add an edge from `src` to `Field(o, attr)`; run a descriptor's `__set__` (a property's setter). `del x.attr` runs `__delete__` (a property's deleter) |
| `dst ⊇ x[k]`, `x[k] ⊇ src` | subscripts, slices | On a container, read or write fields (*Containers and iteration*); on an instance, call `__getitem__`, `__setitem__`, `__delitem__`; on an analysed class, see *Subscripts of classes* |
| `dst ⊇ iter(x)` | `for`, comprehensions, unpacking, `yield from`, `list(x)`... | See *Iteration* |
| `call(site, caller, x, args, dst)` | `x(...)` | Call `o` (*Calls*) |
| operator | binary, unary and comparison operators | See *Special methods and protocols* |

**Implicit calls.** Implicit calls (`__iter__`, `__enter__`, operators,
descriptor accessors, attribute hooks) use the machinery of calls, and
they call back the functions that they pass to a builtin (see *Call
backs*). Which of them are reported as edges is a convention of the output
(see *What is reported as an edge*).

**The caller of a site** is the innermost enclosing function, lambda or
module. Calls in a class body or a comprehension belong to the function or
module around it, because classes and comprehensions are not nodes.

### Loads

A load `x.attr` acts on each object of `x`:

- `Module`: see *Imports* (the module-level variable, a submodule, or the
  module's `__getattr__`).
- `Class`, `Instance`, `Super`: see *Classes and hierarchies*.
- `Function`: `Field(function, attr)`.
- `Container`, `Const`, `Generator`, `Wrapper`: what a wrapper wraps
  (`__func__`, `fget`...), a modelled method as a `BuiltinMethod`, or else
  what the stubs say its type has (see *Typed outside values*).
- `External`: what the stubs say the name has, if they have its top-level
  module; else `External(name.attr)`, bounded as *External names* says.
  What the code stores on an external is not tracked.
- `Typed`: a member of its class in the stubs.

### Calls

A call acts on each object of its callee:

- `Function`: bind the arguments to the parameters (*Arguments*), emit the
  edge `caller → function`, and connect `Return` to `dst`; a generator
  function gives its `Generator` instead.
- `BoundMethod`: as `Function`, with the receiver bound to the first
  parameter.
- `Class`: see *Calling a class*.
- `Instance`: look up `__call__` and call it.
- `Wrapper` of a static method: call the function it wraps.
- `BuiltinMethod` and modelled builtins: emit the edge to the builtin's
  name and apply its rule from `builtin_models.py`. The arguments bind to
  the signature that the table declares, as for a function, so unpacked
  and keyword arguments reach the rule.
- `Typed`: call the `__call__` of its class (`functools.partial.__call__`).
  An instance of `type`, or of a metaclass that keeps `type.__call__` (a
  value annotated with a bare `type`), is a class that is not known:
  calling it instantiates that class, so the call gives no edge and an
  unknown result, never `<builtin>.type.__call__` (the edges of a class
  call are those of the class: *Calling a class*). Its other methods are
  those of `type` (`cls.mro()` calls `<builtin>.type.mro`). A function or
  method object is called likewise.
- `Closure`: emit the edge to its name, and give a value of its result
  type (see *Decorators and functions that return a parameter*).
- `External`: emit the edge `caller → name` (for an implicit call, see
  *What is reported as an edge*). If the stubs describe the name, the
  result is what its signatures return (see *Typed outside values*); else
  it is the external without a name, so `ext.Cls().method` names nothing
  (see *External names*). Outside code calls nothing that the analysed
  code gives it, except the builtins of *Call backs* and, as the second
  exception there, the replacement of `re.sub` and `re.subn`.

### Arguments

Positional arguments before the first unpacked one bind by position; extra ones
go to the `*args` tuple, one field per position. An unpacked list or tuple keeps
the positions of its elements; any other unpacked iterable, and every argument
after it, may bind to any later position. Keyword arguments bind by name (not to
positional-only parameters); the others go to the `**kwargs` dict, keyed by
name. An unpacked dict binds its constant keys by name and its other elements to
every parameter that accepts keywords. A keyword argument whose value the
analysis does not track still gives `**kwargs` its key. The elements of a
callee's `*args` and `**kwargs` exist only once something is passed to them: the
elements of an unpacked argument at unknown positions or keys bind once it has
gathered something. A default flows into its parameter at each call that may
omit the argument, and into the parameters of an entry point (idea 4). A
receiver binds to the first parameter, or, for a method with only `*args` (`def
run(*args)`, a forwarding wrapper), to `args[0]`, before the arguments.

**A call that cannot bind its arguments gives no edge.** Python raises
`TypeError` before the callee starts (`macro-benchmark/README.md` of the
evaluation repository, "Edges"). This is decided only where the
arguments are known in full: a
call expression without `*` or `**` arguments, its receivers, and the
`__new__`, `__init__` and `__call__` that it runs on what it calls (they
get the same arguments). The callee must be an analysed function without
decorators (`staticmethod` and `classmethod` aside), whose signature the
source gives. The call cannot bind when it passes more positional
arguments than the function has positional parameters and the function
has no `*args`, when a keyword names no parameter that accepts it (a
positional-only one does not) and the function has no `**kwargs`, when a
keyword names a parameter that a positional argument already fills, or
when a required parameter gets no
value. Such a call binds nothing, gives no edge and no result. Every
other call (implicit calls that the interpreter makes with arguments the
analysis does not track, call backs, a decorated function) keeps its edge.

- Limit: a class whose `__init__` cannot bind the arguments still gives
  the instance that Python's `__new__` made before `__init__` raised.

What an unpacked argument passes is gathered once per call site, in
unnamed nodes by position or keyword, and each callee binds those: a site
where many tuples or dicts meet many callees costs their sum, not their
product. Python unpacks the argument once, before the call, so an iterator
that unpacking creates (an instance from `__iter__`) is one object per
call site, whichever function the site calls. In the same way, `xs += ys`,
`xs.extend(ys)` and slice assignment iterate `ys` once per construct, and
each list that they extend gets one edge.

### Decorators and functions that return a parameter

A decorated name is bound to the result of applying the decorators from
the bottom up; the undecorated function or class flows only into the first
decorator. Each application is a call from the enclosing function or
module. `staticmethod`, `classmethod` and `property` make `Wrapper`
objects, as decorators or as calls.

An outside decorator may return its argument, as many do, or something
else: a name it decorates holds the outside result and the undecorated
function or class, also when the decorator is reached through an
instance's `__call__` or bound by a class method. The result of a
decorator without stubs has no name (*External names*), so `@ext.task def
job` makes `job()` call `job` and name nothing after `ext.task`. The same
holds for a decorator that is itself such an unnamed value: a factory
(`@ext.task()`), a method of an unnamed instance (`app = ext.App()` and
`@app.route("/")`), or a stored one; the decorated name keeps the
undecorated function or class, and the application gives no edge. An
ordinary call of an outside value returns none of its arguments
(`ext.make(f)` and `ext.make()(f)` give no `f`). An outside decorator
whose stub has the form `(x: T) -> T` (`typing.final`,
`abc.abstractmethod`, `functools.total_ordering`) returns what it
decorates. Four library callables return their argument where their stubs
do not say so: `functools.wraps`, `functools.update_wrapper`,
`dataclasses.dataclass` and `typing.cast` (whose stub gives the declared
type, not the value). `builtin_models.py` lists them, and they are
modelled so whether they are analysed or outside code. The decorator that
one returns is named as it runs (`dataclasses.dataclass.wrap` for
`@dataclass(frozen=True)`, `functools.partial.__call__` for
`@functools.wraps(f)`). The model replaces the body of an analysed one,
but it stays an analysed function: an implicit call keeps its edge, and it
is no outside callee.

Three decorators of the standard library return a closure that CPython
defines inside them, where their stubs give only a callable type
(`builtin_models.py`, `CLOSURES`): `contextlib.contextmanager` and
`contextlib.asynccontextmanager` return `helper`, which makes a
`_GeneratorContextManager` or `_AsyncGeneratorContextManager`, and
`functools.lru_cache` given an int or None returns `decorating_function`,
which makes a `functools._lru_cache_wrapper` (`Lib/contextlib.py`,
`Lib/functools.py`). The callable result of their stubs is that closure,
named where it is defined (`contextlib.contextmanager.helper`, as the
benchmark names it), and calling it gives the edge to that name and an
instance of the callable's result type. The decorated name holds the closure
and the undecorated function, as for every outside decorator, so `with
managed():` calls `contextlib.contextmanager.helper` and `managed`, which
the closure calls back. A call of a function that `lru_cache` or `cache`
decorates calls `functools._lru_cache_wrapper.__call__` and the function in
the same way; given a function, `lru_cache` and `cache` return the wrapper
at once, as their stubs say. Other library callables whose stubs return a
callable return the unnamed external (see *Typed outside values*).

- Limit: the overloads of `lru_cache` are not selected by the class of the
  argument (see *Typed outside values*), and both fit `@lru_cache` and
  `@lru_cache(maxsize=32)`. So a function decorated by a bare `@lru_cache`
  also holds `decorating_function`, which its calls name, and the
  application of `lru_cache(maxsize=32)` also calls the wrapper
  (`test_limit_lru_cache_is_not_selected_by_the_class_of_its_argument`).
- Limit: the context manager is not run, only made. The site that calls
  the decorated function gets the edges of the closure and of the
  generator function (a generator function is a callee of the site that
  calls it), although its body runs only when a `with` enters the context
  manager, maybe elsewhere; and what the generator yields does not pass
  through the context manager (a typed value drops its type argument), so
  `with managed() as value` gives `value` an unknown value, without what
  the generator yields
  (`test_limit_a_context_manager_is_made_where_it_is_called_and_yields_nothing`).
- Limit: the decorated name holds the function whatever it is. Stacked over
  a class method (`@contextmanager` then `@classmethod`), the helper calls
  an object that is not callable and Python raises `TypeError`; the
  analysis still calls the function and gives the context manager
  (`test_limit_a_context_manager_of_a_class_method_object`).
- Limit: the closure adds values to the decorated name (the wrapper, and
  the unknown result of the overload that does not apply), so a name can
  reach the cap where it did not before (see *The solver*): at a cap of 2,
  `@lru_cache(maxsize=32) def f` makes `f()` lose its edge to `f`
  (`test_limit_at_a_low_cap_the_closure_values_saturate_the_decorated_name`).
  At the default cap of 5,000 no measured package lost an edge.

A function that returns a parameter, where the parameter's own definition
reaches the `return` (for a name that is not followed by definition, where
the function never rebinds it), gives each call its own argument back. So
identity decorators and registries in the analysed code keep apart what
they decorate, and `return self` keeps receivers apart. The same holds for
a parameter that is a part of a returned conditional expression or
`and`/`or` that may give the result (`return second if first is UNSET else
first`): the value choice that evaluates such an expression (idea 2)
passes the parameter through, and its other parts are the function's own
result.

An element of `*args` at an int literal index `i` >= 0 (`return args[0]`)
is a parameter in the same way, under the same conditions on `args`: each
call gets what it may bind to `args[i]`. That is the argument at that
position, after the receiver for a method or `__new__` (for `def run(*args)`
the receiver is `args[0]`), and every argument that the call binds to an
unknown position of `args` (one at or after an unpacked iterable whose
positions are not known). A call with too few arguments gets nothing.
`args` passed on does not stop the rule: a tuple cannot change.

- Limit: a negative index (`args[-1]`) depends on the number of arguments,
  and `kwargs["key"]` reads a dict that the function or its callees may
  change: neither passes through, so each call gets what every call binds
  there (`test_limit_a_negative_index_or_kwargs_merges_the_results_of_every_call`).
- Limit: a parameter in an inner `and`/`or` passes through even where the
  outer one discards that operand (`return (candidate and enabled) or
  default` with `enabled = False` passes `candidate` too).

### Names in the call graph

The conventions of `evaluation/micro-benchmark/README.md` apply. A node of
the call
graph is named after its definition site: `mod.Class.method`,
`mod.outer.inner`, `mod.<lambdaN>` (numbered by the position of the
`lambda` keyword in the enclosing function, class or module),
`<builtin>.name`, `<builtin>.<type>.<method>` for the methods of builtin
types, and the dotted path of an outside name. A re-exported function
keeps one name. The nodes of the call graph are the analysed modules,
every function and lambda they define, and every callee; classes are not
nodes of it. Constants, and the fields of containers that they select,
are named with `ascii()`, so the assignment graph does not depend on the
Unicode database of the running Python. An int of more than 640 digits is
named in hexadecimal: Python may be set to refuse a longer decimal
conversion (`sys.set_int_max_str_digits`), and the names do not depend on
that setting.

### What is reported as an edge

Three conventions of the output, which the ground truths of the micro- and
macro-benchmark share, decide which of the calls that the analysis
resolves are reported as edges. They change what the output reports, not
what flows: the calls still give their results (`loop.create_future()` on
an `AbstractEventLoop` gives a future, whose `cancel` is an edge), and
`object.__init__` calls nothing that is given to it.

- **Implicit calls give no edge to an outside name.** An implicit call
  gives edges to analysed functions, but none to outside names (`r["x"] =
  f` on a subclass of `lib.Registry` calls the outside `__setitem__`
  without an edge); the ground truths count outside callees only for call
  expressions. A decorator application is an explicit call (`@ext.decorate`
  reports `ext.decorate`), and so is the `__init__` that a call of a class
  runs (`C()` with an outside base reports `ext.Base.__init__`); an
  `__init__` that an implicit call runs is implicit.
- **`object.__init__` gives no edge at a creation.** An instance whose
  `__init__` is object's gets no edge when it is created (micro-benchmark
  convention), but an explicit call (`super().__init__()`) does.
- **A method of an abstract outside class gives no edge.** A call of a
  method of a value whose concrete class is not known (a protocol, a class
  with an abstract method that no class of its MRO overrides, or a class
  that exists only in stubs: `asyncio.AbstractEventLoop`, `typing.TextIO`),
  or of a container of an abstract type, gives no edge (macro rule B4): the
  edge would name a class that does not run.

### The solver

A worklist with difference propagation (`solver.py`), in rounds: each
round propagates along the subset edges to a fixpoint, then applies the
constraints of every node whose set grew to its new objects.

```
repeat:
    while worklist:                        # propagation
        node = worklist.pop()
        delta = (union of the sets received since the last pop) - done(node)
        if SATURATED in delta or |done(node)| + |delta| > cap:
            done(node) = {SATURATED}; send it to every dst; continue
        done(node) = done(node) | delta
        for dst in subset_edges[node]:     send the set delta to dst
    for node whose done(node) grew:        # the constraints
        for c in complex_constraints[node]:
            apply c to each object of done(node) - fired(node)
        fired(node) = done(node)
until nothing was added
```

Applying a constraint may add subset edges, objects, constraints and call
edges; what it adds is propagated in the next round. It never removes
anything, so the solve is monotone. Each constraint sees each object of its
node exactly once, and when it does, the node holds everything that
propagation brings it in that round. A constraint attached to a node sees
at once what the node holds (what the last propagation left there), and
the rest in later rounds. The objects that the constraints add are
collected and reach each node as one set.

**Saturation.** A node that would hold more objects than the cap (5,000
by default, `DEFAULT_CAP`; see *Bounds*), or that receives the saturated
value,
holds the saturated value only (Wimmer et al., PLDI 2024, saturate type
flows in the same way). Its successors receive it; what its constraints did
with the objects of earlier rounds stays. The saturated value stands for
the objects that the analysis no longer tracks there. It is not an outside
value, and no rule ever sees it: when a node saturates, each of its
constraints gives the saturated value to the nodes where it puts what it
finds (`Constraint.results`: the result of a call, a load, a subscript, an
iteration, an `await`, a `with`, an operator, an `except`, an annotation)
and does nothing else. So the saturated value itself causes no edge, no object and no
constraint, and no rule asks what it is (a class? a constant key? a type?)
to take a branch for it. In particular:

- A call of it has no callee: the call expression gets no edge from it
  and, if it has no other edge, is unresolved with the cause `saturated`
  (see `docs/format.md`). Its result is the saturated value.
- A store into it is dropped; a key, a needle of `in`, a comparison, a
  truth test, a format or a hash of it does nothing.
- A class is unknown when the set of one of its base expressions or of
  its metaclass (written in `metaclass=` or inferred) holds the saturated
  value or an unknown class (`Hierarchy.unknown_classes`). Nothing about it
  is known, its own members included: the class and its instances are, to
  every rule, the saturated value (`opaque`, tested where the saturated
  value is), every lookup on it gives the saturated value, and no fixpoint
  decides its hierarchy. Its order could put any class anywhere
  (`class Child(Left, base)` with `Left(Root)` puts `Root` after `base`),
  and the methods that its own body defines may never be the ones that
  run (an inherited `__bool__` comes before an own `__len__`). Whether a
  class is unknown is decided between rounds, from the sets that the last
  propagation left, and fixed while the constraints apply. A call of an
  unknown class, or of what its instances give, is unresolved with the
  cause `saturated`, and the document's `mro` of an unknown class lists
  the class only.
- The dispatch never hands a rule the saturated value, an unknown class
  or an instance of one: neither as the object that a constraint applies
  to, nor as an object that the constraint holds (`Constraint.captured`:
  the arguments of an `Each`, the receiver of a binding or a delivery, the
  class whose bases it collects), nor as the method of a `__getattr__`
  that a lookup gave earlier (a `Fallback`); a rule that comes back to an
  object it remembered (the instances that a pattern of attribute names
  reached, the keys stored in a dict) goes through the same test
  (`Solver.revisit`); a rule that waits for the class of an instance runs
  before the class becomes unknown (see *Rules that wait*); and a
  hierarchy update skips an unknown class. What
  earlier rounds derived from an object before its class became unknown
  stays: the edges, the objects and the constraints.
- The test does not look inside the objects that it lets through: the
  receiver of a bound method, or the receivers that a descriptor call
  passes, may be an instance of a class that became unknown since; a call
  passes them on as arguments, to nodes, where the dispatch tests them.
- The document never names it: it is no export target, no callee, no
  outside name and no class of an MRO, and the assignment graph (for tests)
  does not list it either.

What the saturated value stood for is lost. Code that is reached only
through it is, for the analysis, code that no analysed code calls, and a
value that only it would have filled holds less, or nothing. So past the
cap, any rule that depends on how much a set holds (nothing at all, or no
more than another bound) may apply where it would not without the cap:
the entry points and the steps at a fixpoint (see *Entry points* and *The
fixpoint steps*), and the bound of four computed names (see *Computed
attribute names*). A cap may add edges as well as remove them:

```python
def fallback():
    pass


def real():
    pass


def leaf(cb=fallback):
    cb()


def first():
    return leaf


def second():
    return leaf


def third():
    return leaf


for factory in (first, second, third):
    factory()(real)
```

Python calls `leaf(real)`, and the analysis reports `leaf -> real`. With a
cap of 2, `factory` saturates, the call that passes `real` has no callee,
and `leaf` is a function that no analysed code calls: it gets its default,
and the analysis reports `leaf -> fallback`. The same holds for a key, a
base or a receiver that only a suppressed call would have supplied. And a
set that the cap leaves smaller but not empty may pass under another
bound: in

```python
class C:
    def a():
        pass

    def other():
        pass

    b = c = d = e = other


name = "a"


def first(value):
    global name
    name = value


# second and third alike
for setter in (first, second, third):
    setter("b")
    setter("c")
    setter("d")
    setter("e")
getattr(C, name)()
```

`name` holds five strings, more than the four that a computed attribute
name may hold, so the call is unresolved; with a cap of 2 the setters are
not called, `name` holds `"a"` only, and the analysis reports
`main -> C.a`. One case is avoided: the functions that reached a
saturated node themselves (bound, wrapped, or as methods of a class or
instance that did) may be what a call of the saturated value runs, so they
count as called (`Solver.absorbed`). Without the steps at a fixpoint, every
rule only adds and none sees the saturated value, so a cap only takes edges
away; `tests/test_saturation.py` checks that for each protocol and every
case of the micro-benchmark, and pins the edges that the steps add for the
programs of the review.

A saturated node costs one application of each of its constraints, where a
hub of generic code (a parameter that every strategy of a library reaches,
a registry of every lexer) cost its size times its constraints, and its
calls were noise. The solve still ends (see *Termination*), and the result
does not depend on the order (see *Order independence*).

A hub is generic code that calls every callable with every argument, such as
`func(*args, **kwds)` in `contextlib`: without context, each callable gets
each argument, so a solver that keeps a private copy of a set per node and
moves objects one at a time does work quadratic in the size of the hub.
`tests/test_scaling.py` measures the work of the solver without a clock, as
the objects written into sets, the constraint applications and the subset
edges that `Solver.work` counts, and checks that it grows about linearly
with the size of a hub.

Two mechanisms keep the cost close to the size of the result:

- **Shared sets (hash consing).** Every set is immutable and exists once; a
  table maps the content of a set to its one copy. A node refers to its
  set, and its inbox to the sets it received, so sending a delta along an
  edge copies nothing. The union and the difference of two sets are
  computed once and remembered: when many nodes hold the same set and
  receive the same delta, they share one union. The table is rebuilt from
  the sets that nodes hold when the sets created since the last rebuild
  hold more objects than those that survived it, and at the earliest when
  they hold 2^20 objects (`_SWEEP_NEW_OBJECTS_MIN`). Many nodes hold and
  receive the same sets, so the order of the objects of a set is kept with
  it; and many constraints that act on a few kinds of objects
  (`Constraint.kinds`) are applied to the same large sets (each lookup in
  a dict reads the keys of the dict for the instances among them), so the
  objects of those kinds are selected once and kept, for a set of at
  least 32 objects (`_KIND_SELECTION_OBJECTS_MIN`): for a smaller one,
  looking the selection up costs more than the constraint's own test of
  each object.
- **Cycle collapsing.** The nodes of a cycle of subset edges hold the same
  set at the fixpoint. When a successor already holds the same set as the
  node that sends to it (with hash consing, the same object), the edge may
  close a cycle (lazy cycle detection, Hardekopf and Lin 2007). Such edges
  wait; one search (Tarjan) finds the strongly connected components
  reachable from all their successors, walking each node and each edge at
  most once, and merges each into one representative (union-find). The
  solver searches when edges wait at three moments: before a propagation
  starts, so a cycle already known is one node before objects go round it;
  at the propagation's fixpoint; and during it, once the nodes it has
  processed since the last search, plus the edges along which they sent
  objects, are at least the nodes plus edges that search walked. So the
  searches during one propagation walk at most as many nodes and edges as
  that propagation did, plus the last search. The bound is per
  propagation, not for the whole solve: a later round may search again a
  part of the graph that did not change. A search per edge as it arrived
  walked the nodes after a point where many paths meet once per path; one
  search per fixpoint let the objects that wait in a known cycle go round
  it, copied to every node; counting only the nodes of a search let it
  walk a dense part of the graph after every few processed nodes
  (`test_scaling.py`, `test_solver.py`). When nodes merge, each one's
  successors outside the cycle catch up on the objects that the others
  saw, and its constraints in the next round, so every constraint still
  sees every object once. An edge that a constraint adds between two
  nodes that already hold the same set is a candidate in the same way.

A constant node (the value of a literal or a definition) holds one object
and never gets another; edges and constraints on it act at once and are
not kept. Its set stays in the table of sets. A program has many of them
(pygments: 116k), so a constant keeps only its set. A program has
millions of nodes with a successor, and most have one: a node keeps its
one successor itself, and a dict (successor to whether the edge started a
search for cycles) only for more. It has millions of `Each` constraints
too: of a bound method one keeps the function and the object, not the
method that Python makes for each use, and of one result node the node,
not a tuple. The solver counts its work in measures that do not depend on
the machine (`Solver.work`): objects written into new sets (a set that is
reused copies nothing), constraint applications, subset edges, nodes
processed, nodes merged, and nodes and edges walked by searches for
cycles. A chain of constraints that
attach constraints to nodes that already hold objects would nest calls
without bound; past 50 nested attachments (see *Bounds*), the application
waits for the solve. The rules that walk a class hierarchy (the MROs of a
class and its subclasses, the classes below a class for `type[C]`) take
the classes from a work list, so a long hierarchy does not nest calls
either. A field that a container gains notifies its observers through a
queue: a notification that adds a field to another container queues more
instead of nesting calls, so a long chain of copied containers (`a + b +
c + ...`) does not exhaust the stack in any order. Copying the fields of
one container to another is done once per pair: many sites copy the same
container to the same place (pydantic: half of 191,000 copies), and each
copy would add the same edges again for every field.

A program has millions of `Each` constraints and of nodes with a successor.
An `Each` keeps its function and the function's owner, not a bound method
(64 bytes), and its one result node itself, not a tuple of one (56 bytes).
Most nodes with a successor have exactly one, and a node keeps that one
successor itself, without a dict. The records that the analysis keeps for
each pair of an object and a site (the parameters that a call supplies, the
set of instances that the calls of a class make, an attached special-method
call) are shared between pairs where they hold nothing of the pair: on large
programs these records are most of the memory, millions of bindings and
implicit calls.

A node that no rule can read yet need not exist. A call of a modelled builtin
or of a stubbed function binds its arguments to the parameters of each
signature that it fits, and no rule reads most of those parameters (on sphinx,
1.2 million bindings, of whose parameters the rules read 12 %). For a plain
call to a plain signature (no `*` or `**` in either, no argument passed twice),
where a parameter has one source, the node of a parameter is made when a rule
first reads it, in the state that it would have had (`Solver.follower`). The
rules run only between propagations, and a propagation ends at its fixpoint: a
node bound in an earlier phase holds what its source holds (the same set, or
the saturated value with it), and a node bound in the same phase still waits
for what its source held. So the result is the same, also with the cap, and the
unread parameters cost no node, no edge and no propagation. The constant
defaults of such a signature are made at the binding in both cases, since the
solver numbers objects in the order in which their nodes are made.

### Limits of idea 1

- One node per parameter for every call (no calling context): see
  *Open problems* for what this costs on the standard library.
- One node per attribute and container element for the whole program (no
  flow-sensitive heap): a store adds to what an attribute holds and never
  replaces it.

## Local names by definition and code that cannot run (idea 2)

A name that only its own scope's statements bind gets the values of the
definitions that reach each read, not every value it ever holds
(`flow.py`; static single assignment for structured code). The builder
walks the statements of a scope in order and carries a state: for each
name, the node of the value of the definitions that reach the point, and
whether the name may be unbound there. A definition stores the node of the
value itself, so a plain assignment makes no node; a value that the
analysis does not track (`None`, a number) is a definition that holds
nothing. The state also records what `bool()` of each value may give, and
the literal values that the name may have (*Value choice*).

```
x = A()            x1 = Instance(A)
if flag:
    x = B()        x2 = Instance(B)
else:
    return         (this path ends: it does not reach the join)
x.run()            reads x2 only: edge to B.run
for item in xs:    loop head h = join(x2, the end of the body)
    x.close()      reads h
    x = C()        x3 flows into h
```

### Which names

A name bound in a module, class body, function or lambda is followed by
definition unless code other than the scope's statements may rebind it: a
nested scope that binds it through `global` or `nonlocal`, an assignment
expression in a comprehension (which binds it on each iteration), or code
that reads or writes the scope's names through its namespace. In a
module, that code is `from ... import *` (which may bind any name),
`globals()`, `exec`, `eval` or `sys.modules[__name__]`; in a function, it
is `locals()`, `vars()` without an argument, `exec` or `eval`. The syntax
decides it: a call of a name that the code does not bind. Those names, and the
variables of comprehensions, keep one node for every definition.

A read of a followed name gets the definitions that reach it when the
reading code runs in statement order with the binding scope: the scope
itself, or a class body or a list, set or dict comprehension inside it,
which run where they are written. Any other reader (a function, lambda or
generator expression nested in the scope, another module, `getattr` on the
module) runs at times that the statements do not decide, and reads the
variable, which every definition also flows into. So a module's own
top-level code reads its names in order, while its functions and other
modules see every value.

- Limit: a call through a qualified name (`builtins.locals()`) is not seen
  as a read of the namespace.
- Limit: a closure reads every value of a name it captures, not the one
  the name has when the closure runs.
- Limit: code that rebinds a module's name through the module object
  (`import m; m.x = v`, `setattr(m, ...)`) while that module's top-level
  code still runs (an import cycle, a call from the top level into code
  that patches the module) is not seen by the module's own later top-level
  reads: a followed module name read after such a call keeps the
  definitions of the module's statements. A rebinding through `global` in
  a function is not missed: that name is not followed, so every read sees
  every value.

### Definitions and reads

An assignment (each target, in order, after the value), `+=` and the other
augmented assignments, `:=`, the targets of `for`, `with ... as` and
`except ... as`, imports, `def`, `class`, `type X = ...` (no value) and the
captures of a `match` pattern define a name. Parameters are the first
definitions of a function: the parameter node holds what calls pass, and a
rebinding is another definition, so a method whose body assigns `self`
still gets receivers from the completion. `del x` and the end of an
`except ... as x` handler unbind the name. A `return` of a parameter whose
own definition reaches it returns each call's argument (see *Decorators
and functions that return a parameter*).

Reads follow the evaluation order of the language reference: an augmented
assignment reads its target before it evaluates the right-hand side; a
dict display evaluates each key before its value; a call evaluates its
callee, then its positional and unpacked arguments, then its keyword ones;
displays, subscripts, slices and f-strings evaluate from left to right.

### Paths, joins and loops

Where paths of control meet, each name that a path changed gets one join
node that the value of each path flows into. A path that ended (`return`,
`raise`, `break`, `continue`) does not reach the join. These are paths:
the branches of `if`/`elif`/`else`; the cases of `match` (each runs where
the cases before it did not match, and the definitions before the
statement reach its end if no case is `_` or a capture); and every
sub-expression that may not be evaluated: the operands of `and`/`or` after
the first, the arms of a conditional expression, the comparisons of a
chain after the first, and the message of an `assert`, whose path raises.
Comprehension conditions and bodies, lambda bodies and generator
expressions are other scopes, and default arguments are evaluated where
the function is defined.

A loop needs its definitions before the builder has walked its body. The
scope pass records the names that each `for` and `while` statement binds
on an iteration (in its target, its test and its body). At the loop, each
such name gets a head node that the definition before the loop flows into,
and the iterations read it; the end of the body and each `continue` add
edges into the head nodes, which exist already, so the AST is walked once.
The loop ends where its test is false (for `for`, at the start of an
iteration), which is where the `else` block runs; each `break` leaves to
after the `else` block. A `break` or `continue` outside a loop, a syntax
error, only ends its path.

### Exceptions, `finally` and `with`

An exception may leave from any point, so a handler starts from the join
of the state before the `try` and every definition made in its body. A
binding that the type expression of one clause makes is not seen by the
clauses after it. The clauses of `except*` run in order, each where those
before it ran (also when they raised) or did not, since every clause that
matches part of the group runs. A `finally` block starts from the join of
the state before the statement and every definition made in it (body,
handlers, `else` block). After a `try` with `finally`, the names that the
`finally` block binds have its definitions, and the others those of the
paths that end normally (the end of the body and of the `else` block, and
of each handler). A `break` or `continue` in the body, a handler or the
`else` block runs the `finally` block first, so it waits for the end of
the block: where the block ends normally, the jump goes on, still a
`break` or a `continue`, with the block's definitions of the names that
the block binds; where the block leaves (`return`, `raise`, `break`,
`continue`), that exit replaces the jump. `__exit__` may suppress an
exception, so what follows a `with` statement starts from the end of its
body or from any point of it.

- Limit: a `return` gives its value to the call's result where it runs,
  so a `finally` block that leaves does not discard that value.

### Value choice

A definition also records what `bool()` of its value may give, where that
cannot change: true for a function, a lambda, and a class without bases,
keywords or decorators (a metaclass may define `__bool__`; an empty `Enum`
is false; a module's class can be replaced by one that defines it); the
truth of a literal or of a tuple display; that of another name read in
order; and that of `not`, `and`, `or` and conditional expressions of
those. A list, set or dict display has none, because the container may
change; a decorated definition, a loop head and the value of a call have
none either. A truth is two bits (`TRUE`, `FALSE` in `flow.py`): the
value may be true, it may be false; a definition with no value has
neither, and one whose truth is not known has both. Definitions that meet
join their truths. `a or b` gives `a`
only if `a` may be true, and evaluates `b` only if `a` may be false (`and`
the other way round); a conditional expression evaluates the arm whose
truth its test may have. An operand or an arm that is not evaluated gives
no value and is not walked. A name read where it runs at other times has
no known truth, so `DEBUG = False` decides `if DEBUG` in the module's own
statements but not in its functions, which another module may run after
it changes `DEBUG`.

A definition also records the literal values that the name may have (str,
bytes, int, float, bool and `None`, which are immutable and compare by
value in the same way on every supported Python; each with its type, since
`True` and `1`, or `False`, `0` and `0.0`, are equal and hash alike but
`is` tells them apart), from literals, names, `not`,
`and`, `or`, comparisons and conditional expressions of those; any other
value makes them unknown. A comparison of literals whose values decide it
gives a known bool: `==`, `!=`, `<`, `<=`, `>`, `>=`, `is` and `is not`
(only between `None`, `True` and `False`, whose identity does not depend
on the interpreter), and `in` and `not in` a tuple, list or set display of
literals. So `mode = "fast"` decides `if mode == "slow":` and a `match` on
`mode` (see *`match`*).

### Class tests

In the branch where `isinstance(x, C)` holds, a read of a name `x` that
the scope follows by definition gets the values of `x` that may be
instances of `C`, and what an annotation `x: C` names (see *Annotations*):
every instance of `C` and of its subclasses for an analysed class, a typed
value for a class of the stubs (so `isinstance(content, bytes)` then
`content.decode()` calls `<builtin>.bytes.decode`), and each of them for a
tuple of classes. In the branch where the test fails, it gets the values
that may not be instances of `C`. `issubclass(x, C)` does the same with
classes. `inspect.iscoroutine(x)` is `isinstance(x, types.CoroutineType)`
(`CLASS_PREDICATES`), called through a name or a module that an import of
`inspect` binds. `callable(x)` tests the type of `x` for `__call__`: where
it holds, `x` gets its values that may be called, and where it fails those
that may not. A function, a method, a class and an outside function or
class are called; an exact constant, container, generator or coroutine and
a module are not; an instance of an analysed class may be called if some
MRO of its class finds `__call__`, and may not if some MRO lacks it (an
outside base counts where its stub declares it); a typed value whose stub
class declares `__call__` is called, and any other value (a typed value
without it, which a subclass may give one, an alias, an unknown value)
passes both branches.

```python
def load(parser, stream):
    if isinstance(parser, ConfigParser):
        parser.parse(stream)  # every instance of ConfigParser and below
    else:
        parser.close()  # what parser holds, but its ConfigParser instances
    parser.parse(stream)  # what parser holds
```

The branches are those of `if` and `elif`, the body and the end of
`while`, the arms of a conditional expression, the operands of `and` and
`or` that run after the test, and the statements after `assert`. A test
may be under `not`, under `and` (the branch where every operand holds) and
under `or` (the branch where none holds). After an `if` of which only one
branch goes on, the rest of the block is that branch: `if not isinstance(x,
C): return` (or `raise`, `break`, `continue`) gives the test to the
statements after it.

The value that the test gives is a definition of `x` that only the reads in
the branch see. The flow state keeps it beside the definitions
(`State.narrowed`), for as long as the definition that the test read still
reaches the read. Joins, loop heads, jumps, handlers, the end of a class
body and the variable get the definitions only. So a read after the
branch, or after a statement in the branch that rebinds `x`, sees every
value of `x` and nothing that the test added; so does a function or
generator expression nested in the branch, which reads the variable. A
list, set or dict comprehension in the branch, which runs in statement
order, sees the branch's value.

What the analysis knows of the class of a value decides whether it may
pass (`narrowing.py`):

| Value | Its class |
|---|---|
| an instance of an analysed class `D` | `D`, by its MROs |
| a `str`, `bytes` or `int` constant, a str pattern | exactly that builtin class |
| a container that the analysed code makes: a display, a comprehension, a constructor (`list(x)`, `dict(...)`, `collections.OrderedDict(...)`), the `*rest` of an unpacking, a pair of `enumerate` or `zip`, `*args` and `**kwargs`, the list and pairs of `inspect.getmembers`; a slice, a copy and a pair of `dict.items()` of such a container | exactly the class of its kind (`list`, `tuple`, `dict`, `generator` for a generator expression) |
| the generator or coroutine that a call of a generator or coroutine function returns | exactly `types.GeneratorType`, `types.AsyncGeneratorType` or `types.CoroutineType` |
| a typed value of a class `S` of the stubs | `S` or a subclass of it |
| a class (analysed or of the stubs) | `type` or a subclass of it |
| anything else (the alias of a value whose class stops being exact, below; a container that an annotation or a stub result makes, which stands for any value of its type; the namespace that reflection gives; a function; an outside value without a type) | not known: it passes every tested class, in both branches |

**Where a class stops being exact.** A constant, pattern, container,
generator or coroutine is exactly of its class from where the analysed
code makes it. It stops being exact where another object may stand for
it, and from there on the analysis passes its one alias, which is not
exact (`Containers.inexact`): the same elements (the same nodes),
function or literal value, and the same name. Three rules treat it
otherwise: class tests; the rules that make or change a pattern, which
give any value for it (see *Computed attribute names*); and a pattern
read, which reads every element stored under it as a key (see *Pattern
keys*).
A rule that reads the value of a constant reads that of its alias too:
the mode of an opened file (see *Typed outside values*), where a str
subclass with the value selects the same class.
An alias has no alias. The places where another object may stand for the
value:

- the namespace of a class body, as the class attribute: a metaclass
  (`E.A` of an `Enum` is a member, not its value), `__init_subclass__` or
  a decorator may replace it; in the body, the name is still the value;
- the result of a method that a subclass may override: a slice, a copy
  and a pair of `dict.items()` are exact only if their receiver is, and
  the result of `+` and `*` never is (the right operand may be a subclass
  whose `__radd__` runs first);
- the class taken from a value that is not exact (`x.__class__`,
  `Outside._class_object`): it names its kind's class for the methods but
  is marked inexact, so as a tested class it lets every value pass,
  `issubclass` does not know it, and a constructor called through it
  makes a container that is not exact. As a base or a metaclass it is
  the class itself (`Analysis.same_class`): C3 sees one class.

`iter()` of an exact collection is another object of a class of its own
(see *Iteration*): exactly `list_iterator` and so on, a builtin class below
`object` that the stubs do not have, so it passes a test of `object` and
of no other class that can be written.

For `issubclass`, the value is the class: an analysed class by its MROs, a
class of the stubs exactly, anything else not known.

- Where the test holds, a value passes if its class may derive from the
  tested class (or, for a class of the stubs `S` or below, if the tested
  class may derive from `S`); an instance of an analysed class whose MROs
  hold an outside base without stubs may derive from anything. An instance
  (or, for `issubclass`, a class) does not pass a tested analysed class:
  what the test adds already holds every one that may (`C.instances`
  takes the instances of each candidate subclass).
- Where the test fails, a value passes unless its class certainly derives
  from the tested class: for an analysed class, every MRO of it holds the
  tested class (or an outside base whose stub MRO does); an exhaustive
  order stands for hierarchies that may not.
- With a tuple of classes, a value passes where the test holds if it may
  pass for one element, and where the test fails if it may for every
  position of the tuple (a tuple whose length is not known lets every
  value pass there).
- `object` is the root of every class: every value may be an instance of
  it, and none may not. `isinstance(x, ())` is false: every value passes
  where it fails, and none where it holds, whatever is known of its class.
- Only a tested class whose instance check follows its MROs filters,
  because a metaclass's `__instancecheck__` and `__subclasscheck__` may
  answer anything (an ABC answers for the classes registered with it and
  by `__subclasshook__`, a runtime-checkable protocol by the members of
  the value). Such a class is (`Hierarchy.nominal_outside`):
  - a class of the stubs of `builtins`, or `Generic`;
  - a class of the stubs whose stub MRO has no class that declares a
    metaclass other than `type` (`IntEnum`: `int`, then `Enum` of
    `EnumMeta`), and, up to its first class of `builtins` or final class,
    no protocol, no class that exists only in stubs, no abstract class and
    no class of the modules `abc`, `typing`, `typing_extensions` and
    `_collections_abc` (the stubs declare no metaclass for the ABCs of
    `collections.abc`, so a missing metaclass proves nothing there); the
    stubs give the builtin classes protocol bases that they do not have at
    run time, so the MRO is read only up to them, and a final class
    (`types.CoroutineType`) is one from which no class derives, so its
    protocol bases do not answer for it either;
  - an analysed class whose metaclasses are all `type` and none of whose
    MROs holds an outside class that is not one of the above (an outside
    class without stubs included).

  Any other class (`numbers.Number`, `collections.abc.Iterable`,
  `io.IOBase`, an enum, a class of the analysed code built on `abc.ABC` or
  `Protocol`, an outside class without stubs), anything else that the
  class expression holds (a `typing` name, a value that is not a class),
  and a class expression, or a position of a tuple of classes, that holds
  nothing at a fixpoint let every value pass.

The decisions only let values through, and each looks at what only grows:
the values, the classes, and the MROs and metaclasses of an analysed
class, for which a decision waits as a lookup does and is redone when they
grow (`Hierarchy.relation`); it asks whether some hierarchy allows the
value, which only turns from no to yes. An empty class expression is
decided at a fixpoint, and only adds (see *The fixpoint steps*). So the
result does not depend on the order of the solve.

Cost. The values of a test are kept in groups by what is known of their
class, and each pair of a group and a tested class is decided once. A
position of a tuple keeps its classes as an ordered set, so a class that
arrives is found in one step, and where the test fails a group counts the
positions that it passes, one step per position. So the filter's own work
for a test of t classes on v values of c classes is v + c*t; the solver
delivers the values and the classes as for any constraint, and the question
that a decision asks of a hierarchy is one node per (class, tested class)
that every test shares. Each node of a class expression or of a position of
a tuple of classes is subscribed at most once per test, so a tuple that
contains itself, or tuples that share their elements, end
(`tests/test_scaling.py`, `tests/test_termination.py`). Once every value
passes a position, a value that is not a class can add nothing there, so
it stops at once; a class goes on, since its metaclass and its hierarchy
may saturate the result. A hub of values at a position of many tests ends
there (hypothesis: 5.8 of 7.2 million values).

- Limit: only the builtin `isinstance` and `issubclass`, with a name as the
  first argument and, as the second, a name, an attribute path or a tuple
  display of those. Attributes (`self.x`), subscripts, functions that test
  their argument (`is_thing(x)`), `type(x) is C`, `callable(x)`, `x is
  None` and `match` statements give nothing.
- Limit: only a name that the scope of the test binds and follows by
  definition; a name of an enclosing scope (read in a comprehension, or
  through `nonlocal`) gives nothing.
- Limit: where a path in the branch rebinds `x` and joins the others (an
  inner `if`), the join holds every value of `x` before the test.
- Limit: what a read in the branch gives on (`self.x = x`, `f(x)`, `return
  x`) takes the added value with it, as an annotated parameter does; a
  parameter that the function returns unchanged still gives each call its
  own argument back.
- Limit: an object whose `__class__` attribute is not its type (a proxy, a
  mock with a spec) is judged by its type.
- Limit: where a stub types a result by a type variable that an argument
  binds, the analysis takes the stub at its word: the result is the
  argument (or its elements), with its class. A function that returns
  another class there loses the branch that Python takes:
  `x = reduce(lambda acc, _: list(acc), [0], (f,))` gives the tuple, so
  `if isinstance(x, list): x[0]()` does not call `f`. The analysis trusts
  the stubs for what an outside call returns anyway; an alias at each such
  result cost 30% more time and 24% more memory on hypothesis and gave no
  edge on the benchmarks.
- Limit: a branch that holds fewer values may keep a node under the cap
  (see *The solver*) that saturated without the test, so calls there
  resolve and give more edges: on hypothesis, 24,737 more, nearly all of
  them outside names built past a function of an extension module, at 13
  sites that call a drawn value.
- Limit: an assert narrows as if it always runs. The analysis follows the
  default interpreter, where asserts run. Under `python -O` an assert does
  not run, so the statements after `assert isinstance(x, C)` also run with
  values of `x` that are not instances of `C`, and the analysis misses the
  calls on them (`test_limit_an_assert_narrows_as_if_it_always_runs`). On
  the 30 benchmark packages this misses 4 edges, all in h11, whose ground
  truth also counts runs under `-O`: `normalize_and_validate` and
  `get_comma_header` call `str.lower` and `str.split`.

### Code that cannot run

The builder does not walk code that the syntax and the definitions prove
cannot run: its calls give no edges, its definitions do not exist (a
function defined there is not a node), and its imports import nothing.

- A path ends at `return`, `raise`, `break` and `continue`, and at a
  statement none of whose paths go on (an `if` whose branches all return,
  a `try` whose body and handlers all end); the statements after it in the
  block are not walked.
- A branch of `if` runs only if its test may have the truth that the
  branch needs: `if False:`, `while 0:`, and `if DEBUG:` after `DEBUG =
  False` in the module's own statements.
- A `while` loop whose test is always true ends only by `break`; without
  one, what follows it and its `else` block cannot run.
- The message of an `assert` runs only where the test may be false; an
  `assert` whose test is always false ends the path.
- A statement whose expression, or the value that it assigns, is a call
  that cannot bind its arguments (see *A call that cannot bind its
  arguments gives no edge*) ends the path: Python raises `TypeError`
  there. This is decided while building, so only where the callee is
  known from the syntax: a name whose one binding in its scope is a `def`
  without decorators outside a class body
  (`ModuleScopes.function_definition`), and a call without `*` or `**`
  arguments (`warn(0, 13, msg)` for `def warn(major, minor, cause,
  fix)`).

  - Limit: a call nested in the statement's expression that cannot bind
    (`print(warn(0))`) raises too, but ends no path.
- The operands of `and`, `or` and conditional expressions are pruned the
  same way.
- A module that the analysis does not otherwise bind `__name__` in, and
  that is not an entry module, has its own name as `__name__`, so the
  block under `if __name__ == "__main__":` does not run in it. An entry
  module may run as `__main__` or be imported by another analysed module
  (in a package analysis every module is an entry module), so its
  `__name__` is not decided; nor is that of a module whose names code
  reads or writes through its namespace.
- `TYPE_CHECKING` of an outside `typing` or `typing_extensions` module is
  false at run time, imported by name or read as an attribute of the
  module (`typing.TYPE_CHECKING`, `t.TYPE_CHECKING` after `import typing
  as t`), so the block under `if TYPE_CHECKING:` cannot run. A function
  reads a module name at times that the module's statements do not decide,
  but a name that every binding statement of the module binds to the same
  import (see `ModuleScopes.imported`) holds that import whenever it is
  bound, so this holds in functions too. The block's imports import
  nothing and bind nothing at run time; the builder records what they
  would bind in `ModuleBuilder.type_only_names` (from the block of a test
  that is `TYPE_CHECKING`, or the `else` block of `not TYPE_CHECKING`), for
  the reading of annotations and nothing else.
- A module or a class body binds the names that it may bind at its end
  (and a module those that its functions bind through `global`): a name
  defined only under `if TYPE_CHECKING:` (a stub for a type checker), or
  deleted with `del`, is not an attribute of the module or the class, so a
  load of it calls the module's `__getattr__`, a lookup goes on to the
  class's bases, and a star import does not take it.

What stays reachable:

- A handler may run wherever its `try` body may raise, which is anywhere,
  so the code after a `try` with a handler stays reachable.
- A `with` body may raise before it ends, and `__exit__` may suppress the
  exception, so what follows a `with` statement stays reachable even if
  its body returns.
- Tests that depend on the interpreter or the platform
  (`sys.version_info`, `sys.platform`, `os.name`) have no known truth: they
  are attributes, not literals or names with literal definitions, so the
  results do not depend on where the tool runs.
- Every function body is analysed, since a function that no analysed code
  calls may be called from outside (idea 4); a function that never runs
  keeps the edges of its calls.

Constant folding by CPython's compiler removes some of the same code (`if
False:`); the analysis does not depend on it.

- Limit: every statement that the syntax and the definitions do not prove
  dead is assumed to run; any call may raise, and every handler may run.
- Limit: a package with its own top-level module `typing` is out of scope
  for the `TYPE_CHECKING` rule.

### Class bodies

A class's namespace is what its body binds by its end, so the class field
gets the definitions that reach the end of the body, not every one (`f =
staticmethod(f)` leaves only the static method). A name that the body
does not follow by definition (a body that calls `locals()`, `vars()`,
`exec` or `eval`) is in the namespace if code that runs binds it, with
every value that this code binds; the class statement treats it as any
other name of the namespace (see *The class statement*). Where a class
body may not have bound a name yet, it reads it from the module and the
builtins (`LOAD_NAME`), never from an enclosing function; a module name
that may be unbound reads the builtin too. A read of a name that the body
does not follow gets every value that the body binds, and, as the name may
not be bound yet, the module's and the builtin's.

- Limit: what the class machinery makes of a value that the body binds is
  not modelled: the class attribute is the value. A field of a
  `typing.NamedTuple` or of a `dataclass(slots=True)` is a descriptor in
  Python, and an `Enum` member wraps its value; a load (`T.field()`) and
  the class namespace (`T.__dict__["field"]()`) both call the default
  value, where Python raises `TypeError`
  (`test_limit_transformed_class_fields_are_the_values_as_a_load_gives`).

### In the assignment graph

A variable keeps its name in the output: the variable node gets every
definition (for any reader that runs at other times, and for the output),
and a parameter that the function rebinds gets a second node with the same
name, fed by the parameter, so the output shows the union under one name.
Join and loop-head nodes have no name. A class field shows what reaches the
end of the class body.

For the other parts of the builder: a construct binds a name with `_bind`
(None for an untracked value) and reads it with `_load_name`; a new
branching construct forks with `Flow.branch` and joins with `Flow.merge`.

## Outside code (idea 3)

When the stubs have the top-level module of an outside name (the builtins,
the standard library, and the third-party libraries that typeshed has
stubs for), what the analysis knows about it comes from them
(`outside.py`, *Typed outside values*). Code without stubs (other
third-party packages, missing modules) keeps the path names of *External
names*. The analysed package wins: a module under the package root is
analysed and never read from a stub, also when a stub has its name (a
package named like a stubbed library, or a vendored copy that the package
imports under its own name, `pkg._vendor.requests`).

- Limit: a stub describes the versions of its library that its
  `METADATA.toml` names (`requests ~=2.33.0`). The analysis cannot know
  which version the analysed code runs with, so a name that only another
  version has gives nothing, and a name that the installed version dropped
  still has its type.

### Stub data

The stubs of typeshed are read as data. `tools/generate_stubs.py`, a development
tool that is not installed and uses the standard library only, reads the stubs
of one pinned typeshed commit with `ast`, importing and executing none: the
standard library (`stdlib/`) and every third-party distribution (`stubs/`, all
of them: 201 at the pinned commit). It writes one JSON file per top-level module
into `pycg/analysis/stub_data/`, those of the distributions into its
`third_party/` directory, with the commit, each distribution's version and
typeshed's licence (Apache-2.0). `pycg/analysis/stubs.py` reads a file when the
analysis first asks for one of its modules, once per process (the format is
under *Format of the stub data*); a program that imports no third-party module
reads no third-party data. The rules ask the same questions of the data (a
module, a definition, a member of a class) at every object and site, and the
data does not change, so `Stubs` finds each answer once and shares it: a caller
does not change it. Nothing is imported, and the data depends neither on the
running Python nor on what is installed where the tool runs.

Which stub gives a module:

- The standard library and the distributions are read together, so a stub
  resolves the names that it imports from any of them (`requests` takes
  `Mapping` from `collections.abc`).
- A top-level name that the standard library has is the standard
  library's; a distribution's modules under it are left out (setuptools'
  `distutils`, the only one).
- A directory that holds stubs but no `__init__.pyi` is a namespace
  package: a module without names. Distributions may share one (`google`:
  `google.protobuf` from protobuf, `google.cloud.ndb` from
  google-cloud-ndb). A module that two distributions both define stops the
  generator; none does at the pinned commit.
- Every module is kept, also the helper modules that exist only in stubs
  (`_typeshed`, `_win32typing`): they define types.
- Directories whose name starts with `@` (`@tests`) hold no stubs.
- A distribution that `METADATA.toml` marks obsolete (the library ships its
  own types since a version: 8, among them `requests`) or partial (the stub
  describes part of the library: 10, among them protobuf and Pygments) is
  read like the others; the data's README marks it.
- A class's public name is a path through the modules of its own
  distribution (the standard library is one): a distribution that
  re-exports another's class does not rename it
  (`xml.etree.ElementTree.ParseError` does not become
  `defusedxml.ElementTree.ParseError`). So the standard library's data is
  the same with or without the distributions, byte for byte.

Per module the data keeps:

- functions: each overload a signature (parameters with their kind,
  whether they have a default, and their type; the type of the result;
  `async`);
- classes: bases, members, type parameters, whether it is a protocol,
  whether the class exists only in stubs;
- properties, variables, and references: imports that re-export (`from x
  import y as y`, `import x as x`), star imports, the names in `__all__`
  and assignments of names. An assignment of a value (`x = f()`) is a
  variable, of the class that it calls if it calls one. A name bound to a
  method of an instance that the module holds (`uniform = _inst.uniform`
  in `random`) is a function with the method's signatures, without the
  receiver.

A name in a stub resolves as for type checkers: a class body sees its own
names and those of the enclosing class bodies first, then the module's,
then the builtins'. A name on a cycle of imports resolves to nothing. The
parameters with two leading underscores (and no trailing ones) after the
receiver are positional-only, as stubs marked them before PEP 570. The
type parameters of a generic class are those of its `Generic[...]` or
`Protocol[...]` base if it has one, else those of its bases in order of
appearance (PEP 484), or those of `class C[T]`.

Every Python version and platform counts: all branches of
`sys.version_info` and `sys.platform` tests are read, and a name that they
bind differently keeps every definition (the data records no versions).
The implicit calls that the hand rules model take the union of the
supported CPython versions in the same way (see *Length hints*). A
class has a public name, its shortest path through public modules and names
(`asyncio.AbstractEventLoop` for `asyncio.events.AbstractEventLoop`,
`io.TextIOWrapper` for `_io.TextIOWrapper`), preferring a path from its
own module, then the first in alphabetical order. A nested class is named
through the public name of its enclosing class; a class without a public
path keeps its definition path. A type keeps classes, unions,
`None`, `Self`, `type[...]`, callables with their result (and their
parameters, when listed), type variables with their bound or their
constraints (a constrained variable, `AnyStr = TypeVar("AnyStr", str,
bytes)`, is one of the constraints, not any subclass of their union), and
two layers of generic arguments (see *Bounds*):
`list[tuple[list[str], int]]` keeps `tuple` and its arguments, and the
inner `list` without its own. Dropped:
`Any`, `ParamSpec`, `TypeVarTuple`, `Concatenate`, the parameters of
generic aliases (an alias stands for its definition, unsubstituted),
imports that a stub only uses, and the platform of a definition. A
recursive alias is unknown where it recurs. The parameters that a function
passes on (`*args: P.args`, `**kwargs: P.kwargs`, `*args: Unpack[Ts]`,
`*args: *Ts`) are `object`. `Literal` is the class of its values (an enum
member: its class), `TypeGuard` and `TypeIs` are `bool`, and `Annotated`,
`ClassVar`, `Final`, `Required`, `NotRequired` and `ReadOnly` are the type
that they wrap; a variable without a type (`x: Final = 1`) has the type of
its value. Lookups on a class walk a C3 order of
its bases in every version, ending with `object`; a base that the stubs do
not have is left out.

One fact of Python corrects the data: the two mixin methods of
`collections.abc` that return `self`, `Iterator.__iter__` and
`AsyncIterator.__aiter__`, return the receiver, where typeshed declares a
new `Iterator[T]` or `AsyncIterator[T]`; `Generator.__iter__` too, which
Python inherits from `Iterator` and typeshed restates as `Generator[Y, S,
R]`. `stubs.py` reads their result as `Self` (`RETURNS_SELF`), so a `for`
over an instance of a class that inherits `__iter__` from `Iterator` calls
the class's `__next__`, and an `async for` the `__anext__` of a class that
inherits `__aiter__` from `AsyncIterator`. The other mixin methods that
return `self` (`MutableSequence.__iadd__`, `MutableSet.__ior__`) are
declared `Self` by typeshed.

- Limit: other library methods that return `self` where typeshed declares
  another type keep typeshed's type: `io.IOBase.__iter__` (`Iterator[bytes]`),
  `contextlib.AbstractContextManager.__enter__` (a type variable of the
  class, unknown).

- Limit: a partial stub, or a stub that lacks a name, gives nothing for
  what it lacks, as the standard library's stubs do; without the stub the
  name would keep its path name (*External names*).
- Limit: a type that a stub takes from a library that typeshed has no
  stubs for is unknown (`requests` takes `HTTPResponse` from `urllib3`,
  which ships its own types).
- Limit: types that installed packages ship themselves (`py.typed`, their
  own `.pyi` files) are not read: the result must not depend on what is
  installed. The analysed package's own stubs are read for annotations
  (see *A module's own stub*).

#### Format of the stub data

A file is `{"modules": {name: module}}` with every module of one
top-level module (`os`, `os.path`). A module is `{"names": {name: entry},
"all": [...]}`; `all` is its `__all__`. The data is the union of every
Python version and platform. Every entry has a kind `k`:

| `k` | Entry | Keys |
|---|---|---|
| `"f"` | function or method | `s`, its signatures (the overloads, of every version); `d`, `"classmethod"` or `"staticmethod"`; `x`, abstract |
| `"c"` | class | `b`, its base classes (types, without `Generic` and `Protocol`); `m`, its members (entries); `tp`, its type parameters (type variable names); `proto`, a protocol; `final`; `tco`, a class that exists only in stubs (`@type_check_only`); `meta`, its metaclass; `pub`, its public name where it is not its definition path |
| `"p"` | property | `t`, its type; `set`, it has a setter; `x`, abstract |
| `"v"` | variable or attribute | `t`, its type |
| `"r"` | reference | `to`, the definitions it may be, each `[module, qualified name]` (an empty name for a module); `also`, for a definition that another version or platform re-exports from elsewhere, those places |

A signature has `p`, its parameters, `r`, the type of its result, and `a`
if it is a coroutine function (`async def`). A parameter is `[name, kind,
default, type]`: kind `"/"` positional-only, `""` positional or keyword,
`"*"` the `*args` parameter, `"k"` keyword-only, `"**"` the `**kwargs`
parameter; default 1 if it has one. Imports, re-exports and assignments
of names are references; a name that platforms or versions bind
differently has every definition. The target of a reference is never
itself a reference.

A *definition path* is the module that defines something, then its
qualified name (`re.Pattern.match`, `asyncio.events.AbstractEventLoop`).
A type is null (unknown: `Any`, or what the generator dropped), a string,
or a list:

| Type | Meaning |
|---|---|
| `"module.Class"` | an instance of that class (its definition path) |
| `"*none"` | `None`, or no value |
| `"*self"` | the type of the receiver |
| `["module.Class", arg, ...]` | an instance of a generic class with its type arguments, `"..."` for the variadic part of a tuple |
| `["\|", type, ...]` | a union |
| `["*type", type]` | the class itself (`type[C]`) |
| `["*call", result, params]` | a callable, with the types of its parameters, or null when they are not listed |
| `["*var", name]`, `["*var", name, bound]`, `["*var", name, union, "c"]` | a type variable, with its bound, or the union of its constraints (`AnyStr`: the variable is one of them) |

### Typed outside values

- **Names.** A load on an outside module or class gives what the stubs say
  it has. A module, class or function keeps the path through which the
  code reached it (`os.path.join`, as the convention names functions); a
  class attribute also finds what its metaclass defines (`ValueError.mro`).
  A variable or property gives a value of its type (`os.environ`); a
  variable that a module declares is a value of its type also when the
  code imports it by name (`from os import environ`). A name that the stubs
  do not have gives nothing.
- **Standard streams.** `sys.stdout`, `sys.stderr` and `sys.stdin` are
  `io.TextIOWrapper` objects, which the interpreter makes at start-up; the
  stubs type them as the abstract `TextIO`, whose methods give no edge
  (`builtin_models.py`, `VARIABLE_TYPES`). So `sys.stdout.write(s)`, also
  through a parameter whose default is `sys.stdout`, calls
  `io.TextIOWrapper.write`.
  - Limit: a program that replaces a stream (`sys.stdout = StringIO()`,
    `contextlib.redirect_stdout`) still has a `TextIOWrapper` there: what
    code stores on an outside module is not tracked; an interpreter started
    without a console (`pythonw`) has `None` there.
- **Opened files.** `open`, `io.open`, `os.fdopen` and `pathlib.Path.open`
  give the class that `io.open` makes for their mode and buffering, where
  the stubs give one overload per kind of mode (their `Literal` modes
  reduce to `str` in the data; `builtin_models.py`, `opened_class`): a
  text mode, or none, gives `io.TextIOWrapper`; a binary mode gives
  `io.FileIO` with `buffering=0`, else `io.BufferedRandom` with `+`,
  `io.BufferedReader` for `r`, `io.BufferedWriter` for `w`, `a` and `x`.
  What Python rejects with `ValueError` gives nothing: a mode with a
  letter other than `rwaxbt+`, with a repeated letter, without exactly one
  of `rwax` (`"rw"`), or with both `b` and `t`, and a text mode with
  `buffering=0`. Each str constant
  that reaches the mode adds its class, and each value of the buffering
  its own (an int constant is 0 or not; any other value is both). The
  alias of a constant (a class attribute, see *Where a class stops being
  exact*) counts by its value, as a str subclass with that value would.
  A mode that holds anything else, or nothing at a fixpoint (see *The
  fixpoint steps*), and a call with `*` or `**` arguments, give the class
  of each overload that the call fits, as other calls do. The selection
  only adds, so `with open(p, "rb") as f: f.read()` calls
  `io.BufferedReader.read` and no other `read`.
  - Limit: a member of an `Enum` that is not a `str` subclass is the
    alias of its value too, so it selects a class where Python raises
    `TypeError`.
  - Limit: the fixpoint step marks every argument that holds nothing at
    once. An argument that would get its value only through what another
    open marked in the same step returns (the first open's lines name the
    attribute that holds the second open's mode) is already unknown when
    the value arrives, so that open gives the class of every overload that
    fits, as without the rule. The result does not depend on the order of
    the solve; it is too wide, never too narrow. Marking in the order of
    the dependencies between opens would need a graph of which result
    reaches which argument, through calls, containers and computed names:
    machinery that this rule does not justify.
- **Typed values.** A value whose type is an outside class is `Typed`, one
  object per class (the type arguments are dropped). A method loaded
  through it is the outside function named by the public name of the class
  and the method, also when a base class defines it
  (`collections.OrderedDict.get`; `<builtin>.str.split`), bound to the value
  (to its class for a class method). The engine's own builtin objects
  (containers, constants, generators, wrappers) find the methods that the
  table does not model the same way, through their type
  (`<builtin>.list.index`, `types.GeneratorType.close`).
- **Abstract outside classes.** A value whose concrete class is not known
  (a protocol, a class with an abstract method that no class of its MRO
  overrides, or a class that exists only in stubs) is typed too; calls of
  its methods are reported as no edge (see *What is reported as an
  edge*).
- **Calls.** Calling a stubbed function binds the arguments to each
  overload that the call fits, by the number of its arguments and their
  keywords against the parameters and their defaults (to all overloads if
  it fits none), and gives the result of each. An `async def` gives its
  result, which `await` gives again. Calling a stubbed class gives a typed
  instance of it; calling a container class of `collections` gives a
  container (see *Containers*).
- **Results.** A class is a typed value. `object` and `Any` are the
  unnamed external: no name is invented (a path past a function, such as
  `json.loads.get`, never names a function). The builtin containers, the
  containers of `collections` (see *Containers*), and
  the abstract iterables and mappings of `typing` (`Iterator[X]`,
  `Mapping[K, V]`), are the engine's own containers, one per call and
  position in the type, with values of their element types, so elements
  keep flowing (`for m in re.finditer(...)`). A union gives each arm.
  `type[C]` gives the class.
- **`Self`.** `Self` is the receiver, and for an instance of the analysed
  code also the abstract instance of its class (a fluent method returns
  the receiver, a copying one a new object: `Path.with_suffix`). For a
  class of the analysed code, or a class method loaded through a class, it
  is an instance of that class (`date.today()`; `datetime.fromordinal(n)`,
  defined on `date`, gives a `datetime`). A module name that a stub binds
  to a class method of a class (`open = TarFile.open` in `tarfile`) is
  that method bound to the class, so `tarfile.open(p)` gives a `TarFile`.
- **Type variables.** A type variable that parameters have gives what the
  call binds to them (to `*args` too: `max(a, b, c)`; not to `**kwargs`,
  whose keys a type argument would lose): the argument (`copy.copy(x)`),
  the instances of a class passed as `type[T]`, the elements of an
  argument passed as `Iterable[T]` (`sorted(xs)`), or what awaiting an
  argument passed as `Awaitable[T]` gives (`asyncio.run(main())`; also
  `Coroutine[Y, S, T]`, `Generator[Y, S, T]`, `Future[T]`). A type
  variable that the call passes no argument to is its bound or its
  constraints (`AnyStr` is `str` and `bytes`), else unknown: one that no
  parameter has (a class's), and one whose parameters the call leaves out
  (`subparsers.add_parser("x")`, without `parents:
  Iterable[_ArgumentParserT]`, gives an `ArgumentParser`). An argument
  whose type has the variable where it is not read (`PathLike[AnyStr]`,
  `**kwargs: T`) binds nothing known: the engine's mappings keep their
  keys, which a type argument would not (`frozendict(a=f, b=g).get("x",
  f)` would give `g`). A constrained
  type variable (`AnyStr`, marked in the data) bound to a value is the
  constraint that the value is (`bytes` for `b"x"`; every constraint for a
  value of neither: no `bytearray` passes through). A callable result is
  unknown.
- **Special methods.** Iterating a typed value gives what `__next__` of
  what `__iter__` returns gives; a subscript what `__getitem__` returns; a
  `with` what `__enter__` returns; `async for` and `async with` await what
  `__anext__` and `__aenter__` return; an operator what the operand's
  method returns. These are implicit calls: no edges. `except E as e`
  gives a typed instance of a stubbed class.

Limits:

- A result is the union over the overloads that fit by arity and keywords:
  `subprocess.check_output(cmd, text=True)` gives `str` and `bytes`, and
  `re.fullmatch("x", "x").group()` gives `str` and `bytes`. Overloads are
  not selected by the types or the literal values of the arguments (but
  the mode of an opened file, above), so `print(x, file=f, flush=True)`
  does not call `f.flush` (the overload that flushes takes `flush:
  Literal[True]`, which the data reduces to `bool`).
- A result keeps the class of its stub where CPython chooses the concrete
  class at run time: the event loop of `asyncio.get_running_loop()`,
  `get_event_loop()` and `new_event_loop()` (by the platform and the event
  loop policy), the parser of `xml.sax.make_parser()` (by `PY_SAX_PARSER`
  and its argument) and the traversable of `importlib.resources.files()`
  (by the package's loader). The stubs give an abstract class
  (`AbstractEventLoop`, `Traversable`), whose methods give no edge, or a
  base class (`XMLReader`), whose methods are named in place of the
  subclass's (`ExpatParser.parse`). A table of the default classes, as for
  the standard streams, would find 0 / 1 / 12 missed edges on the
  macro-benchmark's batches 1, 2 and 3 (counted by reading), but none of its entries is a class that CPython
  always makes, so it is not built
  (`test_limit_a_result_whose_class_python_chooses_at_run_time_keeps_its_stub_type`).
- A typed value drops its type arguments, so `Match[str]` is `Match`, and
  `map()` and `zip()` give no elements. A future that outside code returns
  (`Future[T]`) is a typed value without its type argument, so awaiting it
  gives the future, not a `T`.
- The type variables of a generic alias are not substituted, so a
  parameter of `asyncio.create_task` or `asyncio.gather`
  (`_CoroutineLike[_T]`) binds nothing.
- Results typed `Any` and callable results give nothing known, but the
  closures of three decorators (see *Decorators and functions that return
  a parameter*).
- The result of `functools.partial` and of similar wrappers is a typed
  value: calling it gives the edge to `functools.partial.__call__`, and
  neither that call nor making the partial calls the wrapped function.

### External names

Outside code without stubs is named by the path through which the code reached
it. The root of a name is an import (including the module paths that `import
a.b.c`, `import a.b.c as x` and `from a.b import c` attach to their packages) or
a builtin. An attribute load extends a name by one step, up to two steps past
the root (see *Bounds*), and never with an attribute that is already among those
steps. An element of an external (iteration, subscript, `with`, `await`) is that
external, and so is an instance of an outside class found through a base class
or an `except` clause: `class Task(ext.Base)` makes `Task().run()` call
`ext.Base.run`, and `for x in ext.ITEMS: x.run()` calls `ext.ITEMS.run`.

The result of calling an external without stubs is the external without a name.
So nothing loaded from it, no element of it and no call of it names a callee:
`ext.f().a()`, `ext.f()[0].a()`, `ext.f()()`, `ext.Cls().run()`, `with ext.f()
as x: x.a()` and `x = await ext.f(); x.a()` call `ext.f` or `ext.Cls` and
nothing more, and the other calls are unresolved (`outside value`, see
`docs/format.md`). Every external that is not a root is made by one attribute
step from another, so the bound holds on every path. So `x = x.parent` adds one
name and `x = x.next()` none, and `p = os.path; p.join()` and `import
xml.etree.ElementTree` with its full path resolve. A load past the bound gives
the same external without a name: anything loaded from it is itself, it is
never a base class, and calling it gives no edge.

One name passes the bound by one step. A member that a lookup through an
analysed class finds in an outside base that the stubs describe is named one
step past that base, also where the base is at the bound: `class
Task(concurrent.futures._base.Future)` makes `Task().done()` call
`concurrent.futures._base.Future.done`, three steps past
`concurrent.futures`. The stubs give a class finitely many members, and a base
past the bound (a member class of such a base, `class P(R.ForkingPickler)`)
names no member, so no name has more than three steps.

The bound favours precise names over more edges. Generic parameters
collect externals from all callers; without the bound, loads on them make
names like `ext.a.keys.items` that no code calls, and their number grows
with every method name in the program. A name past a call result is such
a name: on hypothesis, 68% of all edges ended in names of an extension
module without stubs, nearly all built on the results of its functions,
and of 47,681 names one attribute past a call result 5 were real methods
(on `_pytest`, none of 55). On the ten
benchmark packages, naming none removes three wrong edges and loses no
true one.

- Limit: the types of outside code without stubs are not known.
- Limit: a method of an instance of an outside class without stubs is not
  named when the code makes the instance: `client = ext.Client();
  client.send()` gives no edge to `ext.Client.send`, and a class whose
  base expression is such a result (`class Model(ext.declarative_base())`)
  has no outside base.

### Call backs

A function that the analysed code gives to outside code is not called,
since what outside code does is not modelled. The exception is the
builtins that apply a function, which are part of the language: a call of
a function or class of the `builtins` module calls back an argument that
some overload that the call fits binds to a parameter typed as a callable
(or a union with one): `open(path, opener=f)`. Arguments bind by
position, keyword, `*` and `**` as for a function, after the receivers of
a method. The call back calls a function, bound method or callable
instance from the caller, with no arguments
(`evaluation/micro-benchmark/README.md`,
"Callbacks"); these calls are implicit. Classes are not instantiated. All
calls with one origin share one call back, and each passes its arguments
to it. `isinstance(f, C)` and `list.append(f)` call nothing. The builtins
with a hand rule (`builtin_models.py`) decide for themselves, and so do
the builtins that compare, which call their key on their items
(`sorted(xs, key=f)`, `min`, `max`, `list.sort`; see *Methods that
builtins call on their arguments*). One callable of `collections` is
called back too: the factory of a `defaultdict`, on a read (see *The
containers of `collections`*).

The second exception is the replacement of `re.sub` and `re.subn`, and of
the methods `sub` and `subn` of `re.Pattern` (`CALLS_BACK` in
`builtin_models.py`). Like the builtins, they are C code with a
documented call: a callable replacement is called with each match. So a
function, bound method or callable instance that the call binds to
`repl`, by position or keyword, is called from the scope of the call, as
`map` calls its function (a class is instantiated); a str replacement
calls nothing. The call back is implicit and passes one argument, the
match, which holds no value. No other library function calls back, also
where its stub types a parameter as a callable: on 15 packages of the
macro-benchmark, calling back every such parameter found the same 38 true
edges as `re.sub` alone, and 53 false ones (45 in one package, through
`inspect.iscoroutinefunction`, whose overloads take callables but only
inspect them).

- Limit: the match is not typed. A typed value drops its type arguments
  (see *Typed outside values*), so a `re.Match` there would give
  `m.group()` both `str` and `bytes`, and a `str` method called on it a
  false `bytes` edge: on the four known sets of the macro-benchmark, 22
  more true edges and 5 false ones.

### Methods that builtins call on their arguments

A function or class of the `builtins` module calls, on an argument that a
fitting overload binds to a parameter typed as a protocol, the methods
that the protocol declares, special or not: `print(file=f)` calls
`f.write` through `file: SupportsWrite[str]`, `abs(x: SupportsAbs[T])`
calls `__abs__`, `round(number: SupportsRound[T])` calls `__round__`,
`len(obj: Sized)` calls `__len__`, `int(x: ConvertibleToInt)` calls
`__int__` and `__index__`. A builtin with a hand rule (`str`, `format`,
`iter`, whose fallbacks the protocol does not give) calls through the
protocol only the methods that are not special, and its rule decides the
others. Of several protocols (overloads, arms of a union) Python uses the
first that the class implements, so each method is called where no
analysed class of the MRO defines a method of an earlier protocol: `int()`
calls `__int__`, else `__index__`. Where the argument is an instance of an
analysed class that defines the method, the call is implicit and comes
from the scope of the builtin's call, with no arguments; arguments bind as
for a function, unpacked ones too.

`sorted`, `list.sort` and `min` compare their items with `<`, `max` with
`>`: `__lt__`, or the reflected `__gt__` where no class defines `__lt__`
(`COMPARISONS`). The items are what a fitting overload binds to its
positional parameters: the elements of the one (`sorted(xs)`, the list
that `sort` sorts), or the values of several (`min(a, b)`); a `default` is
returned, not compared. With a key, Python compares what the key returns:
the key is called on the items, from the scope of the call (a class is
instantiated; `key=len` calls `__len__`), and its results are compared
instead of the items. An item or a result that is a class is compared by
the methods of its metaclass, and one that is a list or tuple by its
elements (see *Comparisons of containers*). Like a builtin with a hand
rule, these call through their protocols only the methods that are not
special.

Outside code other than `builtins` and the operations below calls no
method of the analysed objects it gets (`Thread.start` and `run`,
`Logger.warning` and a handler's `emit`, `ExitStack.enter_context` and
`__enter__`).

- Limit: the stubs list the buffer protocol before `SupportsInt` and
  `SupportsFloat` for `int` and `float`, and `Iterable` and
  `SupportsIndex` before `SupportsBytes` for `bytes`, where Python tries
  `__int__`, `__float__` and `__bytes__` first.
- Limit: a key written in the call is a key even if it is `None`, which
  has no object: `sorted(xs, key=None)` compares nothing, where Python
  compares the items. A key that only `**kwargs` may give leaves the items
  compared too.
- Limit: with an unpacked argument every overload fits, so `min(*[a, b])`
  also iterates `a`.

### Selected standard-library operations

A table of operations of the standard library (`LIBRARY_ITERATION`, keyed by the
canonical stub definition and the exact parameters whose arguments they iterate,
or `*` for every parameter that the stub types as `typing.Iterable`,
`typing.Iterator` or `typing.Collection`, at its top level or in an arm of a
union) calls the iteration methods of what they get, as CPython 3.12 to 3.15
does (probed with an iterable apart from its iterator). The stubs cannot state
it: `islice`, `chain`, `groupby` and `product` have one shape there (no bases,
`__iter__` and `__next__`), but `product` makes a tuple of its argument at once
and the others do not. A name that only looks like an operation (a package
function `islice`) is not one; an alias is.

| Operation | At the call | Where the object is advanced |
|---|---|---|
| `functools.reduce`, `math.sumprod`, `math.fsum`, `math.prod`, `operator.countOf`, `operator.indexOf` | iterate | (no object) |
| `math.dist`, `itertools.product`, `combinations`, `combinations_with_replacement`, `permutations` | make a tuple: iterate, ask the length (`LENGTH_HINT`, 3.12 and 3.13; every version counts); `math.dist` reads a tuple, also of a subclass of `tuple`, without either | nothing of the program; the items come in tuples |
| `heapq.nlargest`, `nsmallest` | `__len__`, `iter()`, `iter()` of that iterator again, advance it | (no object) |
| `itertools.islice`, `dropwhile`, `takewhile`, `filterfalse`, `compress`, `cycle`, `accumulate`, `pairwise`, `batched`, `zip_longest` | `iter()` | advance the iterators |
| `itertools.tee` | `iter()`, and `iter()` of that iterator again | each copy advances the iterator |
| `itertools.starmap` | `iter()` | advance; make a tuple of each argument bundle (iterate it, ask its length) |
| `itertools.groupby` | `iter()` | advance; a group, also one that another scope advances, advances the same iterator |
| `itertools.chain` | nothing | `iter()` of each argument and advance it |
| `itertools.repeat` | nothing | nothing of the program; each item is its `object` |
| `heapq.merge` | nothing | `iter()` of each argument, advance it, and `iter()` of that iterator again (it delegates to the last one with `yield from`) |
| `itertools.chain.from_iterable` | `iter()` of the outer iterable | advance it; iterate each inner iterable |

A lazy object is an engine container of the operation's class (methods
named by it, `itertools._tee` for a copy of `tee`, `itertools._grouper`
for a group) whose state holds the iterators (the iterables for `chain`
and `merge`). It is advanced by what advances an iterator: `next()`, its
`__next__` called explicitly or through a stored bound method, a loop,
unpacking, a builtin or an operation that consumes it (`list`, `sorted`,
`deque`, `"".join`, `sum`, `reduce`), and another lazy object when that
one is advanced. Making, storing, returning it and `iter()` of it advance
nothing. Advancing it from a scope and a site advances its sources from
there: library frames are transparent, so the calls belong to the scope
that advances the object, and a lazy object that only a client advances
gives no `__next__` edge, neither at the call that made it nor in the
function that returns it. A lazy operation's result type does not bind
its type variables by iterating the argument at the call (the deferred
binding of that definition's signature; another callable at the same call
keeps its own). Items pass through the objects that keep them (`islice`,
`dropwhile`, `takewhile`, `filterfalse`, the data of `compress`, `cycle`,
`accumulate`, `chain`, `chain.from_iterable`, `tee`, `merge`), as tuples
(`pairwise`, `batched`, the combinatorial ones), per position
(`zip_longest`, `product`: the arguments that `*iterables` takes keep
their positions, and the tuples have one shape per arity of the calls,
of unknown length where an unpacked argument or `repeat` hides the
positions; `compress` keeps its data apart from its selectors, also in a
call that unpacks them),
and as (item, group) pairs for `groupby` whose key is the item (no key,
`key=None` by keyword or position, or a key that `**kwargs` may omit);
`starmap` gives nothing. `zip_longest`'s `fillvalue`, `accumulate`'s
`initial` and `repeat`'s `object` are values of the result, at any
position.

One state stands for every call of one origin of an operation (the
implicit calls that copy a call expression, each with its receivers): each
merges its arguments into the state's nodes and gets its result, and what
a later one brings (a position, a fill value) is wired into every
activation made before; a call of another arity adds a tuple shape and
changes none, and the key becoming the item rewires what came before.

Each advancing of a lazy object from a scope and a site is one
activation: a result node made before its subscriptions, which every
request of that key joins, also a later one. The lazy objects are keyed by
their call origin, so activations are finite; a lazy object that is its
own source (`acc = chain(acc, x)` in a loop) reaches its own activation.
A saturated source passes the saturated value to the result node.

The builtin `map`, `zip`, `enumerate` and `filter` stay eager: they
iterate their arguments, and `map` and `filter` call their function, where
they are made (an approximation, C26), so a lazy object that one of them
gets is advanced there.

Limits, each pinned by a test:

- The callbacks of these operations (`starmap`'s function, the predicates
  of `takewhile`, `dropwhile`, `filterfalse`, `groupby`'s key,
  `accumulate`'s function and its `__add__`) are not called.
- Counts are not read: `tee(x, 0)` and `product(x, repeat=0)` iterate and
  `islice(x, 0)` advances, where Python does not
  (`test_limit_a_count_of_zero_still_iterates`); `nlargest(1, x)` asks the
  length, which its shortcut does not (`test_limit_nlargest_of_one_asks_the_length`).
- `heapq.merge` reads `__next__` by an ordinary attribute lookup, so an
  instance attribute wins in Python; the analysis calls the class's method
  (`test_limit_merge_advances_by_the_special_method`).
- A `groupby` key that a variable gives is taken as a key function, also
  where the variable may hold `None`.
- `Counter(mapping)` counts the keys of a mapping, and a deque that
  extends itself copies itself first: the existing rules of `Counter` and
  `deque` model neither.
- `math.dist` is in the table; `statistics` and the other Python modules
  of the standard library are not.

## Declared types (idea 4)

The analysis models no caller outside the analysed code: a call edge exists
only where analysed code makes the call. Two rules give values to
parameters that no assignment reaches:

1. **A function that no analysed code calls is an entry point:** its
   receiver is any instance of its class or of a subclass that inherits
   it, and its parameters take their defaults.
2. **An annotation names the values that a parameter, or the target of an
   annotated assignment, may hold.**

A class test (`isinstance(x, C)`) declares the same of a local name in the
branch where it holds (see *Class tests*).

### Entry points

Rule 1 is part of the completion (Part 3), done once per method and
function:

- The first parameter of a function defined in a class body (or `args[0]`
  for `def run(*args)`) that holds nothing gets every instance of the class
  and of its subclasses that inherit the method. Decorated with
  `classmethod`, it gets the class and its subclasses that inherit it, by
  the class hierarchy (also a subclass that has no instance); decorated
  with `staticmethod`, nothing (the decorator's name in the source
  decides). `__new__` takes the class first, so its first parameter gets
  the classes, as a class method's does.
- A subclass inherits the method when, in some MRO of it, the first
  analysed class body that defines the name is the method's class, or
  binds the method itself there (`run = Base.run`, also wrapped in a
  static or class method), which each fixpoint reads (in an exhaustive
  order, when the order holds the method's class).
- Limit: a subclass that binds the method under another binding mode
  (`run = classmethod(Base.run)`) passes its class, not its instances;
  the analysis gives the instances
  (`test_limit_a_class_method_alias_keeps_the_instances`). An instance of a
  subclass that overrides `m` reaches `C.m` only through `super().m()` or
  `C.m(self)`, which are analysed calls that value flow follows. Each
  fixpoint checks the instances again, so an instance or a hierarchy that
  arrives later is added; a class (an instance of a metaclass) is not
  checked. Saturated and unknown values pass as before.
- A function that no analysed code calls gets its defaults; elsewhere a
  default flows at each call that may omit the argument.
- A class is among the instances of each analysed metaclass of it, so the
  receiver of a metaclass method that no analysed code calls gets the
  classes (see *Metaclasses*).
- None of this applies to code that reached a saturated node (see *The
  solver*): a call of the saturated value may run it, so it counts as
  called. Code that only a call through it reaches does not, and is
  completed as any code that no analysed code calls.

**Abstract instances.** Every class has one abstract instance, which
stands for any object of the class, whoever made it. A class has none when
Python certainly makes no object of it (see *Classes that Python does not
instantiate*): Protocol's initializer or `object.__new__` refuses it. A class whose MROs all derive from `type` is a metaclass and has
none either: its objects are classes.

Limits, each pinned by a test:

- A wrapper that a decorator returns (`def wrapper(*args)`) is no function
  of the class body and gets no receiver
  (`test_limit_a_decorators_wrapper_gets_no_receiver`).
- A method that analysed code calls on one receiver does not get the
  others, although outside code could pass them
  (`test_limit_a_method_that_analysed_code_calls_keeps_those_receivers`).
- An outside base between the subclass and the method's class may define
  the name; the subclass is taken to inherit the method.
- A function gets no arguments from callers that the analysis does not see
  (`test_limit_no_arguments_from_callers_that_the_analysis_does_not_see`).

### Annotations

The annotation of a parameter names (`annotations.py`):

- an analysed class `C`: every instance of `C` and of its subclasses; for
  `type[C]` (`typing.Type`), `C` and its subclasses;
- a class of the stubs: a typed value of it, as a call result of that type
  is, and for `type[C]` the class (a concrete outside type gives the edges
  of its methods; an abstract one gives none, see *What is reported as an
  edge*); and, for an abstract class, also every instance of each analysed
  class below it, and for `type[C]` those classes (see *Analysed classes
  below an outside class*);
- `Optional[...]`, `Union[...]`, `A | B`: what each arm names;
  `Annotated`, `Required`, `NotRequired`, `ReadOnly`, `Final`, `ClassVar`:
  what the first argument names;
- one level of a standard container or iterable (`list`, `Sequence`,
  `Iterable`, `Iterator`, `Generator`, `set`, `frozenset`, `deque`,
  `tuple`, `dict`, `Mapping` and their `typing` names): one container per
  parameter and kind, whose elements (a mapping's values, a generator's
  yield type, every position of a tuple) are what the arguments name; a
  container of `collections` (`deque`, `OrderedDict`, `defaultdict`) is a
  container of its class, whose methods are named by it; the analysed
  classes below the container's class are named too when it is abstract,
  as for any class of the stubs (a subclass of `list` for `Sequence[int]`,
  none for `list[int]`);
- for `*args: T` the elements of the `args` tuple, for `**kwargs: T` the
  values of the `kwargs` dict;
- a subscripted analysed class (`Box[int]`): its instances.

Anything else names no value of the package: `object`, `type`, `Any`,
`ModuleType`, a `typing.Callable`, a type variable, a `Literal`, an
outside class without stubs (scope rule B2 of the macro-benchmark).
`object`, `type`, `Any` and `ModuleType` are concrete classes of the stubs,
so they name no analysed class below them either (`class Mock(Any)`,
`class Lazy(ModuleType)`). `collections.abc.Callable` is abstract: it
names the analysed classes that derive from it. The names of `typing` are
annotation vocabulary, not classes.

The builder reads annotations from the AST. Annotations are not evaluated
where they are written, so a name in one is resolved against what its
scope binds at any time (the variable that every definition flows into,
and for a class body also the module's), not against the definitions that
reach that point: a class or an alias defined later in the module is
found, and so is a class's own name in its methods. Imports and aliases
resolve, and so does a name that an import under `if TYPE_CHECKING:` would
bind (which binds nothing at run time), as that import would, through the
builder's table of type-only names (the reading of annotations is its only
user; it imports no module and registers none, not even an extension
module that the lookup meets). A submodule `p.n` that such an import names
is read as the attribute `n` of `p` (see *Imports*). A string is parsed; the sites inside it are
positions in it, also for a string nested in a string. Python never
evaluates a string annotation, so an attribute in one is looked up as a
name, without running a hook: what a module binds, what a class defines in
its MROs, the name of an outside object; no `__getattr__` runs and no
descriptor, so a name that only a hook gives names nothing
(`test_a_string_annotation_runs_no_attribute_hook`). A shape that names
no type (a call, a lambda, a comprehension) gives nothing.

`tuple[()]`, the annotation of the empty tuple, is a subscript with no
arguments. It names a tuple, as `tuple[int]` does, and `type[tuple[()]]`
names the class `tuple`.

A union or a subscript becomes a `TypeForm`, one per site, that holds the
nodes of its parts. A name bound at module or class level to a union or a
subscript (`T = A | B`, `T: TypeAlias = ...`) also gets its `TypeForm`, once
one of its operands may be a type (a class, a form, an outside class or a
`typing` construct), so an annotation that names the alias, also in
another module through an import, reads it. An annotation that subscripts
the alias (`AnyIterable[int]` with `AnyIterable = Union[AsyncIterable[T],
Iterable[T]]`, or a `type` alias with type parameters) reads the alias too;
the type arguments are ignored, as those of a generic class are. An ordinary subscript or `|`
gets none, and a rule that acts on a name or a key (`getattr`, a
subscript) ignores a `TypeForm`. `type T = ...` always binds its form. The
type constructors are recognised at solve time by the last part of the
outside name that the subscripted value holds (`typing.Optional`,
`<builtin>.list`, `collections.abc.Sequence`). Reading follows the forms
through constraints; each (annotation node, destination, shape) is read
once, so a recursive alias ends. A class or an alias that a subscript
reads is read as the node that holds only it, under the same rule, so an
alias whose form subscripts itself or another alias that subscripts it
(`type Loop[T] = Loop[T]`, `A = List[T]` then `A = A[T]`) ends too.
Inside a container, a container or a `type[...]` names nothing.
`tuple[()]` has no arguments: a container or another generic class names
what it names without them, and a form that names what its argument names
(`Optional`, `type`) names nothing.

A dataclass-like class (decorated with `dataclasses.dataclass`, also
`dataclass(frozen=True)`, or a subclass of `typing.NamedTuple`; decided at
solve time from the values of the decorator and the bases) has an
`__init__` that the library makes from its class-level annotations, which
initialises every instance: each annotated field of every instance of the
class and of its subclasses holds what its annotation names. A class-level
annotation without a value of any other class names nothing (with a value
it is an annotated assignment, below); a `TypedDict` value is a
dict, read by subscript, so its annotations are no fields
(`test_a_typed_dict_gives_no_attributes`).

**Annotated assignments.** An assignment with an annotation (`x: T = v`,
`self.parsers: list[Parser] = []`, at any level and to any target) stores
what `T` names as well as `v`, read as the annotation of a parameter is
(the containers that it makes are keyed by the target's position). The
annotation declares what the target holds from that binding on, so it
supplies the values that later stores from outside code bring (a list that
the client fills). An annotation without a value (`x: T`) names nothing,
in a function, at module level and in a class body that is not
dataclass-like: Python binds nothing there (in a function it does not even
evaluate the annotation), so no store exists to add the declared values
to. A dataclass-like class differs because the library turns each such
annotation into a store, that of its generated `__init__`.

**Analysed classes below an outside class.** An annotation that names an
outside class names the analysed classes below it only when that class is
abstract. Abstract means that the class cannot be instantiated as it is: a
protocol, a class that exists only in the stubs, or a class whose MRO has
an abstract method that no class before it implements (`Stubs.abstract`).
For a concrete outside class (`list`, `dict`, `BaseException`, `Enum`,
`object`, `type`, `Any`) the annotation already names a value, an instance
of that class, so its analysed subclasses are as unlikely as any other
value. The protocols that the builtin types implement, `Iterable`,
`Iterator`, `Collection`, `Container`, `Sized`, `Hashable` and
`Reversible` (of `typing` and `collections.abc`), name a class below them
only through abstract classes: some outside base of the class reaches the
protocol by stub bases that are all abstract (`Stubs.abstract_reach`;
`class Line(Sequence)` and `class Countdown(Iterator)` count, a subclass of
`list`, `str`, `tuple`, `dict` or `NamedTuple` does not, nor does a class
of the stub-only base `tokenize._TokenInfo`, abstract itself but a
`NamedTuple`). A class that reaches one only through a concrete class is a
builtin value, and a client most likely passes a builtin one. This is a
policy for what an annotation supplies, not Python's subclass relation: a
subclass of `list` is an `Iterable`, and a value of it that the program
passes is called as any value is. On hypothesis (6.170.12, the package
alone) the rule adds 308 edges to 20,200 and removes none, with no
saturated site; admitting the protocols through concrete classes as well
gives the same graph there.

An analysed class is below an outside class `B` when one of its MROs
reaches `B` through the stub MROs: a candidate base of it, or of one of
its analysed bases, is an outside class whose stub MRO holds `B`
(`class Chain(AsyncIterator)` is below `AsyncIterator` and
`AsyncIterable`; a subclass of `list` is below `Sequence`). Classes are
compared by their stub definition, so a name of `typing` and the
`collections.abc` class that it stands for are one class. `type[C[...]]`
of a container names the classes below `C` as `type[C]` does
(`type[Sequence[int]]`). Only the declared hierarchy counts: a class that only has
the methods of an outside class or protocol (`__aiter__` and `__anext__`
without deriving from `AsyncIterator`), or that is registered with it, is
not below it, although `isinstance` accepts it. The classes below an
outside class are known only as bases arrive during the solve, so the rule
follows the one for analysed classes: when a class gets an outside
candidate base, its node of instances joins the node of the instances below
each class of that base's stub MRO, as it joins the node of an analysed
base, and its class family joins their class node; an annotation that
names an outside class reads these nodes. Both sides only add, so the
result does not depend on which comes first.

**A module's own stub.** A package may ship its annotations in a stub
beside a module: `x.pyi` in the directory of `x.py` (`pkg/__init__.pyi` for
`pkg/__init__.py`). Where the source gives a parameter, a class attribute or
a module variable no annotation, the annotation of the same name in the
stub is read as if it were written in the source, under the rule above and
its limits: a parameter takes the stub's annotation of the parameter of its
name and kind (named, `*args`, `**kwargs`) in the function or method of the
same path (`C.m`); an assignment to a name (`x = v`, not unpacking) that
binds a class variable or a module variable (also through `global`) stores
what the stub's annotation of that variable names as well as `v`, as
`x: T = v` does. Names are as Python stores them, in the source and the
stub alike: in the class `C`, `__x` is `_C__x` for a variable, a name read
in an annotation, an attribute in an annotation (`m.__x`), a member that
an import takes (`from m import __x`; a submodule that the import runs
keeps the written `m.__x`) and a module that an import names
by one name (`import __m`, `from __m import x`; a dotted name is not
mangled). The builder imports source modules by the same rule. An
annotation in the source wins, for the whole variable: any annotation of
it in that class body or module, with or without a value and wherever it
stands, keeps the stub's annotation off every assignment to it. Every
definition of the name in the stub counts, so an `@overload` set, and the
branches of an `if` (version tests, `TYPE_CHECKING`), name the union of
what their annotations name. A name in a stub annotation resolves as
Python resolves it in the stub: in the annotation's class body, else in the
module, else among the builtins. Each binding that it has in the first
scope that binds it contributes (a binding under an `if` or a `try` of
that scope counts): an import, what a type-only import of it binds,
without loads (so no hook runs) and without registering a module; a class
statement, the source's class definitions of the same qualified name; any
other binding (an alias, a variable, a function), nothing.

The bases that the stub declares for a class count for what an annotation
names, and for nothing else: the source's class definitions of the same
path are below each outside class that a base names (subscripts dropped:
`class Peek(Iterator[_T])` for `class Peek:` puts `Peek` below `Iterator`
and `Iterable`), as if the source declared that base, under the rule
above. The source's own bases count too, so a stub that contradicts them
adds its classes (`class C(list)` with the stub `class C(Iterator[int])`
is below `Iterable` through `Iterator`). The stub's bases never give an
inherited method, never change whether the class has instances, its MROs
or `super()`: lookup is the source's. A base that names an analysed class
adds nothing, a limit of scope: the declared relation could follow it
without changing the source's hierarchy, but no case asks for it. The
bases are one node per class statement. When it saturates, as any node
past the cap does, it admits nothing more: the classes that it already put
the class below stay (rules only add), those that would arrive later are
lost, and the source's hierarchy is untouched
(`test_a_stub_base_node_that_saturates_late_keeps_what_it_admitted`).

Nothing else of the stub is used: it defines no function, class or
variable, a name that only it defines is ignored, its calls and return
types give nothing, and its imports bring in no module. A stub without its
`.py`, a stub that cannot be read or parsed, a stub with a `global` or
`nonlocal` statement, and a `-stubs` directory are
ignored. The macro-benchmark counts these stubs as annotations (rule
B4).

Limits:

- An annotation is believed even when the calls pass something else
  (`test_limit_an_annotation_is_believed_when_the_calls_pass_something_else`).
- Python never evaluates the annotation of an assignment in a function,
  but its names are read as every annotation's are, so an attribute hook
  that one would run (a module's `__getattr__`) is an edge of the function
  (`test_limit_the_annotation_of_a_local_assignment_is_read_as_if_evaluated`).
- Annotations name values only for parameters, the targets of annotated
  assignments and the fields of dataclass-like classes, and only analysed
  classes and classes of the
  stubs: not return types, not the keys of a mapping, not more than one
  level of containers.
- A `Protocol`, analysed or outside, and an outside abstract class name
  their analysed subclasses, not the classes that match them structurally
  (`test_limit_an_outside_class_does_not_name_a_class_that_only_fits`).
- An annotation of an abstract outside class names every analysed class
  below it, also where the package does not play that role (a set-like
  class for a parameter annotated `AbstractSet[str]` that is only ever
  given sets).
- An annotation of a concrete outside class names no analysed class below
  it, and one of a protocol of the builtin types none that reaches it only
  through a concrete class, also where the package passes one: an analysed
  exception for `BaseException`, a subclass of `list` for `Iterable`
  (`test_limit_a_builtin_protocol_names_no_class_below_it_through_a_concrete_class`).
- The admission through abstract classes, with the stubs' bases, has a
  measured cost. On the 40 development packages, the 30 older ones get 41
  false edges inside the package and no true one (cachetools 20,
  marshmallow 20, h11 1); more-itertools gets 2,142 true and 334 false
  edges, 182 of the false ones at parameters whose annotation is wider than
  the documented contract (numbers, mappings, matrices and the helpers
  they reach). Batch 6's recall inside the packages rises from 0.383 to
  0.788, and its precision falls from 0.975 to 0.915.
- The stubs' `Collection` does not derive from `Sized`, where Python's
  does, and classes are compared by their stub definitions: a subclass of
  `Sequence` is not below `Sized`.
- A stub base that names an analysed class adds nothing
  (`test_limit_a_stub_base_that_names_an_analysed_class_adds_nothing`).
- A stub annotation's attribute chain must start at a name that the stub
  imports: `Outer.Inner` for a class nested in the module's class names
  nothing
  (`test_limit_a_stub_attribute_chain_must_start_at_a_stub_import`). An
  alias that the stub defines names nothing.
- A stub with a `global` or `nonlocal` statement is not read at all: the
  module is analysed as if it had no stub, so its annotations are lost.
  The stub reader does not model these scope declarations, which stubs do
  not use (`test_limit_a_stub_with_a_scope_declaration_is_not_read`). A
  stub annotation never makes a dataclass field: the library reads the
  annotations of the source.

## Language features

### Classes and hierarchies

#### The class statement

A class statement makes the class as
`type.__new__` does. A plain function that the body binds to `__new__`
becomes a static method, and one bound to `__init_subclass__` or
`__class_getitem__` a class method (whatever the body binds there, as it
reaches the end of the body). The statement then calls, implicitly and from
its own scope:

- the `__set_name__` of each instance or class that the body binds to a
  name (looked up on its type), with the class and the name;
- the `__init_subclass__` of the nearest base that defines it (a lookup
  after the new class, so not the class's own), bound to the new class,
  with the keyword arguments of the statement but `metaclass`;
- each analysed metaclass of the class (see *Metaclasses*).

A class body defines the names that it binds and the names that its
`__slots__` lists: Python makes a descriptor on the class for each slot,
which stores the value on the instance. So a slot ends a lookup through
the class (it shadows an attribute of that name in a base class, a
property of a base `Protocol` say), a load of it through an instance
does not call `__getattr__`, and the value is the instance's own field.
The rule applies only to the final binding of `__slots__` in the body
(the last plain statement at its top level that binds it, see *Classes
that Python does not instantiate*), and only when that statement assigns
a str, or a tuple, a list or a dict (its keys) of str constants; a private
slot name is mangled as any private name. `__weakref__` there is a
descriptor of the class too, so its load calls no `__getattr__`;
`__dict__` there keeps what `object` gives (the instance's `__dict__`).
A `__slots__` that the body binds in a compound statement, or in any
other form, defines no names.

- Limit: a slot that is read before any store raises `AttributeError`,
  which calls `__getattr__`; the analysis calls none for a slot.
- Limit: stores are not restricted. Python refuses a store of a name that
  is no slot when no class of the MRO gives a `__dict__`; the analysis
  keeps the stored value (`test_limit_stores_are_not_restricted_by_slots`).

#### Alternative hierarchies

A base expression that may refer to several classes (`A if flag else B`, or a
name bound by `try`/`except` imports) gives alternative hierarchies, not
multiple inheritance. A class has one MRO per choice of one candidate per base
expression (and of one MRO per candidate), and a lookup is the union of the
first definition in each. `object` as a candidate means that the base may be
absent: `class C(A if flag else object)` has the MROs `[C, A]` and `[C]`. A
hierarchy without a C3 order, which Python would reject, still gets an order:
the class and then the MROs of its bases, left to right, each class at its first
position. A class is never its own base, nor is a base whose MRO already
contains the class; a repeated base counts once. `<builtin>.object` is never a
base: it is the implicit root of every class.

- A class gets its MROs (it is *ready*) only when each of its base
  expressions holds a ready candidate, an external, or no base (`object`,
  an expression that the analysis does not track, or one that a fixpoint
  step decided empty). Lookups on the class and on its instances wait
  until then, `__init__` included, so no lookup sees a hierarchy that a
  later base would change.
- After that, a new candidate only adds MROs, and a base expression decided
  empty keeps "no base" as an alternative, so earlier lookup results stay
  valid. MROs only grow (alternatives are added; an exhaustive order gains
  classes).
- Beyond 8 MROs (see *Bounds*), one order with every candidate stands for all
  of them (the *exhaustive order*). It finds what each hierarchy that it
  stands for would find: every definition; for `super()`, every class but the
  starting one and the receiver's; for `str()` and similar, every class unless
  the class itself defines the method that Python prefers (a lookup that
  starts after a class does not search the class, so what the class defines
  excludes nothing); and the `__getattr__` of every class whose body defines
  one, unless the class itself defines the name. When the order grows, only
  its new classes are walked. A class whose base is exhaustive is exhaustive.
- A class on a cycle of candidate bases (`class P(Right)`, `class
  Q(Left)`, `Left, Right = P, Q`) gets the exhaustive order, whether the
  cycle shows at a fixpoint (its classes wait for each other) or later (a
  candidate's MRO contains the class).
- The alternative MROs of a class are kept in a canonical order: compared
  class by class, classes come by module name and, in a module, in the
  order of their class statements (then externals by name).
  The `mro` of a class in the output (docs/format.md) lists each class at
  its first position in that sequence, and for an exhaustive class the other classes in that order,
  so the reported MRO depends neither on the order in which the candidates
  arrived nor on the order of the entry modules, which decides the order in
  which modules are built. Of two classes of one name (a class `b` in the
  package `a` and the module `a.b`), it reports the first in that order.

#### Lookup through a class

A load `C.attr` walks these places in order:

```
C.attr
 1. the MROs of C, each up to the first class body that defines attr:
      analysed class          Field(class, attr)
      outside base, stubs     its stub hierarchy, named through the base
      outside base, no stubs  External(base.attr): may define any name
 2. object                    only for a name that the code loads
 3. the metaclasses of C      bound to C
 4. __getattr__ of the metaclass, with the name
```

- Walk each MRO. Subscribe to `Field(C, attr)` for each class up to and
  including the first one whose body defines `attr`.
- An outside class of the MRO that the stubs describe gives what its stub
  hierarchy has, named through the base as the code names it
  (`collections.abc.MutableMapping.popitem`), and a name that it does not
  have continues the walk. The MRO holds an outside base as one class,
  without its own bases, so its whole stub hierarchy is searched where the
  base stands. Python's C3 order puts them there too unless another base
  shares one (`class E(KeyError, Mine)`: `KeyError`, `LookupError`,
  `Exception`, `BaseException`, then `Mine`). An outside class without
  stubs gives `External(base.attr)` and may define any name.
  - Limit: C3 puts a base that two bases share after both of them, and
    the analysis does not see that an outside base shares it. tablib's
    `HeadersNeeded(TablibException, AttributeError)`, with
    `TablibException(Exception)`, has the MRO `TablibException`,
    `AttributeError`, `Exception`, `BaseException`; the analysis searches
    `Exception` and `BaseException` before `AttributeError`, so
    `HeadersNeeded()` gives `<builtin>.Exception.__init__` where Python
    runs `AttributeError.__init__`.
- A base that the class statement replaces stands as the replacement
  (`MRO_ENTRIES`): `typing.NamedTuple` as `tuple`, through its
  `__mro_entries__`, and `typing.TypedDict` (also from
  `typing_extensions`) as `dict`, whose metaclass makes every `TypedDict`
  class a subclass of `dict` alone. So calling a `TypedDict` class runs
  `dict`'s construction (the edge `<builtin>.dict.__init__`, named through
  the nearest outside base), and its methods are `dict`'s
  (`<builtin>.dict.get`).
  - Limit: Python's call of a `TypedDict` class gives a plain `dict`; the
    analysis gives an instance of the class, whose elements are not
    tracked. The functional form `TypedDict("Name", {...})` makes no class.
- A name of `typing` that is an alias of an abstract class of
  `collections.abc` (`typing.Iterator`, `typing.AsyncIterator`,
  `typing.AbstractSet`, subscripted or not) is replaced too: it stands as
  that class, so its inherited methods
  are named through `collections.abc` (`collections.abc.Set.isdisjoint`
  for `class S(typing.AbstractSet)`). The stubs say which names these are
  the other way round: typeshed defines the classes in `typing`, and
  `collections.abc` re-exports them (`Stubs.abc_name`).
  - Limit: the other aliases of `typing` (`List`, `Deque`, `DefaultDict`,
    `ContextManager`, `AsyncContextManager`) are not replaced: the stubs
    declare the first ones as values of a stub-only class, which names no
    member, and the context managers as classes of `typing`, so their
    inherited methods are named through `typing`.
- A name that the code loads (`C.x`, `self.x`, `super().x`; not the special
  methods that the interpreter looks up) and that no class defines is then
  looked up on `object`, named through the first stubbed outside base, else
  `<builtin>.object`: `super().__init__()` reaches `abc.ABC.__init__`, and
  `self.__class__` is the class of the instance. The lookups that
  instantiation makes do not find `object`'s members (see *What is
  reported as an edge*).
- Through the class, the metaclass of a stubbed base gives its members too
  (`API.register` for `class API(abc.ABC)`), unless a class of the MRO,
  `object` included, defines the name.
- An instance found there whose class resolves `__get__` to an analysed
  method calls it with no value for the instance and the class, from the
  scope of the load, and the load gets the result; a property loaded
  through its class is itself (see *Descriptors*).
- The lookup is remembered and redone when the MROs change.
- Limit: the stub hierarchy of an outside base is searched where the base
  stands in the analysed MRO, so a later analysed base that shares an
  ancestor with it (`class C(UserDict, Mixin)` with `class
  Mixin(MutableMapping)`) is searched after that whole hierarchy, not
  before the shared ancestor as in Python's MRO.

On a chain of n classes, each class looks a name up through an MRO of up to
n classes: n² steps in all. The step that asks whether the receiver derives
from a class of the MRO, the C3 merge and the reported MRO look classes up
in a set or a dict; searching a list of the classes placed so far made each
of them cubic (`tests/test_scaling.py`).

#### Lookup through an instance

A load `obj.attr` gives the instance's own `Field(instance, attr)` and
what the lookup on its class gives.

```
obj.attr  =  Field(obj, attr)                the instance's own field
          ∪  steps 1 and 2 of C.attr         a function binds to obj,
             on the class of obj             a descriptor runs
          ∪  where no class of an MRO defines attr:
             the __getattr__ of the first class body of the MRO
             that defines one, called with the name
```

- A function found on the class becomes `BoundMethod(instance, f)`; a
  static method is the function that it wraps, unbound; a class method
  binds the class to the function that it wraps.
- A descriptor found on the class runs instead (see *Descriptors*). The
  instance's own field is never a descriptor.
- If no class of an MRO defines `attr`, the load also calls, with the
  attribute name, the `__getattr__` that the first class body of the MRO
  that defines one defines, bound as any class attribute; it may be any
  callable. Python's attribute lookup calls it after `__getattribute__`
  fails, so it is called from the scope of the access.
- Limit: CPython binds the class to any callable that a class method
  wraps, such as a bound method, a class or a callable instance; the
  analysis gives those unbound.
- Limit: a `__getattr__` stored on a class after its body (`C.__getattr__
  = fetch`, or through `setattr`) is not called, as it would be in Python.
- Limit: where a property's getter or a descriptor's `__get__` raises
  `AttributeError`, Python then calls the class's `__getattr__` with the
  name. The analysis calls `__getattr__` only where no class of the MRO
  defines the name, so that call, and what it calls, are missing
  (`test_limit_a_getter_that_raises_attribute_error_does_not_call_getattr`).
  On the 30 benchmark packages, 32 missed edges have this cause (bottle
  19, structlog 8, anytree 4, asyncstdlib 1). A rule that makes each load
  of a name bound to a property or a descriptor also call the class's
  `__getattr__` was measured: it adds 31 of them and 21 wrong edges
  (anytree 19, bottle 2). That is more than one wrong edge for every ten
  true ones, the bound for admitting a rule, so the rule is not built.

**Records on demand.** Whether a class has a name depends on the class
only; only what the class gives is bound to the instance. So a rule that
looks a name up on the class of an instance, and acts only on what the
lookup finds, is applied for that instance once the class may have the
name (`Hierarchy.later`): the class side of a load and of a store, the
attribute hook of an access, and the special method of an implicit call.
The first lookup of the name through an instance of the class is the
*witness*. Until it gets an object or an edge, each rule waits as one
entry in a list of the class and the name, with its instance; then the
rules of the list run, and make the lookups and constraints that they
would have made at once, which had nothing to act on before. On
matplotlib, four lookups through an instance in five never get an object
(an attribute that the instance itself has, `self.x`, or a special method
that no class defines), and their records are not made. Likewise, the node
of an attribute of an instance is made at its first write
(`Analysis.field`: a store, `setattr`, a write to `__dict__`); until then
a load of it is an entry in a list of the class and the name
(`read_field`), which the write connects. On matplotlib 88 % of those
nodes stayed empty. So the assignment graph for tests (`output_points_to`)
lists no attribute of an instance that nothing stores. The other lookups
through an instance are made at once: a deletion, a load through
`super()`, the special methods of a descriptor and the hook of its
accessor (made only once the class has answered), and the `__getitem__` of
the sequence protocol. Waiting would save little there: 1.0 % to 1.6 % of
the peak memory for the sequence protocol on pylint, matplotlib and
pydantic, 0.5 % for `super()` on matplotlib (measured); the others are
few. *Rules that wait* says why the results do not change.

#### `super()`

`Super(C, r)` looks up in the MRO of `r`'s class (or of `r`
if it is a class), after `C`, in every MRO that contains `C`, and binds to
`r`. `object` ends every MRO although no MRO holds it: in an MRO where no
class after `C` defines `attr`, the lookup finds the member of `object`
that the stubs have, as a load by name does (`super().__new__(cls)` is
`<builtin>.object.__new__`, named through the first outside base if there
is one). Lookups after a class and loads by name find the members of
`object` this way; the lookups that instantiation makes do not. The methods
of `object` call nothing that is given to them.
`super()` with a class receiver also looks in the MROs of the class's
metaclasses after the starting class.

`super(C, x)` with two arguments gives `Super(C, r)` only for a receiver
`r` of `x` that Python accepts: an instance of `C` or of a subclass, a
class whose metaclass is `C` or derives from it, or `C` or a subclass of
it (the instances of `C` and the family of `C`, which only grow as bases
and metaclasses arrive). For any other receiver Python raises
`TypeError`, so there is no object. A second argument that is neither an
instance nor a class of the analysed code (an outside value, a typed
value, a constant) gives no object, as before. `super()` without
arguments takes the class around it and its first parameter, and pairs
the class with every receiver that the parameter holds: a receiver that
is no instance of the class finds nothing after the class in its MROs. A `super()` load calls a property's
getter from the scope of the load, without the class's attribute hook.

#### Calling a class

As `type.__call__` does, the call calls `__new__` with
the class and the arguments, gives what it returns, and calls `__init__`
with the arguments, bound, on what it returns that is an instance of the
class or of a subclass (the instances of the class, joined with what
`__new__` returns: either may arrive first). A class has thousands of
calls and of instances, so the calls of a class share one set of its
instances; each call sees every instance, in the same rounds, unless it
comes after the instances of the class saturated: it then sees none.

- Where no analysed class of an MRO defines `__new__` before an outside
  base or the end, Python's own (or the base's) runs: it returns
  `Instance(class, site)`, made by the call.
- A `__new__` of the stubs whose result is `Self` (`object.__new__(cls)`,
  `super().__new__(cls, value)` in a subclass of `str`,
  `tuple.__new__(cls, items)`) gives an `Instance(cls, site)` of each
  analysed class that its first argument holds, and a typed instance of
  each outside one.
- A class with no `__init__` in its MRO gives no edge; an outside base
  gives the edge `caller → base.__init__`.

#### Classes that Python does not instantiate

Two refusals of Python make a call of a class give no instance and run no
`__init__`, and leave the class without an abstract instance (see *Entry
points*). The analysis applies them only where Python certainly refuses,
in every alternative hierarchy; in any other case the class is made.

- **Protocol's initializer.** A class that lists `Protocol` among its
  bases is refused when no class body of any MRO of it defines `__init__`
  (one that does replaces the initializer of `Protocol`) or uses its
  namespace (which may bind `__init__`).
- **`object.__new__` of an abstract class.** A class is refused when
  all of these hold:
  - it is *made by `ABCMeta`*: every metaclass of it, in every MRO of the
    metaclass, derives from `abc.ABCMeta` (`class C(abc.ABC)`,
    `metaclass=ABCMeta`, a base whose metaclass does, such as
    `collections.abc.Mapping` or a protocol of the stubs); an exhaustive
    metaclass is not certain;
  - in every MRO of it, the allocator is `object.__new__`: every outside
    class of the MRO is described by the stubs, derives from no builtin
    type but `object` (a builtin type such as `list` or `Exception`
    allocates in C, without the check), and has no `__new__` of its own;
  - in every MRO of it, some name is abstract, as `ABCMeta` decides it:
    the first class of the MRO that defines the name is made by `ABCMeta`,
    and its final binding of the name is a method decorated with
    `abstractmethod` (the name, or an attribute that ends with it, under
    any other decorator: `property`, `classmethod`, `staticmethod`), or it
    is an outside class whose stub member is abstract. The final binding
    is read from the body: the last plain statement that binds the name
    at the top level (an annotation without a value binds nothing); a
    compound statement, a `del` or an assignment expression that runs in
    the body (also in a decorator or a default of a nested function, under
    a compound statement or not; not in a nested function's body) that
    binds it leaves it with none until a later plain statement binds it
    again; a body that reads or writes
    its namespace (`locals()`, `vars()`, `exec`) has none at all (and
    `__slots__` none either); and a store on the class from outside its
    body replaces it. An outside base without stubs may
    define any name. In an exhaustive order, a name is abstract when every
    class of the order that defines it defines it so.

  So an abstract method of a mixin that `ABCMeta` does not make does not
  count, and neither does one that a later `f = 1` replaces.

The decision is made when the class is ready and redone when its MROs or
metaclasses grow, when the MROs of one of its metaclasses grow, and when a
store outside a body assigns a name on it or on a base. It only turns from
"no instance yet" to "instance": evidence of one concrete alternative
keeps the class concrete for good. Where an analysed `__new__` runs
instead of Python's, it is called as before; the instance that
`object.__new__(cls)` would give (`super().__new__(cls)`) is not made for
such a class either.

A class that is abstract only by convention (its methods `raise
NotImplementedError`), or whose `abstractmethod` decorators have no
`ABCMeta` to act on, is instantiated as any class. A class whose body
uses its namespace (`locals()`, `vars()`, `exec`) may bind any name there,
as an outside base without stubs: no name is abstract through it and it
may define `__init__`, so it is never refused, and a subclass is refused
only for a name that a class before it in the order makes abstract.

- Limit: Python decides at the class statement, so a store that replaces
  an abstract method after a subclass is made does not make that subclass
  concrete; the analysis, which has no order of statements in the heap,
  makes it concrete. Any store of the name counts, even `C.f = C.f`
  (`test_limit_a_store_on_a_class_counts_as_a_new_binding`).
- Limit: a class body that only reads its namespace (`snapshot =
  locals()`) binds nothing through it, so Python still refuses the class;
  the analysis does not tell a read from a write and makes its instance
  (`test_limit_a_body_that_only_reads_its_namespace_is_not_refused`).
- Limit: a name that an `ABCMeta` base obliges stays abstract where the
  method selected for it comes from a class that `ABCMeta` does not make
  and is abstract itself; the analysis takes it as concrete
  (`test_limit_an_abstract_name_selected_from_a_mixin_without_abcmeta`).
- Limit: an abstract property whose final binding is a concrete accessor
  (`@f.setter`) stays abstract; the analysis reads only the final `def`
  (`test_limit_an_abstract_property_with_a_concrete_setter`).
- Limit: a Protocol class that binds `__init__` to Protocol's own
  initializer is still refused; the analysis sees a body that defines
  `__init__` (`test_limit_a_protocol_that_binds_protocols_own_initializer`).
- Limit: an explicit `object.__new__(cls)` on a class whose builtin base
  allocates otherwise is refused; the gate is per class, not per
  allocator (`test_limit_a_builtin_base_with_an_explicit_object_new`).
- Limit: an outside metaclass's `__call__` (an `Enum` whose metaclass also
  derives from `ABCMeta`) may return an object without `__init__`; the
  analysis makes the instance as `type.__call__` does
  (`test_limit_an_enum_whose_metaclass_derives_from_abcmeta`).
- Limit: a value of `Self` that a stub method gives through a class
  (`C.create()` with an outside class method) is the abstract instance of
  that class, made for any class.

#### Subscripts of classes

A read `C[key]` on an analysed class calls the
metaclass's `__getitem__`, and only where the metaclass does not define
one (decided like a lookup; for an outside metaclass, by its stubs) the
class's `__class_getitem__`, a class method, with the key, and gives the
result. Where no analysed class defines `__class_getitem__`, the read
gives the class itself, as the generic alias that an outside base's
`__class_getitem__` makes (`typing.Generic`'s) calls and loads through the
class.

### Descriptors

A descriptor found on the class of an instance runs instead of being the
value, from the scope of the access (or from the class's own attribute
hook, see *Attribute hooks*), and the access gets the result:

- a property calls its getter with the instance on a load, its setter on
  a store and its deleter on a `del`;
- an instance whose class resolves `__get__`, `__set__` or `__delete__`
  to an analysed method calls it, with the instance and its class for
  `__get__`.

A *property* is the engine's own (`property(...)`, `@property`) or an
instance of an analysed class that may derive from the builtin `property`
(`Hierarchy.relation`, so a base that comes late counts; an analysed class
that is itself named `property` and derives from nothing is an ordinary
class). Such an instance keeps the accessors that a valid call of the
resolved builtin `property.__init__` passes: the inherited `__init__` of
`Sub(f)` and `@Sub`, `super().__init__(f)` in an `__init__` of its own, or
`property.__init__(self, f)`. The call is valid if it may bind `(self, /,
fget=None, fset=None, fdel=None, doc=None)`: no other keyword, `self` by
position, at most five positional arguments. `property.__init__` calls none
of its arguments. In each MRO of the instance's class, the first class that
resolves the descriptor method decides (an outside base by its stubs): an
analysed class's method runs; the builtin `property`'s runs as the engine's
own property does; any other outside class's method that the stubs describe
is called by its stub, with a typed result, and the descriptor is also the
value of the load; an outside base without stubs gives an external that is
not called, and the descriptor is the value. Where no class resolves
`__get__` (`object` has none), the instance is itself the value (decided
like a lookup: `Hierarchy.descriptor_itself`).

A load through the class runs `__get__` with no value for the instance and
the class: a property is then itself (property's own `__get__` is not
run), and a subclass's own `__get__` runs.

The methods of `property` are also called explicitly, on the engine's
property or on a property instance, through the instance, through
`super()` or unbound: `p.__get__(obj, owner)` calls the getter with `obj`
and gives its result, or gives `p` where `obj` is the literal `None` and an
owner other than the literal `None` may be passed; `p.__set__(obj, v)` and
`p.__delete__(obj)` call the setter and the deleter and give None, whatever
the accessor returns. `prop.setter(f)` and its siblings add `f` to `prop`
itself and give `prop`, for a subclass too. An explicit `__get__` of the
engine's `staticmethod` gives the function it wraps; of a `classmethod`,
its function bound to each class that the owner may hold (analysed or
outside), and, where the owner may be absent (an unpacking may omit it) or
is the literal `None`, to the class of the instance, or to the metaclasses
of a class (see `Hierarchy.bind`). A call of these methods is valid if it
passes no keyword and a number of positional arguments in the range of the
signature (`(instance, owner=None, /)`), or an unpacking that may fill it
(a call with `**` is not valid, even `**{}`: a restriction of the analysis);
`x.__get__(None)` and `x.__get__(None, None)` give nothing, as Python
raises. "The literal `None`" is what the source writes: the builder
records the positions at which a call expression passes `None` (before any
unpacking), and the calls that copy it keep them, with bound receivers
before them (`Analysis.literal_none`). An argument without a value is not
`None` (`False` and `1.5` have none either), and a node that holds nothing
decides nothing.

- Limit: Python's `prop.setter(f)` calls the class of `prop` to make a
  copy, so the original property keeps its accessors apart from the
  copy's, and a subclass's own `__init__` may run for the copy; the
  analysis merges them and calls nothing (the micro-benchmark cases
  `descriptors/property_subclass_copy` and `property_subclass_copy_init`).
- Limit: which of a data descriptor and the instance's `__dict__` wins is
  not decided: both count.
- Limit: a known `None` flows only as a literal argument: a subclass
  `__get__(self, obj, owner=None)` that forwards to `super().__get__(obj,
  owner)` calls the getter on a load through the class
  (`descriptors/property_get_forwards_none`).
- Limit: an explicit `__get__` with `**` gives nothing, even with an empty
  mapping (`descriptors/wrapper_get_double_star`).
- Limit: a second `property.__init__` adds accessors; Python replaces them.
  The reads and writes of `__doc__` that construction makes, and the name
  that a property keeps, are not modelled.
- Limit: a class that derives from `property` only through an outside
  class (`abc.abstractproperty`) is not a property: that class resolves the
  descriptor methods by its stubs. The descriptor methods of other outside
  bases (`functools.cached_property`) run only by their stubs
  (`descriptors/outside_descriptor_subclass`).
- Limit: in Python 3.12, `classmethod.__get__` calls `__get__` of a
  wrapped descriptor with the owner twice; the analysis binds as 3.13 to
  3.15 do, and gives a wrapped callable other than a function unbound. An
  explicit `__get__` of a function is not modelled.
- Limit: a descriptor method has one set of parameter and return nodes for
  all the descriptor objects that it serves (no calling context), so the
  accessors of all the instances of one property subclass, and the owners
  of all its accesses, mix in its body. Measured on the one development
  package where the rule fires (path, whose `ClassProperty.__get__` serves
  four instances): of the 41 false edges that the rule adds, 40 come from
  this mixing (36 to `functools.partial.__call__`, 4 from `Multi.__iter__`),
  and 74 of its 168 true edges (`TempDir.__new__` and `__init__`) are
  reached only through it, while Python makes those calls through a class
  that `type()` makes.

### Attribute hooks

A load, store or deletion through an instance calls the
`__getattribute__` (with the name; the load gets its result),
`__setattr__` (with the name and the value) or `__delattr__` that the
class attribute holds: defined in a class body, or stored as the attribute
(`C.__setattr__ = put`, `setattr(C, name, put)`). The access looks the
hook up as any attribute of the class, so a hook that the solve stores
after the access is found too. A hook is whatever the class attribute
holds, called as any value found on the class is called: a function or a
lambda (defined or assigned in the class body, or assigned later) binds
the instance, a static method does not, a class method binds the class,
and a bound method or a callable instance keeps its own receiver, as in
CPython. An outside hook (`__setattr__ = object.__setattr__`) is Python's
own, which is not called. The instance's fields are read and written in
every case, and an explicit `object.__setattr__(self, name, value)` is not
a store.

Python's own hooks call the descriptor accessors (a property's, and
`__get__`, `__set__` and `__delete__` of an instance's class) from the
scope of the access. Where the class of the instance defines the hook for
the access (`__getattribute__` for a load, `__setattr__` for a store,
`__delattr__` for a deletion), that hook is the caller of the accessor
(`C.__setattr__ -> C.value`), whatever its body does; a hook that is not a
function or a method (a callable instance) leaves the access as the
caller. Python's own hook also runs where, in some MRO, no class body
defines the hook before an outside class (decided like a lookup);
flow-insensitively, a hook assigned to such a class later runs as well, so
its accessor is called from both.

- Limit: a hook that replaces Python's (`self.__dict__[name] = value`)
  never calls the accessor, but gets the edge.
- Limit: Python calls a data descriptor's or a property's accessor for
  `object.__setattr__(obj, "x", value)`, `object.__getattribute__(obj,
  "x")` and `object.__delattr__(obj, "x")` with a literal name, also
  through `super()`; the analysis does not. It cannot tell from the stubs
  whose native slot a hook is (they give `type.__setattr__` and
  `super.__getattribute__` as object's), nor always that the name
  `object` is the builtin (a star import may supply it)
  (`test_limit_object_hooks_by_name_run_no_descriptor`, the
  micro-benchmark case `descriptors/object_setattr_runs_set`).
- Limit: `functools.partial` is outside code, so a partial hook is not
  called: neither the access nor making the partial calls its function
  (`test_limit_a_partial_hook_is_not_called`).

### Computed attribute names

`getattr`, `hasattr`, `setattr` and `delattr` with a str literal as the name are
a load (whose result `hasattr` discards), a store or a deletion. With any other
name, they are a load or a store of each str constant that the name holds at
each fixpoint (Part 3), whatever else it holds (a str of unknown value, an
outside value), as long as it holds at most four str constants (see *Bounds*);
once it holds more, the access is dynamic and gets no more names. This is a
limit on how far the analysis models dynamic features, not a tuning knob: a
name that may be any of many strings (`typing`'s `__getattr__` forwards every
missing name) would turn one access into a load of every name in the program.
What else the name holds gives no name: `name: str` with the constants `"a"`
and `"b"` loads `a` and `b`, and the attributes that the other values name are
missed. The `__name__` of an analysed function is a str constant, the name of
its `def` (`<lambda>` for a lambda), so `getattr(obj, f.__name__)` loads the
attribute of that name; a name that the code stores there is one too.

A str that the code builds from a constant part and another value is a
`Pattern` of its constant prefix and suffix (`patterns.py`): `"visit_" +
kind`, `"visit_%s" % kind`, `"visit_{}".format(kind)`, `f"visit_{kind}"`,
and the same with a constant suffix. It needs a non-empty constant part,
and it flows like a str constant. An f-string of more than one part and
`str.format` of a literal build a new str, so their pattern is the whole
result. The literal parts are read as Python reads them: the constants of
an f-string, the literal text that `string.Formatter().parse` (the parser
of `str.format`) gives, and for `%` the text between the fields that
`protocols.percent_spans` finds, the one reader of `%` formats in the
analysis (a key in balanced parentheses, flags, a width and a precision in
digits or `*`, one length modifier, a conversion; `%%` is a literal `%`,
and `%` is no other field's conversion). A `%` format with a field that
Python rejects (an unknown conversion, an incomplete field, a `*` with a
key, a width past its bound) makes no pattern, so the read stays
unrestricted. A pattern of `+` or `%` is the whole result only where `str`'s
own operation runs on plain strs: any other operand may be a str
subclass whose `__radd__`, `__add__` or `__rmod__` runs first and returns
any value, which replaces the prefix. The operands that leave the
pattern alone are these, and no others:

- a constant written in the source (a str, an int or bytes);
- an f-string of more than one part (a literal part, or two fields),
  which CPython joins into a new str;
- a value that is an exact pattern (one that the code builds, not an
  alias of a class member), or a container of exactly its builtin class
  (none derives from str);
- a typed value of `str` or `bytes`: a typed value is of its declared
  class (a stated limit of typed values), and `str`'s own operation keeps
  the prefix and suffix with either (`str` has an `__rmod__`, which
  formats and so keeps them; `bytes` has none that takes a str).

The other operand of the `+` chain, or the right operand of `%`, that
holds any other value (an instance of an analysed class, an external, an
enum member, which is the inexact alias of its value, a constant, a
pattern or a container, a function),
that is a single-field f-string (`f"{x}"` is what `format` returns,
which may be a str subclass), or that holds nothing at the fixpoint (step
4 in Part 3), adds the unnamed external to the result: a value of any
class, as the reflected method may return any object. A dict read by
such a key reads every element, as before the pattern key rule, and a
later `+` on the result widens again. The operator still calls the reflected method of an
instance of an analysed class, and its result joins. A `%` whose right
operand is an instance of an analysed class that does not derive from
str runs `str.__mod__`; the analysis does not decide the class here and
widens it too.

An arithmetic operator, a subscript, a slice or an iteration on a `str` or
`bytes` constant runs the method of its builtin class, so it gives what
the stub of that method gives, as for a typed value (`("ab" * n).upper()`
calls `<builtin>.str.upper`); an expression that makes a pattern has the
pattern alone as its value, so the operators of its own chain add nothing
on its constants. An f-string that makes no pattern is a str of unknown
value.

- Limit: whether an expression makes a pattern is read from its own
  syntax, so a constant prefix that a name holds makes none: `prefix +
  kind` is a str of unknown value, and a dict read by it reads every
  element
  (`test_limit_a_key_built_from_a_name_of_a_constant_reads_every_entry`).
`getattr` and `hasattr` with a pattern
load every attribute of the object whose name matches: on an instance, the
names that the class bodies of its MRO define or that stores assign on
those classes (an ordinary load), and the names that stores assign, as
fields of the instance only; on a module, its fields when the solve
starts. Both sides subscribe, so a base or a name that appears later is
found. A name that the object does not define is not loaded, so a pattern
does not call `__getattr__`.

`lower()`, `upper()` and `casefold()` of a pattern give a pattern: the
method applied to the constant prefix and suffix, which matches no ASCII
name that the method changes. Of an alias of a class member (an enum
member, whose class may define the method), they also give any value
(the unnamed external), beside the str or pattern that `str`'s method
gives, as an operand that is an alias does to `+` and `%`. Python looks up the converted
name, so `getattr(self, f"visit_{kind}".lower())` loads `visit_field` and
not `visit_Field`. The analysis converts ASCII only, as the case of other
characters depends on the Unicode database of the running Python: a
pattern with a constant part that is not ASCII gives a str of unknown
value, and a case pattern matches every name with a character that is not
ASCII and with its prefix and suffix (`visit_é`, which `lower()` gives for
`É`, and `visit_É` too). On ASCII,
`casefold()` is `lower()`, and converting a converted pattern gives what
converting the first pattern gives, so a pattern gives at most two others. The other
methods of `str` give a str of unknown value, also for a pattern
(`strip()` and `title()` depend on the other value in ways that a prefix
and a suffix cannot state) and for a str constant (`"Visit".lower()`).

- Limit: the other value does not narrow the names, even when it is a
  constant.
- Limit: a case pattern matches a name with a character that is not
  ASCII, though the method may never give it (`visit_É` for `lower()`).
- Limit: `setattr` and `delattr` with a pattern store and delete no known
  name, and a `getattr` on a class by pattern loads nothing.
- Limit: a typed `str` operand is taken to be of its declared class, as
  any typed value is: a subclass that overrides `__radd__` is not seen
  (`"pre_" + name` with `name: str` is a pattern only).
- Limit: the unnamed external that a widened result holds is one more
  object in the name of a `getattr` by pattern; where it saturates the
  name (at a cap of 1, or with two patterns at a cap of 2), the matching
  names are lost (see *Saturation and the rounds*). A widening for an
  alias adds one object to a node, so it can saturate the node one object
  sooner; at a cap of 1, `C.value.lower().upper()` loses `str.upper`, and
  the alias node of a callee's `**kw` that takes two values saturates (see
  *Bounds*: without the completion steps, a cap only takes edges away).
- Limit: `eval`, `exec`, names that may be more than four strings, and
  stores on an object through its namespace (`obj.__dict__[name] = value`)
  are not modelled (see *Namespaces read by reflection*).
- Limit: an operand that holds nothing at a fixpoint widens the result of
  `+` or `%` (step 4), and the widening stays when a later round gives the
  operand a str constant, since rules only add. A dict read by such a result
  reads every element, though Python, where no key matches the pattern,
  raises `KeyError`, and what the widened read gives flows on
  (`test_limit_an_operand_that_only_the_completion_fills_stays_unknown`).

### Namespaces read by reflection

`C.__dict__` and `vars(C)` of an analysed class give its namespace: a dict, one
per class, whose keys are the names that the class body binds (see *The class
statement*) and the names that stores assign on the class, and whose element
under each name gets, by an edge, what the class field of that name holds. The
field is the node that loads read, so a name that a store adds later, or a value
that reaches the field later, is in the dict in every order of the solve; where
the set of names saturates, the elements of the dict get the saturated value. It
holds what the body binds, not what a load gives: the plain function, and the
`staticmethod` or `classmethod` object, which a call runs as its function (a
static method; Python 3.10 made it callable) or not at all (a class method,
which Python refuses to call). The names of the bases are not in it. The
namespace is a dict as any other, so `items()`, `values()`, `keys()`, iteration
(the names, as str constants that `getattr` then loads, see *Computed attribute
names*), a subscript with a constant name and the unpacking in `for name, member
in vars(C).items()` work on it. It is not exact for class tests, since Python
gives a `mappingproxy` for a class. The rule applies where the `__dict__` that
Python finds on a metaclass of the class may be the default one, `type`'s
(`Hierarchy.default_member`). The walk follows each candidate MRO of the
metaclass, and the first class that defines `__dict__` decides: `type` means the
default; an analysed class whose body binds the name, or an outside class whose
stub class defines it before its stub MRO reaches `type`, means another
definition; an outside class that only inherits it from `object` lets the walk
go on, since `object` comes last in Python's MRO; an outside class without stubs
may define it. By the stubs, `type` supplies `__dict__` (and Python's `type` its
own `__dir__`, which the stubs leave to `object`), and `object` supplies
`__dir__` and `__dict__`. So `M(type, Hidden)` keeps the defaults and `M(Hidden,
type)` does not. As for a lookup, the rule applies if some candidate MRO reaches
the default first: the answer only turns from no to yes as MROs are added, as
the solve needs, and a hierarchy that Python does not build may add members
(`test_any_candidate_mro_that_reaches_the_default_applies_the_rule`). A
metaclass that defines its own `__dict__` gives that attribute instead, and the
rule adds nothing; a class body's own `__dict__` is not in the way, since the
descriptor of the metaclass wins. Of the common outside metaclasses, `type`,
`abc.ABCMeta`, `typing._ProtocolMeta` (protocols) and `enum.EnumMeta` define no
`__dict__` of their own in the stubs; a `NamedTuple` class is made by `type`.

`inspect.getmembers(x)` of a class or an instance gives an exact list of
exact (name, value) pairs: the names of the class (of its class, for an
instance) and of the analysed candidate bases of each class on the way up,
which a base that a base expression gives later joins, each with what an
ordinary load of that name through `x` gives (a bound method through an
instance, a class method bound to the class, the result of a property's
getter through an instance); for an instance, also the names stored on it,
with what its fields hold, without the lookup on the class (which would
call `__getattr__`). The names are those that the default `__dir__`
lists, `object`'s for an instance and `type`'s for a class: the rule adds
them where the `__dir__` that Python finds on the class (on a metaclass,
for a class) may be that default one, by the same criterion as for
`__dict__`. `abc.ABCMeta` and `typing._ProtocolMeta` keep the default;
`enum.EnumMeta` and `enum.Enum` define their own `__dir__` in the stubs,
so `getmembers` of an enum class or member gives the stubs' result. The list
and its pair are made when the first such class or instance arrives, so
`getmembers` of a module gives the stubs' result alone. These rules add to
what the stubs give for `vars` and `getmembers`.

Each member is loaded once per object that `getmembers` reaches, and is one
field of one namespace dict, whatever the loops that read it. Each receiver
is read once per site that reaches it, so many classes read at sites of
their own and at one shared site cost the sum of the two
(`tests/test_scaling.py`).

- Limit: neither the predicate of `getmembers` nor a test on the name
  (`if name.startswith("_func_")`) is evaluated: every member is called
  (`test_limit_a_filter_on_the_name_is_not_evaluated`).
- Limit: a `__dir__` other than the default one, analysed or outside, is
  not evaluated: `getmembers` of an object whose class (metaclass, for a
  class) defines it gives the stubs' result, so edges may be lost and none
  are added (`test_limit_an_analysed_dir_leaves_getmembers_to_the_stubs`,
  `test_an_outside_dir_leaves_getmembers_to_the_stubs`).
- Limit: the pairs of `getmembers` are one pair whose name is every name
  and whose value is every value, as for any list of pairs: a dict made of
  them (`dict(inspect.getmembers(C))["x"]`) gives every member
  (`test_limit_the_pairs_of_getmembers_do_not_keep_names_apart`).
- Limit: the names that Python adds to a namespace (`__module__`,
  `__qualname__`, `__doc__`, `__dict__`) and the members of outside bases
  (those of `object`) are not there
  (`test_limit_names_that_python_adds_and_outside_members_are_absent`). The
  namespace of a class names its methods as a dict's
  (`<builtin>.dict.items`), where Python names them as the mappingproxy's
  (`types.MappingProxyType.items`;
  `test_limit_the_methods_of_a_class_namespace_are_named_as_a_dicts`).
- Limit: a write through the namespace of a class (`d = C.__dict__; d["x"]
  = f`) goes to the dict, which later reads of that dict see, and not to
  the class, whose loads do not; Python's mappingproxy refuses it
  (`test_limit_a_write_through_the_class_namespace_stays_in_the_dict`).
- Limit: an element of the namespace is the value that the body binds, as
  a load takes it, also where the class machinery replaces it (see the
  limit in *Class bodies*).
- Limit: the namespace of an instance (`obj.__dict__`, `vars(obj)`) is what
  the stubs say, a dict of unknown values
  (`test_limit_the_dict_of_an_instance_is_what_the_stubs_say`). Code writes
  it (`self.__dict__.update(kw)`, `self.__dict__[name] = value`), which the
  analysis does not store on the object, and reads it with computed keys
  (`d["cached_" + name]`), which read every element when this was measured
  (a pattern key now reads the keys it matches, see *Containers*): on `_pytest` and
  `hypothesis`, the fields of every instance that reaches a generic reader
  (a report serialiser, a pretty printer, a cache) met there and gave 355
  edges, none of them traced. `getmembers` of an instance reads it by
  loads of the names stored on it (a store through a property or a slot
  counts as one).
- Limit: `dir(x)` gives what its stub says, a list of str of unknown value,
  so `getattr(x, name)` for each name loads nothing. A module's `__dict__`,
  `getmembers` of a module and `vars()` without an argument (see *Which
  names*) give what the stubs say
  (`test_limit_dir_modules_and_vars_without_an_argument`).

### Metaclasses

A class is an instance of its metaclass: the most derived of the classes
that its `metaclass=` expression holds (`type` without one, or for a value
that is no class or that the analysis does not know) and the metaclasses of
its bases (the stubs' metaclass of an outside base, `typing._ProtocolMeta`
for one that is or derives from a protocol, whose `Protocol` base the stub
data drops; `type` for one without stubs). An expression may hold several candidates, so a candidate is a
metaclass if, for each other expression, it derives from one of that
expression's candidates: the most derived of some choice. That only grows
as candidates arrive, so it does not depend on their order. The class
waits for its `metaclass=` expression as for its bases, and the decision
is redone when its MROs or its bases' metaclasses grow
(`Hierarchy._decide_metaclasses`).

- A class is among the instances of each analysed metaclass of it, and a
  metaclass has no abstract instance (see *Entry points*).
- A function found on a class through a receiver that does not derive
  from that class (a class whose metaclass it is) binds to the receiver.
- A load through a class that no class of its MROs, nor `object`, answers
  finds the attribute in its metaclasses, bound to the class: an analysed
  metaclass's by a lookup, an outside one's (`type`) as the stubs give it
  (`C.mro()` is `<builtin>.type.mro`; `C.__name__` a str). A class with a
  stubbed outside base finds its base's metaclass members through the
  base.
- A load through a class that neither its MROs nor its metaclasses answer
  calls the `__getattr__` of the metaclass, bound to the class, with the
  attribute name, from the scope of the load, as for an instance.
- The special methods of a class are those of its metaclasses, bound to
  the class (see *Special methods and protocols*). What the class of an
  instance decides (is the instance searched by `in`, is it its own
  awaited value, is it iterated through `__getitem__`), its metaclasses
  decide for a class, and an outside metaclass decides as an outside base
  does. An outside metaclass's method (`type`'s) gives what the stubs say;
  the call is implicit, so it gives no edge.
- A class statement is a call of each analysed metaclass of its class,
  implicit, from the scope of the statement, with the name, a tuple of the
  bases, a dict of the namespace (the names that reach the end of the body,
  with their values) and the keyword arguments: first the metaclass's
  `__prepare__` (with the name, the bases and the keywords, found on the
  metaclass as a class attribute), then `__new__` and `__init__` as for any
  call of a class. Where Python's own `type.__new__` runs, it makes the
  class of the statement; an explicit `type.__new__(mcs, ...)`
  (`super().__new__` in a metaclass's `__new__`) gives every class whose
  metaclass `mcs` is, since the analysis does not tell the statements apart
  there. Each class that such a `__new__` may return gets `__init__` with
  the arguments of its own statement, and `__init__` is the same method
  for each, so the work grows with the number of classes, not with its
  square. A class whose metaclass is `type` makes no such call.

  The metaclass's `__init__` still runs on the class of its own statement
  only, not on every class that `type.__new__` gives there, so the
  statements of one metaclass cost their number (`tests/test_scaling.py`).

Limits:

- A data descriptor of the metaclass does not take precedence over the
  class's own attribute, and a property of the metaclass is not called.
- `type(name, bases, namespace)` makes no class: it gives a typed `type`.
  Where the call passes exactly three positional arguments, without
  keywords or unpacking, and `bases` is a tuple display of one element,
  it calls each analysed metaclass of the class in it (with one base, the
  base's metaclass is the winner) with the three arguments: its `__new__`
  and `__init__`, as a call of a class, implicitly from the caller. With
  several bases the winning metaclass depends on the new class: no call.
  A call with a keyword, with unpacked arguments (`type(*args)`) or with
  another number of arguments makes no calls, although Python passes the
  keywords on.
- Limit: the `__init_subclass__` that Python calls on the new class is not
  called: the new class, whose namespace may override what the hook finds
  through `cls`, is not modelled, and the written base does not stand for
  it (`test_limit_the_hook_of_the_new_class_is_not_called`). Its
  namespace's functions are not methods of anything either, so loads and
  calls through the made class give no edges (a new class at solve time
  would be needed: a class object per call site, with the namespace's keys
  as its fields and the bases' MROs, which the hierarchy would treat as a
  class statement).
- A metaclass's `__call__` is not modelled: where it creates the instance
  through `type.__call__`, it would give an instance of every class that
  reaches it.

### Special methods and protocols

The receiver of a special method is any object; its type decides: the
class for an instance, the metaclass for a class (see *Metaclasses*).
Builtin and outside values have the special methods that the stubs give;
calling one gives no edge.

**Operators.** A binary operator calls `__op__` of the left operand and
`__rop__` of the right one; `x op= y` calls `__iop__`, and `__op__` where no
analysed class of the MRO defines `__iop__`. A comparison calls the method
of each side (`__lt__`, the reflected `__gt__`) and gives what it returns,
which need not be a bool; `!=` also calls `__eq__` where no class defines
`__ne__` (`object.__ne__` does). A unary operator calls `__neg__`,
`__pos__` or `__invert__`.

**Comparisons of containers.** Two containers that the analysis tracks
compare their elements within one family, the pairs of kinds for which
CPython compares elements:

| Family | Compares with | `==`, `!=` | `<`, `<=`, `>`, `>=` |
|---|---|---|---|
| list | a list | elements | elements, then the order of the first pair that differs |
| tuple | a tuple | elements | as a list |
| deque | a deque | elements | as a list |
| set, frozenset | a set or frozenset | elements | elements (subset tests) |
| dict (any of `collections`) | a dict | keys and values | nothing |

A list never compares its elements with a tuple or a deque:
`deque([a]) == [b]` calls nothing. Comparing elements calls each element's
`__eq__`, and for an ordering of lists, tuples or deques also the method
of the comparison (`__lt__`, or the reflected `__gt__` where no class
defines `__lt__`), as any pair may be the first that differs. The items
of `sorted`, `list.sort`, `min` and `max` are compared with each other in
the same way (see *Methods that builtins call on their arguments*). A
comparison gathers, per family, the elements of the containers of each
side in one node, and compares them once both sides have a container of
the family: its work grows with the containers, not with their pairs. An
object stands for every object of its site, so a container's elements
also meet each other.

- Limit: containers among the elements compare nothing, though Python
  compares the elements of those of one family (`[(a,)] == [(b,)]` calls
  `__eq__`); `[[a]] == [(b,)]` rightly calls nothing. Comparing them per
  level, by family, cost hypothesis 13% more time at one level down and
  78% at two.
- Limit: a strict subset or superset test (`<`, `>`) of two sets
  compares their elements also where their sizes exclude it: Python
  returns False before it compares a key when the sizes are equal
  (`{a} < {b}`), and the analysis does not know the size of a set.
- Limit: a `Counter` orders by counts (`Counter(a=1) < Counter(a=2)`),
  which looks its keys up in the other counter; the analysis orders no
  dicts and calls nothing there. The other dicts raise TypeError.
- Limit: an instance of an analysed subclass of `list`, `tuple`, `set`
  or `dict` compares no elements; dict views (`d.keys() == s`) neither.

**Subscripts.** A subscript calls `__getitem__`, `__setitem__` or
`__delitem__`. A read of an instance also calls `__missing__` where no
analysed class defines `__getitem__`, as `dict.__getitem__` does for a
subclass (whether the class is a dict is not checked); for a read of a
class, see *Subscripts of classes*.

**Hashing.** A set or a dict (also a dict of `collections`) calls
`__hash__` of each key that enters it or that it looks up. Keys enter by a
set or dict display or comprehension, a subscript store, `set()`,
`frozenset()`, `dict()` and `dict.update` with (key, value) pairs,
`dict.fromkeys`, a `Counter`, `set.add` and `set.update`; they are looked
up by a subscript read and `del`, `get`, `pop`, `setdefault`,
`OrderedDict.move_to_end`, `in`, `set.remove`, `set.discard`, and by the
set methods that take iterables (`union`, `intersection`, `difference`,
`symmetric_difference` and their `_update` forms, `issubset`, `issuperset`,
`isdisjoint`, `builtin_models.py`, `HASHED_ARGUMENTS`), which hash their
elements. The analysis does not hash again the keys that come from some
containers, whose stored hashes CPython reuses in the common cases: a set,
a frozenset or a dict of exactly that class, for a set, a set method and
`dict.fromkeys` (`set(s)`, `{*s}`, `s.union(t)`); any dict but an
`OrderedDict` (which iterates by its own `__iter__`), for a dict that
takes the items of a mapping and for a `Counter` (`dict(d)`, `{**d}`,
`d.update(e)`). Each store and
lookup but `in` (which compares as it does for any container, see *`in`*)
compares the key, whatever object it is (an instance, a constant, a
function), with each stored key that is another object (the stored key's
`__eq__`, where the stored key is an instance or class, as Python does
where the hashes are equal; the same object is found by identity). The
stored keys of a set method that takes iterables include their elements,
which Python puts in a new set.

- Limit: keys whose hash is reused are stored keys only: Python also
  compares them, as they enter, with the keys of a set or dict that is
  not empty (`s.union(t)`, `d.update(e)`, `dict.fromkeys(s)`).
- Limit: whether CPython reuses a hash depends on the operation and the
  destination too, not only on the class of the source, which is all the
  analysis looks at. It hashes the keys of a dict again in
  `intersection`, `intersection_update`, `issubset`, `issuperset` and
  `isdisjoint` of a set (`set().intersection(d)`), in `Counter.update` of
  a counter that is not empty, and in `OrderedDict(d)` and
  `OrderedDict.update(d)`; the analysis does not hash them there.
- Limit: an instance of an analysed subclass of `set` or `dict` is
  iterated and its keys hashed, where CPython reuses the hashes of a
  subclass of `set` (`set(sub)`) and of a dict subclass that keeps
  `dict`'s iteration (`dict(sub)`).
- Limit: the operators of sets (`|`, `&`, `-`, `^` and their in-place
  forms) and the set operations of dict views compare or hash keys; the
  analysis does not.
- Limit: an object stands for every object that its creation site makes,
  so two equal keys made by one call site in two runs of it are one object,
  found by identity: their `__eq__` gives no edge.
- Limit: where the stored key's `__eq__` returns `NotImplemented` (a
  stored `1` and a searched `Key()`), Python calls the searched key's
  `__eq__`, reflected; the analysis does not.

**Truth.** Python tests the truth of a condition (`if`, `while`,
`assert`, a conditional expression, a comprehension's `if`, a case guard),
of the operand of `not`, of each operand of `and` and `or` but the last, of
each result of a comparison chain but the last (`a < b < c` tests `a < b`),
and of what `__contains__` and the `==` of a value or literal pattern
return: the analysis calls `__bool__`, else `__len__`. Which branches the
builder walks depends on the syntax only (idea 2), not on what these
methods return.

- Limit: a builtin that compares (a dict lookup, the search of `in`,
  `sorted`, `list.index`) tests the truth of what `__eq__` or `__lt__`
  returns; the analysis does not test it.

**Conversions.** `str()` and `print()` call `__str__`, and `__repr__` where
Python falls back to it; `repr()` calls `__repr__`; `format()` and f-strings
call `__format__` with the format spec (the empty string by default), and
`__str__` and `__repr__` where Python falls back to them; an f-string field
with `!s`, `!r` or `!a` converts as `str()` or `repr()` does. The fallback
to `__repr__` stops at a class of the MRO, analysed or outside, that defines
`__str__` before `object`: an outside class counts where its stub declares
`__str__` (`BaseException`), and `str`, `bytes` and `bytearray` count
although their stubs omit the `__str__` that CPython gives them
(`STR_DEFINED_BEYOND_STUBS`), so a subclass of `str` that defines only
`__repr__` never has it called by `str()` or `format()`. What library code
then calls back stays a limit: `OSError.__str__` calls `repr()` of its
filename, so formatting an `OSError` about a `path.Path` runs
`Path.__repr__`, which the analysis does not see. The
`__iter__` and `__contains__` of a builtin class never call what Python
falls back to without them: a subclass of `list` that defines
`__getitem__` iterates with `list.__iter__` and tests `in` with
`list.__contains__` (`FINAL_BUILTIN_METHODS`). Conversions are not so:
`int.__format__` calls `__str__` for an empty spec. A literal
format does the same for its fields: `"{0.name!r:>8}".format(x)` loads
`name` from its argument and converts it, and a field that indexes is
skipped. A field's digits name a position whatever their leading zeros;
one past 19 digits names none (Python rejects an index past
`sys.maxsize`). In `fmt % items` and `fmt %= items`, for each str constant
that `fmt` holds (a literal, or a name or attribute that holds one: `msg =
"%r failed"; msg % (x,)`), each `%s` converts its item with `str()`, and
`%r` and `%a` with `repr()`; the items are the elements of a tuple, the
values of a dict for `%(key)s`, or else the one value, whatever it is (a
list, a set, a dict: `"%s" % [x]` converts the list). A `*` width or
precision, and every conversion but `%%`, takes an item of its own, in
order. So the one value goes to what the format takes first: only a
conversion that comes first converts it, also where a later field then
lacks its argument (`"%s%s" % [x]` converts the list and fails after),
and nothing does where a width or another conversion takes it (`"%*s" %
[x]`, `"%d%s" % [x]`). The fields are read as Python reads them: a key
in parentheses may hold balanced parentheses (`%((a))s` names `(a)`), a
precision may be empty (`%.s`, precision zero), and one length modifier
(`h`, `l`, `L`) is skipped. Python formats the fields in order and stops
at the first one it rejects, so nothing from there on converts: a key
whose parentheses do not close, a `*` in a field with a key, a conversion
that it does not support (`%y`, a `%` after flags or a width), a `%` that
ends the format, a width in digits past `PY_SSIZE_T_MAX` or a precision
past `INT_MAX` (`%.2147483648s`); with a tuple, a field with a key; with
any other value, a field without a key after one with a key, and a number
conversion (`%d`) that takes a dict. A bytes format is read in the same way, with bytes
keys: `%r` and `%a` convert with `repr()`, and `%s` and `%b` take an item
without converting it with `str()`. A format that the analysis does not
know (a parameter that nothing passes, a str from outside) converts
nothing. `print(file=f)` has no rule
of its own: the stub types `file` as `SupportsWrite[str]`, and that
protocol decides what `print` calls on `f` (see *Methods that builtins
call on their arguments*).

Each of these conversions of a list, tuple, set, frozenset or dict that the
analysis tracks calls `repr()` of its elements (the keys and the values of
a dict), from the scope of the conversion, and so on for the containers
among them: these types have no `__str__` or `__format__` of their own, so
`str(xs)`, `f"{xs}"` and `"%s" % (xs,)` give `repr(xs)`, which converts the
elements with `repr()`. Each such container has one node with what its
`repr()` reaches: its elements, and, through one constraint on its element
nodes, the nodes of the containers among them (a container that holds
itself adds an edge to its own node). A conversion gathers the nodes of
the containers that its value holds into one node and calls `__repr__` on
it, so the walk of a container's elements is shared by every conversion
that reaches it.

- Limit: `PY_SSIZE_T_MAX` depends on the platform; the analysis takes
  that of a 64-bit Python (`2**63 - 1`), so that it gives one result
  everywhere. A 32-bit Python also rejects the widths from `2**31` on,
  where the analysis converts the item.
- Limit: `%s` and `%b` of a bytes format call `__bytes__` of their
  item (or read its buffer); the analysis calls nothing there, as for
  `bytes(x)`.
- Limit: `format(xs, spec)` with a spec that is not empty raises
  `TypeError` before any element is converted; the analysis converts them.
- Limit: the other builtin collections (`collections.deque`, dict views)
  and the instances of subclasses of these types convert nothing.

**`in`.** `in` calls the `__contains__` of a container whose type defines
it, which answers alone. Any other container (a builtin one, an iterator,
a generator, an instance or class iterated through `__iter__` or
`__getitem__`, a value from outside or one that the analysis does not
track) is searched: the value is compared with the elements, so the
value's `__eq__` may run, and so may that of each element that the
analysis tracks. The value is compared as soon as a searched object
reaches the container operand, whatever the analysis knows of its
elements, as an empty points-to set is not an empty container (`None` and
numbers have no object). Containers that arrive later still give their
elements to the comparison. An instance or class is searched
once its type may leave `__contains__` to Python or to an outside class
(whose `__contains__` may compare too): in some MRO no class body defines
it before an outside class or the end; an outside metaclass (`type`,
`EnumType`) may. Like a lookup, that is decided when the class is ready
and again when its MROs grow. A str or bytes constant is not searched.

- Limit: `Needle() in []` reports `Needle.__eq__`, though no comparison
  runs.
- Limit: an `in` whose container never holds a searched object (a
  parameter that nothing passes) compares nothing, though Python compares
  the value.

**`with`.** `with` calls `__enter__` (the target gets its result) and
`__exit__`; an outside manager gives an outside result. `__exit__` gets
exception arguments that the analysis does not track.

- Limit: where the body raises, Python tests the truth of what `__exit__`
  returns; the analysis does not follow that path and does not test it.

**Exceptions.** `raise C` instantiates `C`. The name in `except E as e`
holds every instance of `E` and of its subclasses that the analysis
creates, and an outside instance for an outside class. A bare `raise`
raises nothing that the analysis tracks.

**Builtins with hand rules.** `len()` calls `__len__`.

**Length hints.** Some builtins ask the length of what they iterate before
they iterate it (CPython's `PyObject_LengthHint`): `__len__`, else
`__length_hint__` (`LENGTH_HINT`, which selects by definition; the fallback
to `__length_hint__` after a `__len__` that raises `TypeError` is not
modelled). They are, by probes of CPython 3.12.12, 3.13.12, 3.14.9 and
3.15.2:

| Asks the length of `x` | 3.12, 3.13 | 3.14, 3.15 |
|---|---|---|
| `list(x)`, `l.extend(x)`, `l += x` on a list, `sorted(x)`, `[*x]`, `(*x,)`, `f(a, *x)` and a call with more than one argument besides `*x`, `bytes(x)` (after `__bytes__`, `__index__` and a buffer), `bytearray.extend(x)` (after a buffer) | yes | yes |
| `tuple(x)`, a call `f(*x)` whose only argument is `*x` | yes | no |
| `str.join(x)`, `bytes.join(x)`, `bytearray.join(x)`, an assignment to a starred target (`a, *b = x`): the iterator that `iter(x)` gives, so `x` where `x.__iter__` returns `x` | yes | yes |
| `set`, `frozenset`, `{*x}`, `bytearray(x)`, `collections.deque`, `dict.fromkeys`, `min`, `max`, `sum`, `zip`, `enumerate`, `map`, an assignment without a starred target (`a, b = x`), `for` | no | no |

Implicit calls that a hand rule models take the union of the supported
CPython versions, as the stub data does (see *Stub data*): `tuple(x)` and
`f(*x)` ask on every version. The unpacking of an argument is the
interpreter's work, so `f(*x)` asks whatever `f` is, also an outside name
without stubs or a name that has no value. The builtins of the stubs that
ask are `LENGTH_HINTS`.

The length is asked of an argument, or of the iterators that `iter()` of
it gives: `join` takes, for an instance or a class, what the `__iter__`
that its protocol calls returns (a class's metaclass's), or the sequence
protocol's iterator where the type has `__getitem__` only; an engine
container goes on as it is, so an iterator that the program already made
(`"".join(iter(x))`) is its own. A starred target takes the iterators of
its unpacking. What that node may hold, and what Python asks of it (the
table of `BuiltinRules.add_length_hint`):

- an instance of an analysed class: `__len__`, else `__length_hint__`, by
  its class;
- an analysed class: the same, by its metaclass;
- the sequence protocol's iterator: the `__len__` of each sequence that it
  iterates, instance or class, and nothing else; a class whose outside
  base defines `__iter__` (a subclass of `Sequence`, iterated by its
  mixin's generator) is asked nothing there;
- a `reversed` object: the `__len__` of its sequence again, instance or
  class, where the sequence has `__getitem__`, unless a class of its MRO
  defines `__reversed__` (also the mixin of `Sequence`, a generator);
- any other engine container (lists, tuples, sets, dicts, views, their
  iterators, `enumerate`, `zip`, `map`, `filter`, `callable_iterator`), a
  generator, a coroutine, a constant, an outside value, a function, the
  saturated value: nothing that the program defines.

A buffer is a class that defines `__buffer__` or derives from an outside
class whose stubs define it (`bytes`, `bytearray`, `memoryview`,
`array.array`): `bytes()` and `bytearray.extend` read it without asking
its length. Only the length hints test the outside classes for a method,
for `__buffer__`, `__iter__` and `__reversed__` (`DEFINES_MARKERS`); the
conversions of `int()` and `float()`, whose overloads list `Buffer` first,
still call `__int__` and `__float__` of a subclass of `bytearray`, as
CPython does.

`enumerate`, `zip`,
`reversed`, `map` and `filter` are hand rules over the engine's
containers: iterators whose elements are pairs of an index and an element,
tuples of the elements of each argument, the elements (or what
`__reversed__` of an instance, or of a class's metaclass, returns, else
`__getitem__` after `__len__`, both only where the class has both: with one
of them `reversed` raises `TypeError` and calls neither), what the function
returns when called with the elements (a class is instantiated), and the
elements again; `map`
calls the function from the scope of the call, with an element of each
iterable at its position, and `filter` with an element of its iterable,
and tests the truth of what it returns. An unpacked argument passes a number of iterables
that is not known: the elements of the iterables that bind to `*iterables`
(and to `iterable` if the unpacked argument gives it) go to any position
after the explicit ones, so `map(f, [g], *rest)` still passes `g` first.

Limits:

- `filter(None, xs)` tests the truth of the elements; the analysis does
  not test it, as `None` has no object.
- `__del__` is not called: it runs when the last reference to an object
  goes, and the analysis does not track references.
- `__instancecheck__` and `__subclasscheck__` are not called: without
  CPython's exact-type shortcut, `isinstance(Duck(), Duck)` would call
  them.
- `join` asks the length of the iterator of `x`, but the analysis does not
  iterate that iterator further (`__iter__` on it again, `__next__`): its
  protocol gives `x.__iter__` only.
- `xs += ys` asks the length of `ys` only where `xs` is a list of the
  engine, not an instance of an analysed subclass of `list`.

### Containers and iteration

#### Containers

Displays, comprehensions, the builtins `list`, `tuple`,
`set`, `frozenset` and `dict`, slices, concatenations and starred targets
create containers. An unpacking comprehension (PEP 798: `[*it for ...]`,
`{*it for ...}`, `{**mapping for ...}`) holds the elements, or the items,
of each one. A read with a constant key gets that field and
`unknown`; a read with any other key gets every element; a write with a
constant key goes to its field, any other to `unknown`. A read of a dict
with a pattern key (see *Computed attribute names*) gets the fields whose
key is a str that the pattern matches, and `unknown`: a str with the
constant prefix p and suffix s equals only the strs that start with p and
end with s, and no str equals bytes or an int. Only lists, tuples
and dicts have fields: a container that keeps no positions (a set, a
`deque`) reads every element for any key and writes to `unknown`. `True`
is not the constant `1`. Negative indexes are known for displays, whose length is
known. A slice with constant bounds and no step copies the fields that it
covers. Unpacking reads the positions of lists and tuples, and iterates
other values; a starred target gets a new list. `xs += ys` extends the
list in place; `+` keeps the positions of the left operand. The mutators
and accessors in the table (`append`, `extend`, `insert`, `add`, `update`,
`setdefault`, `pop`, `get`, `items`, `values`, `keys`, `copy`) are
modelled. A key that holds nothing when the solve reaches a fixpoint comes
from values that the analysis does not see (`i + 1`, an argument from
outside): the completion (Part 3) then reads every element or writes to
`unknown`.

- Limit: `insert`, `pop(0)` and `sort` do not shift positions.

**Pattern keys.** In one sentence: a pattern key restricts a dict read
only when the key is certainly a plain str built from exact parts (see
*Computed attribute names*), and then the read gets the fields whose
constant key the pattern matches, the `unknown` field, and every element
stored under a key that is an alias of a class member. A pattern that is
itself an alias (an enum member whose value is a pattern) is not such a
key: as the lookup key, it reads every element.

The pattern read is the subscript load `d[k]` and the
lookups `get`, `pop` and `setdefault`, which read as it does, of a dict
or a dict of `collections` (`OrderedDict`, `defaultdict`, `Counter`). It
uses the matching of `getattr` (`Pattern.matches`), and a field that a
store adds later is matched when it appears. A key that holds a pattern
and other objects reads what each of them reads: a constant its field, a
str of unknown value or any other object every element, so the read is
never less than what Python can read. A stored key that is not a
constant (an instance with `__eq__` and `__hash__`, a str of a subclass,
a str of unknown value) is in `unknown`, which the pattern read reads. A
key that is an alias of a class member (an enum member, an inexact
constant) is stored under its value and in the dict's `aliased` node too,
which a pattern read reads whatever the value: by its class's own
equality, hashing or construction the member may equal any str (a
`StrEnum` or `IntEnum` member with its own `__eq__`, a member that
`__new__` builds from its value). The node travels wherever the fields
and `unknown` of the dict go to another dict: a copy (`dict(d)`, `{**d}`,
`update(d)`, `copy()`, through `copy_fields`), the `**kwargs` of a callee
or of a builtin model (`f(**d)`, `dict(**d)`, `update(**d)`, through
the spread of the arguments), and a dict that a class body binds (its
alias shares the node). A named parameter that takes a field of `**d`
takes it by the recorded value, as before the rule. A constant read is not part of this rule: it
reads its field and `unknown`, as before. Any other constant field is
selected only by a key equal to it, as for a constant key. `k in d` and `del d[k]` read no element, and a `defaultdict` read
calls its factory whatever the key. A store under a pattern goes to
`unknown`, as any other key: the pattern may equal a key that no field
has. A list, tuple or `deque` read by a pattern reads every element, and
an instance with `__getitem__` gets the call, as for any other key.

`target.update(source)` copies the fields of `source` to `target` key by
key, also the keys that `source` gets later. Every site that copies one dict
into another copies the same fields to the same place, so the copy is made
once per pair of dicts, not once per site, which would cost the sites times
the keys.

- Limit: `"ext.{}".format(name)` is a pattern and also the str of unknown
  value that the stub of `str.format` returns, so the read gets every
  element.
- Limit: a store under a pattern is read also by a constant key that the
  pattern does not match.

**The containers of `collections`.** `OrderedDict`, `defaultdict` and
`Counter` are dicts, and `deque` is a list: a call of one of these classes
makes a container as a call of `dict` or `list` does, and so does a value
that the stubs or an annotation type as one of them (`builtin_models.py`,
`CONTAINER_CLASSES`). It keeps its elements as its builtin type does
(the keys of a dict, which iteration gives and lookups hash), but a
`deque` keeps no positions, since `appendleft` and `popleft` move them:
`q[0] = f` stores an element and `q[1]` reads every element. Its methods are named by its own class, also where `dict` or `list`
defines them (`collections.OrderedDict.items`, the convention of
`evaluation/micro-benchmark/README.md`), and the modelled methods of its
builtin type
carry its elements, with a few of its own: `deque.appendleft`,
`extendleft` and `popleft`, and `Counter.update`. An operator on it gives
what the method of its class in the stubs returns, as for a typed value
(`Counter(xs) + Counter(ys)` is a new `Counter`, without the elements of
either). A `Counter` counts the
elements of the iterable it gets: they are its keys, and its values are
counts, which are not tracked. A `defaultdict` keeps its factory (a copy
keeps it too), and a read `d[k]` calls it, as `__missing__` does for a key
that is missing, which it may always be: an implicit call without
arguments, from the scope of the read, whose result is a value of the dict
under any key (a call back of `collections`, as
`evaluation/micro-benchmark/README.md`, "Callbacks", counts it). A store,
`get`, `in`
and `del` call nothing. One call per read joins the factories of every
`defaultdict` that the read reaches and gives its result to each of them,
so the calls, and what the factories make (a copy of the dict, another
`defaultdict`), are as many as the reads (see *Termination*).

- Limit: `ChainMap` is not a container. It reads through the mappings it
  holds, so a copy of their elements would miss a later store to one of
  them; it stays a typed value.
- Limit: an instance of a subclass of one of these classes in the analysed
  code is an instance, not a container, as for a subclass of `dict`.
- Limit: a factory that needs arguments is called, though Python raises
  before it starts; a `Counter` built from a mapping that is an instance
  of an analysed class gives nothing (Python reads it through `items()`,
  the analysis iterates it).
- Limit: `+` on an instance of a subclass of `list` copies the list's
  storage in Python and calls no `__iter__`; the analysis iterates the
  operand, so the subclass's `__iter__` gets an edge
  (`test_limit_list_concatenation_iterates_a_list_subclass`).

#### Iteration

Iterating a container gives its elements (the keys of a dict); a
generator gives what its function yields; an instance or class calls
`__iter__` and then the `__next__` of what it returns (`__aiter__` and
`__anext__` for `async for`), with edges from the iterating scope; an
external gives itself. `iter()` of a list, tuple, set, frozenset or dict
(or a collection of `collections`) that the analysed code makes gives its
iterator, one per container, of kind `list_iterator` (and so on), whose
elements are the container's; `iter()` of any other container, an
iterator or a generator gives the object itself. If no analysed class and no builtin class (`list`)
of its type defines `__iter__` but one defines `__getitem__`, `iter()`
gives an iterator whose `next()` calls `__getitem__` with an index that is
not known (the sequence protocol), from the scope that iterates. Every
iteration, `iter()`, `next()` and an explicit `__next__()` of these
iterators and of generators go through one rule. `iter(callable,
sentinel)` gives an iterator whose `next()` calls the callable, implicitly,
from the scope that iterates. `next()`, `iter()`, `send()` and `yield from`
are modelled; the value of a `yield` expression is what is sent; `yield
from` gives the inner generator's return value. The edge to a generator
function comes from the scope that calls it.

`async for` has no sequence protocol: an instance whose type defines
`__getitem__` but no `__aiter__` gives nothing to `async for`, and no
`__getitem__` is called.

### `match`

A `match` statement runs each case where the cases before it did not match
(see *Paths, joins and loops*), and a capture binds what its position in
the pattern holds (`matching.py`, from the language reference):

- a capture of the whole pattern (`case x:`, `case p as x`) binds the
  subject;
- a sequence pattern `[p0, *rest, pn]` reads the subject as `len()` and
  subscripts read it (an instance's `__len__` and `__getitem__`); each
  sub-pattern matches the element at its position, counted from the end
  after a star, and the star binds a list of the others;
- a mapping pattern `{k: p, **rest}` reads `len()` and the value of each
  key as a subscript; `rest` binds a new dict with the subject's items;
- a class pattern `Cls(p0, name=p1)` is an `isinstance` test, which calls
  nothing; a keyword sub-pattern matches the attribute that it names, a
  positional one the attribute that `Cls.__match_args__` names at its
  position (loaded as `getattr` with a computed name loads it, so
  properties and inherited `__match_args__` count), and a single positional
  sub-pattern of a builtin such as `str(x)` the subject itself;
- a value or literal pattern compares the subject with the value by `==`
  as a comparison does (the subject's `__eq__` and the value's reflected
  one, whatever the analysis tracks of either side) and tests the truth of
  the result; `None`, `True` and `False` compare with `is`, which calls
  nothing;
- an or-pattern binds what the alternative that matches binds: its
  alternatives are paths that join;
- a guard is an expression evaluated where the pattern has bound its
  captures.

Literal values decide what may match (see *Value choice*): a case runs only
if its pattern may match a literal subject (a literal value pattern
compares with `==`, `None`, `True` and `False` with `is`; a sequence or
mapping pattern never matches a literal, since `match` takes no str or
bytes for a sequence; a class pattern may) and its guard may hold, and the
cases after one that always matches do not run. A case whose pattern
matches but whose guard fails leaves what the pattern bound to the cases
after it.
Otherwise every case may run, whatever the length or the keys of the
containers that the subject holds.

- Limit: Python hashes the keys of a mapping pattern and reads each with
  the subject's `get`; the analysis reads each as a subscript, so where a
  class overrides `get`, it calls `__getitem__` instead, and it hashes the
  keys only for a dict.

### `async`

`await x` gives what `x.__await__()` finishes with: a coroutine what its
function returns, a generator likewise, an instance or class what the
generators that its `__await__` returns (called implicitly from the scope of
the `await`) return, and itself where its type defines no `__await__` (an
outside call such as `asyncio.wait_for` gives its awaited value at the
call), and an outside value (an external, a typed value, a container that
outside code returns) itself. `async with` awaits what `__aenter__` and
`__aexit__` return, whether or not it uses the result, and `async for`
what `__anext__` returns, in the same way. A coroutine that is not awaited
gives nothing; calling its function still gives the call edge.

**Async generators.** Calling an `async def` whose body has `yield` gives
an async generator, and so does a generator expression that has an `async
for` or an `await` outside its first iterable (the first iterable runs in
the enclosing scope), also inside a list, set or dict comprehension in it,
which the generator expression awaits; not inside a nested generator
expression or lambda, which is a scope of its own (`scopes.py` marks these
expressions). `async for` gives what it yields, as `for` does for a
generator. Its other methods are those of `types.AsyncGeneratorType` in the
stubs, named by that path: `__aiter__` returns the generator itself (the
stub's `Self`), and `__anext__`, `asend`, `athrow` and `aclose` give what
their stubs declare.

- Limit: awaiting what `__anext__()`, `asend()` or `athrow()` returns gives
  no yielded value (the stubs type it with a type variable of the class,
  which no argument binds), and `asend(v)` does not pass `v` to the `yield`
  expressions; the builtins `aiter()` and `anext()` likewise.
- Limit: a plain `for` over an async generator, and `async for` over a
  generator, give the yielded values, where Python raises `TypeError`.

### Imports

**Module discovery.** An import resolves against the package root (see
*Pipeline and modules*). Resolution reads only the file system: it never
imports or executes code, and never reads or changes `sys.path` or
`sys.modules`. A directory's names are read from its listing, once per
analysis, so a name matches case-sensitively also on a case-insensitive
file system, and a directory named like a file is not that file.
`from a import b` imports the module `a.b` if it exists, else `b` is an
attribute of `a`; the `*` of a star import is never a module, and a plain
module has no submodules. The packages on the path of an import are
imported even when the module is missing, since Python runs them before
the import fails. A relative import that goes beyond the top-level
package imports nothing: the package root is not a package. In an
absolute import, the modules that are built-in or frozen in every
supported Python (`BUILTIN_OR_FROZEN_MODULES` of `imports.py`: the
intersection of `sys.builtin_module_names` and
`_imp._frozen_module_names()` over 3.12 to 3.15, static and shared builds,
computed once) come before any file, as in Python, also for submodules
(`importlib` is not frozen, `importlib.util` is): such a module is outside
code, and no absolute import reaches an analysed module of that name. The
set is a constant, so the result does not depend on the Python that runs
the analysis.

Python imports a builtin or frozen module before any file on the path, so an
analysed module of the same name (`os.py`) is not what an absolute import
gives. The analysis applies this only to the modules that are builtin or
frozen in every supported Python and build (`os` is frozen in all of them);
a module that is builtin only in some builds (`math`) is the analysed file,
so the result is the same on every Python that runs the analysis.

**Literal imports.** `importlib.import_module("a.b")` and `__import__("a.b")`
with a str literal are imports too, where the called name is, in the scope
that reads it, the module's import of that function or the builtin (a
parameter of that name is not it). The call gives the module only if its
callee is that function, and `__import__` gives the top-level package
unless `fromlist` is a non-empty literal. The literal must be dotted
identifiers, as `str.isidentifier` says, whose Unicode tables follow the
running Python, so a name with characters that only a newer Unicode
version classes as letters is followed only there.

- Limit: a name that is no literal imports nothing.
- Limit: a relative name (`import_module(".alpha", "pkg")`) is not followed
  (`test_limit_a_relative_literal_import_is_not_followed`).

**Lazy imports** (PEP 810). A lazy import imports its module when code
first reads the name that it binds, so discovery follows it only if some
code of the importing module reads that name (in any scope, whether or not
the code runs; a module that uses `globals()` reads every name). The lazy
imports are `lazy import` and `lazy from ... import`, and the top-level
imports whose module `__lazy_modules__` lists before them, as long as every
top-level statement that mentions it before them assigns it one literal
list or tuple of strings (the last one counts). A lazy import that
discovery does not follow still binds its name.

- Limit: a name that only other modules read (`m.name`, `from m import
  name`, a star import of `m`) does not count, so its module is not analysed
  unless it is an entry module or another import reaches it.

**Star imports and `__all__`.** Linking copies the exported names of
star-imported modules, transitively. The exports are `__all__` if every
top-level statement that mentions it assigns it one literal list or tuple
of strings (the last one counts), else the public names that the module
binds at run time (see *Code that cannot run*), which include the public
submodules that imports attach to a package (an import anywhere in the
program counts, not only one that runs before the star import). A star
import also imports the submodules that `__all__` lists; discovery builds
them. A star import of an outside module binds what its stub exports: the
stub's `__all__` (`all` in the data), else the public names that the stub
has; each name has the value that `from m import name` gives (see *Typed
outside values*), and a module without `__all__` passes them on to its
own star importers. An outside module without a stub exports nothing.

- Limit: an outside module's exports are those of its stub, and a stub
  lists only the names that a type checker sees: the public names that the
  module imports without re-exporting them (`os` in a module that does
  `import os`) are exported at run time and not bound by the analysis.

**Loads on a module.** A load gives the module-level variable, or a
submodule. A load of a name that the module does not bind at run time (by
a statement that runs, a star import or a submodule) also calls the
module's `__getattr__` with the name, from the scope of the load, and gets
its result (PEP 562); `from m import name` loads `name` from `m` this way.
The decision waits for the objects of the `__getattr__` field, which
arrive in the solve, when every module is built and linked. A name that
other code assigns on the module counts as not bound, so its loads keep
both values.

**A package attribute and a submodule of one name.** `from p import n`
reads the attribute `n` of the package `p`. Python imports the submodule
`p.n` only where `p` has no attribute `n` when the import runs. In a class
body, the from-list keeps the written `__n`, which decides the import, and
the name that the import reads is `_C__n`. These three facts together
are enough for the package to supply `n` (they are not necessary: inside
`p/__init__.py`, `x = 1` before `from . import x` already supplies it):

1. `p/__init__.py` binds `n` on every path on which it completes;
2. the import runs after `p/__init__.py` has completed;
3. nothing deletes the attribute between the two (`del p.n`,
   `delattr(p, "n")`, a `del n` in the package).

The first and the third are facts about the code. The second is not. An
import that runs while `p/__init__.py` runs finds only the names bound so
far, and code reaches it through any call that the package's code makes,
also a call of a function that another module registered (a call back).
That is what keeps a general proof out of this pipeline: it needs the
call graph, and discovery comes before it. A narrow syntactic case would
fire on almost no real package. So the analysis never decides that a
package supplies a name:

- Discovery follows the submodule whenever its file exists, and the
  analysis makes it the attribute `n` of `p` (see *Pipeline and modules*).
  The value of `from p import n` is the load of `n` from `p`.
- A type-only import whose dotted name ends in a submodule `p.n` reads
  the attribute `n` of `p`: what the package binds to `n`, and the
  submodule where an import of the program makes it that attribute. A
  file `p/n.py` does not hide what the package binds. The module operand
  of `from p.n import T` is the module `p.n` itself, as in CPython.
- Limit: a submodule that a package attribute shadows is analysed, and its
  calls count, where Python never imports it
  (`test_limit_a_submodule_that_a_package_attribute_shadows_is_analysed`,
  the micro-benchmark case `imports/package_attribute_shadows_submodule`).
- Limit: in a module's own stub, an attribute chain after an imported
  name (`from p import X`, then `X.T`; or `p.X.T`) is joined into one
  dotted name (`p.X.T`) and resolved on the file system. Where the
  package binds `X` to something else and a file `p/X.py` exists, Python
  names the package's `X.T`; the analysis names the file's
  (`test_limit_a_stub_attribute_chain_reads_a_submodule_file`). In the
  source, such an annotation reads the attributes and names the
  package's.
- Limit: `import p.n as c` binds the module `p.n`. CPython reads the
  attribute `n` of `p` after the import (and so on for each part of a
  longer name), which is another value where the package rebinds `n`
  after it imported the submodule
  (`test_limit_import_as_binds_the_submodule_not_the_package_attribute`).
  Reading the parts at the import would be wrong for a lazy import, whose
  parts are read where its name is first read.

**Names that imports bind.** An import under `if TYPE_CHECKING:` binds
nothing at run time; the reading of annotations still resolves it (see
*Code that cannot run* and *Annotations*). The module `builtins` is the
namespace of the builtins (see *Nodes*).

## Open problems

**The analysis does not finish on the standard library.** On packages that
use the standard library as outside code, the analysis takes about a
second. When the standard library itself is analysed (the 312-module
import closure of `json`, or the whole standard library), the solver is no
longer the bottleneck (it shares sets and collapses cycles), but the
fixpoint is very large: after 253 s on the `json` closure it held 5.9M call
edges and 759k externals in 7 GB and was still growing. Context
insensitivity merges what generic code passes through: code that calls a
stored callable with stored arguments (`contextlib`'s `func(*args,
**kwds)`, `functools.partial`, `typing._tp_cache`, `pickle` reducers,
`super().__init__(*args, **kw)` chains) passes every argument to every
callable. A generic value then holds tens of thousands of externals; loads
on it make two-step names from every root and attribute in the program
(`<builtin>.filter.match.fullmatch`), single functions call 25,000 distinct
callees, and 98% of the constraint applications act on externals. Making
the result smaller is a question of precision (context for closures and
partials, external names through generic values).

**A coroutine names any attribute.** The result of calling a coroutine
function names every attribute as `types.CoroutineType.<name>`, also a name
that the coroutine type does not have, where Python raises
`AttributeError`. On the 30 benchmark packages this is 10 wrong edges to
outside code. A fix that prunes the names outside the stubs was built and
measured; it leaves a receiver empty where the wrong name was, and the
receiver completion then adds an edge that the engine did not have. The
maintainer left it out (2026-11-15); a test pins the limit.

**Hubs reach class hierarchies.** `unittest`'s skip decorators rebind their
argument, so every name that they decorate holds every item that they
decorate in the program: on the whole standard library, test mixins such
as `test_cext.BaseTests` hold 2,352 objects, of which about 345 are classes
and externals that become base candidates. Each class built on such a
mixin then has one exhaustive order of about 470 classes, recomputed for it
and its subclasses at every new candidate, which costs about the fourth
power of the size of such a cluster. Deciding hierarchies in batches would
remove that cost.

**`type(x)` gives a typed `type`, not the class of `x`.** As `x.__class__`
does, it would give the class of each object that `x` holds, so
`type(self)()` would make an instance of the receiver's class and run its
`__init__` (on the macro-benchmark's batch 2, 4 more true edges). It is out
because, without calling context, a hub of values that calls what it holds
(hypothesis's drawn values, through `self.target(*args, **kwargs)`) gets
the classes of its instances, calls them, makes more instances, and grows
until memory ends.

**A load of an attribute that `__init__` stores still calls
`__getattr__`.** A rule that knew which attributes every run of `__init__`
surely stores before anything reads them would remove that edge (2 to 3
wrong edges on each known set). It is out because certainty needs to know
what runs before the store (a descriptor installed on the class later, a
call on the right-hand side that reads the instance through a global),
which needs escape and effect information that the analysis does not
have; three reviews each found a new way in which a syntactic version
removed a real call.

**Overloads are not selected by argument types.** A monotone selection
would make an overload applicable when an object that its parameter type
accepts, or a literal that it names, reaches the argument, and every
overload when the argument holds nothing at a fixpoint. The mode of an
opened file is selected that way, by a table of Python's rule rather than
by the stubs, whose data keeps no `Literal` values (see *Typed outside
values*).

# Part 3: Order independence and termination

## Order independence

The solver takes its processing order from `Solver.order`, first in, first
out. Other orders (last in, first out; reversed; seeded random) exist only
as a test hook: `tests/test_order_independence.py` checks under five orders
that the results do not depend on the order. It also checks that they do
not depend on the order of the entry modules, which decides the order in
which modules are built, and so the order in which classes are made: no
rule orders classes by when they were made across modules.

Objects are numbered in the order in which they first reach a node.
Constraints see new objects in that order, and readers of a points-to set
(`Solver.objects`, which includes what the constraints being applied have
added) get it in that order. The output is sorted. So results do not
depend on object identity or hashing.

Hash consing and cycle collapsing keep the fixpoint, but the solver
delivers objects in another order than a naive solver. The results are
the same as with any other solver because the rules do not depend on the
order in which objects arrive: a rule subscribes to a points-to set and
acts on each object. A rule that reads a points-to set while the solve
runs is where such a dependence would come from. The rules that read sets
are the fixpoint steps below and the literal check of `getattr`, which
reads only constant nodes. Class lookups wait for complete hierarchies
(see *Alternative hierarchies*). Decisions that depend on a hierarchy are
not fixpoint steps: whether Python's own special method may run
(`__contains__`, an attribute hook, `__new__`, `__get__`, `__await__`,
`__class_getitem__`, a metaclass's `__getitem__`) is decided like a lookup
(`Hierarchy.python_method`, and `Hierarchy.descriptor_itself` for whether a
descriptor is itself the value of a load), when the class is ready and
again when its MROs grow, and so is whether a class may derive from
another, or may not, for a class test and for a property
(`Hierarchy.relation`).

### Saturation and the rounds

Saturation is not monotone: what the constraints of a node did with its
objects stays when the node saturates, so a rule that applied constraints
to objects as they arrived would keep the effects of whichever objects
came first, which depends on the order (a measured program with a cap of
two gave 16 different call graphs under 5 orders and 24 orders of its
entry modules). The rounds (see *The solver*) separate what is monotone
from what is not:

- **Propagation is monotone.** With the value of a node being its set if
  it has at most `cap` objects and the saturated value
  otherwise, the saturated value above every set, the union of what the
  edges bring is monotone in that lattice, so propagation has one least
  fixpoint, which any order of the worklist reaches (marking a node as soon
  as it passes the cap is a faster way to the same fixpoint; merging a
  cycle unites sets that are equal at that fixpoint).
- **Applying constraints reads only that fixpoint.** A round applies each
  constraint to the objects of its node at the fixpoint that it has not
  seen (to the saturated value, once, if the node saturated), and what the
  constraints add (edges, objects, constraints, call edges) waits for the
  next propagation. Which classes are unknown is decided from that
  fixpoint before the constraints apply, so the constraints of one round
  see one answer, for the objects they apply to and those they hold. Additions commute, and a constraint attached in the
  round sees the node's set at that fixpoint, so the state after the round
  does not depend on the order in which the constraints were applied.

So the state after each round is a function of the state before it, and by
induction a function of the program and the cap. The fixpoint steps below
run when a round adds nothing, as before. `tests/test_order_independence.py`
runs programs that saturate under five orders and every order of their
entry modules, and `tests/unit/test_solver_properties.py` compares the
solver with a cap of two to a reference that implements the rounds by
brute force.

### Rules that wait

A rule that waits for the class of an instance (see *Records on demand*)
must do what it would have done at once, in the same round, since what
the constraints of a saturated node saw depends on the rounds (above).
Three invariants make it so. `tests/test_waiting_lookups.py` checks them:
on programs that saturate, it compares the document, and the round in
which each object first reaches each node, with the same analysis whose
rules run at once.

1. **A waiting rule acts only through its lookup.** Until its lookup gets
   an object, nothing that the rule makes has an effect: its constraints
   act only on the objects of their nodes, and its other records (a lookup
   node, an implicit call of the instance) are read by key only. So no
   rule and no output lists a table of such records, which would miss
   those that wait. A record that the instances share is made at once, by
   the access: the call of an attribute hook is one per site, and it joins
   its result to each load that asks for it (two loads of `"{0.x.x}"`
   share one), whether or not a class has the hook.
2. **The lookups of one name on one class through its instances get their
   first object in the same round.** The walk of the MROs subscribes each
   of them to the same class attributes, and the rules wake inside
   `Solver.add_object` and `add_edge`, before the object or the edge
   arrives, so a wake costs no round. A lookup that fills through a node
   of its own per instance gets its object a round after the walk; the
   `__getattr__` fallback is the one such case, and it wakes the waiting
   rules at the walk.
3. **No waiting rule sees an opaque object.** A class that becomes unknown
   first wakes the rules that wait for it, while its instances are not
   opaque yet; then all its lookups get the saturated value, as those of
   the rules run at once would. The audit of the saturation tests checks
   each receiver as its rule wakes.

### The fixpoint steps

The solver reaches a fixpoint; then the steps below run in this order,
each only if the step before it added nothing, and the solve continues,
until no step adds anything (`Analysis.solve`):

1. **Decide the class hierarchies that still wait.** A base expression that
   holds nothing holds no base; classes that still wait after that are on
   (or below) a cycle of candidate bases and get the exhaustive order.
2. **Complete**, in one round: entry points (receivers that hold nothing,
   and the defaults of functions that no analysed code calls; see
   *Declared types*), keys that hold nothing (see *Containers*),
   `getattr` and `setattr` with names that are not literals (see *Computed
   attribute names*), and class tests whose classes hold nothing (see
   *Class tests*).
3. **Make the arguments of opened files that hold nothing unknown**, only
   when step 2 added nothing (see *Typed outside values*): a default or a
   computed name that step 2 adds must reach a mode before the mode counts
   as holding nothing (`def run(self, mode="rb"): open(p, mode)` reached
   through `getattr(obj, name)()`). Every argument is read before any is
   marked, so the marks depend on that fixpoint only. The step does not
   wait for what one open that it marks gives another: such an argument
   is marked with the rest and gives every fitting class (a limit; see
   *Typed outside values*).
4. **Make the results of patterns whose operand holds nothing any
   value too** (the unnamed external), only when step 3 added nothing (see *Computed
   attribute names*), for the same reason: an entry point's receiver
   reaches `__getattr__`, whose name a pattern formats, only after step 2
   (`self.environ["ext.%s" % name]`). Decided earlier, every such read
   would read every element.

The hierarchies come first because the completion reads which receivers
hold nothing, and lookups that wait for a hierarchy fill receivers. Each
step reads the nodes as the fixpoint left them (in step 2, also what its
parts before added in the same round), which does not depend on the order
in which the solver reached the fixpoint: every rule only adds facts, and
lookups wait for complete hierarchies. The steps run in a fixed order, so
the result does not depend on the order of the solve.

**A decision at a fixpoint may add, never close.** A step decides on what
the nodes hold at that fixpoint, and a later solve can bring more. What it
added stays, and what arrives later is still handled:

- Hierarchies: "no base" is one more alternative. A candidate that arrives
  later adds MROs beside it, and a forced exhaustive order stands for every
  hierarchy and grows with later candidates; lookups are redone as MROs
  grow.
- Entry points: a receiver that gets instances later keeps those of its
  class; a function that a later call reaches keeps its defaults. Keys: a
  key that gets values later keeps the read of every element; a pattern
  whose operand gets values later keeps the unnamed external. Class tests:
  a class expression that gets classes later keeps every value. Opened
  files: a mode that gets constants later keeps every class. Each is
  decided once per method, function, subscript and argument, which is enough,
  because what it tests (an empty node, a function not called) can only
  become false.
- `getattr` names: each round adds the names that a name node holds then.
  This is the one exception: once a name may be more than four strings or
  anything else, the access gets no more names, by design (see *Computed
  attribute names*), so names that arrive after that are not loaded.

## Termination

The solve ends because the analysis can make only finitely many objects
and calls, and each constraint applies once to each object that reaches its
node. The rule that guarantees it: **every object and every call is keyed
by finite things**: source positions, names from the source, a bounded
amount of static context (a method name, the role of an implicit call, a
tuple of at most three receivers), and other objects and calls. No key of
an object or a call holds a node, and no key nests an origin made from
another origin without a bound.

| Kind | Key |
|---|---|
| Module, class, function | its definition |
| Call expression | the expression (one `Call`, made by the builder) |
| Implicit call of a construct (`__iter__` of a for loop, `__eq__` of `in`, a descriptor accessor, an attribute hook) | scope, site (start and end), role; its origin is that key |
| Implicit call of a special method (`call_dunder`) | instance or class, method name, the root call (the call expression, construct call or call back that a chain of implicit calls copies) and `unless`, plus at most three receivers (as below); a copy has the arguments of its root |
| Call that a bound method makes | the call that it extends (never itself such a call) and at most three receivers |
| Call back from outside code | the origin of the outside calls; every call with that origin passes its arguments to it once |
| `Instance` | class and origin; one more per class, the abstract instance |
| `Container` | kind, origin and the rule that makes it: a display or comprehension; a call origin and the model (`tuple(x)` and the pair of `d.items()` at one call are two containers), and for the tuples of `zip` their length (a call that adds receivers keeps the origin and passes more iterables); a slice, operator or unpacking of the source; `(scope, site, role)` for an iterator that `iter()` makes; the container, for the iterator of an exact collection and for its inexact alias; the function and parameter (or class and field) whose annotation names it; the class, for its namespace; for the result of a stubbed call, the call origin (or the stub attribute, never the receiver that it is loaded through, which may itself be such a container: `x = x.__dict__` in a loop), the position in the type and the type, which the stub data bounds; an instance of a generic stub class likewise |
| Lazy object of a standard-library operation | its container (as above); an activation of its advancing: the object, the scope and the site |
| `Wrapper` | kind and origin |
| `BoundMethod` | function (or outside method) and receiver |
| `Generator` | function, and whether it is the inexact alias |
| `Coroutine` | function, and whether it is the inexact alias |
| `Super` | class and receiver |
| `BuiltinMethod` | receiver and method |
| `Fallback` | bound `__getattr__` |
| `ReturnsArgument` | library callable name |
| `Closure` | closure name (one of three) and the stub's result type |
| `External` | name, at most two steps past a root, or three for a member that a lookup finds in a stubbed outside base within the bound (a stub class has finitely many members), and whether it is the class taken from an inexact value; one unnamed external past that |
| `Typed` | stub class |
| `Saturated` | one per analysis |
| `TypeForm` | operator and site (made by the builder) |
| `Pattern` | prefix, suffix and case: from literals in the source, or their ASCII lower or upper case (at most three per pattern of the source) |
| `Const` | value: literals, attribute names, defaults of modelled builtins; and whether it is the inexact alias |

**Origins are finite.** An implicit call's origin is the static key of its
construct, or the origin of the call that it extends: calling a class that
a special method holds (`It.__iter__ = It`) makes one instance per class
and construct, however often the result flows back. A request for an
implicit call with other argument or result nodes is joined to its nodes
by edges, so result nodes never multiply calls. An implicit special-method
call copies the arguments of the call that it extends, and that call may
itself be such a copy (an instance whose `__call__` is another instance):
copies are keyed by the call at the root of that chain, which is finite,
not by the call that each extends, which would make a new key for each
link.

**No key loses an argument.** The analysis makes calls only from the
source, at sites (where a request with other nodes is joined by edges), as
call backs, as copies, and with receivers added. A copy has the argument
nodes of the call that it copies, and receivers are part of the key of a
call with receivers, so every call that shares a root, receivers and the
method passes the same arguments. Every cache follows that rule: its key
decides the inputs that it was asked with (a container's length, the node
that a construct iterates, what an unpacked argument passes, the node that
`in` compares, the number of arguments of a site call), and a hit asserts
that it was asked with the same, so a kind of call that broke the rule
fails the tests instead of losing values.

**Receivers are bounded.** A bound method has one receiver: only a
function is bound, so binding never nests. The cap of three receivers
bounds the receivers that a call passes before its arguments, which grow
by one each time such a call reaches a callable that is not a function and
passes them on with its own (`C.__new__ = D` and `D.__new__ = C`: `C()`
calls `D(C)`, which calls `C(D, C)`): past three, the outermost are
dropped (see *Bounds*). A call through a static method goes through the
worklist, so a wrapper that wraps itself does not recurse. Unpacking that
would move a field of `*args` to a higher index puts it in `unknown`
instead, so `def f(*args): f(x, *args)` terminates.

**Arities are bounded.** A site call passes the number of arguments that
its role names. Most roles name a fixed number (an item of `reversed` or
`filter` one, a hook two, a key one, the replacement of `re.sub` one); the call back of `map` passes one element per
iterable, so its role holds that number. It counts only the positional
arguments of the call that reaches `map` as its root has them, without the
receivers that bound methods and `__new__` add; the elements of the other
positional arguments go to any later position. So the call back, a new
root, passes fewer arguments than the root of the call that reached `map`,
and a chain of call backs that reach `map` again shrinks: no arity exceeds
the most positional arguments that a call expression or a fixed role
passes. Counting the receivers would not end: with `X.__new__ = Y`,
`Y.__new__ = X` and `Y.__new__ = Caller()`, where `Caller.__call__ = map`,
`Y([1])` calls `map(Y, X, Y, [1])`, whose call back calls `Y` with three
arguments, which calls `map` with five, and so on.

**The cap only helps.** Saturation adds one object, the saturated value,
by which no rule keys an object, a call or a node: no rule sees it, and a
constraint only gives it to its result nodes (see *The solver*). It only
takes objects out of nodes: a node changes at most `cap` + 1
times, and a saturated node gives its constraints' results the saturated
value once and then does nothing. Deciding which classes are unknown only
marks classes, a finite number, and gives their lookups the saturated
value. The code that saturation leaves without a caller is completed as
any other, by the steps at a fixpoint, which are finite. The list of what
reached saturated nodes keeps sets that the solver already made. The
rounds end: each propagation ends, because
the sets only grow and are finite; each round applies each constraint only
to objects that it has not seen; and a round that applies nothing ends the
solve. Since the objects and calls are finite, so are the rounds.

Given finite objects and calls, the nodes and constraints are finite too.
Their keys may hold nodes, but only nodes of a kind that is finite before
them, so no kind of node keys another of its own kind:

| Nodes and constraints | Key |
|---|---|
| Field | object and name |
| What `repr()` of a builtin container reaches | container |
| What a conversion converts with `repr()` | the conversion (made by the builder or by the rule that converts) |
| Lookup | class, name, receiver, `after` and `unless` |
| Rules that wait until a class may answer a name (`Hierarchy.later`) | class, name, `after` and `unless`; in it, one entry per rule with its arguments and receiver, which a constraint makes when it applies to an object |
| Loads of an attribute that no instance has written yet (`Analysis.read_field`) | class and name; in it, the result node of each load with its instances, which a load makes when it applies to an instance |
| A class and the classes of its instances (a class method's receiver, `type[C]`) | class |
| The names of a class or instance, and the members of a class (reflection) | class or instance |
| The analysed classes below an outside class, or their instances (an annotation) | stub class and kind |
| Arguments and result of a call; a model's parameters | the call (and the model) |
| The mode and buffering of an opened file; the buffering that a constant mode reads | the call; the call and the mode, a str from the source |
| Constant node | object |
| What a construct iterates (`xs += ys`, slice store, `extend`) | the operator, the slice, or the arguments of the call bound to the model |
| What an unpacked argument passes (`_Spread`), and its fields | call origin and argument; key of a field of the containers that it unpacks |
| Subscription of a lookup to a field, or to a class's `__getattr__` | field, receiver and lookup node |
| `__getattr__` bound to a receiver, before it becomes a `Fallback` | receiver and lookup node |
| Call back of an argument | call back and argument node |
| Handler of a tuple of exception classes | tuple and handler node |
| Subscription of the filter of a class test to a class expression or a position of a tuple of classes | node, filter (one per test and branch), alternative (one per value of the class expression) and position |

The other rules make nodes and constraints per call and object, or per
constraint and object, and no rule makes a constraint whose application
makes another of its kind without passing through a keyed call or object.

No rule walks a hierarchy with a Python frame per class: lookups,
`type[...]` and class annotations, `except` and class patterns walk a chain
or a fan of classes iteratively, so the analysis needs a few dozen frames
whatever the length or width of a hierarchy. The test analyses a chain and a
fan of 300 classes with at most 200 frames above its own.

**The test.** `tests/test_termination.py` searches seeded random programs
for a counterexample in five families: callables wrapped, bound and
stored back in every order; special methods assigned classes and functions
while iteration, calls, subscripts, `in`, `with`, operators and `yield
from` feed their results back into the values they came from; classes
whose bases are builtin and outside classes read from attributes that get
more values later, with attribute hooks, accessed in every way; typed
outside values fed back into the variable they came from; and classes
whose `__new__`, `__call__` and `__init__` are other classes, callable
instances, class methods and the builtins that call back or make tuples
by arity (`map`, `filter`, `zip`, `sorted` with a key), so that receivers pile up
before a call back that calls a class again. Programs
that once broke the analysis are fixed cases. A program fails the test by
raising any error, by running past a time limit, or by making too many
objects, calls, nodes and per-key constraints, counted over every table of
what the analysis makes on demand; the test lists every table of the
analysis as counted or not, so a new table cannot be left out. The fixed
cases and the first 100 programs of each family must also give the same
call graph when the solver takes its worklist last in, first out.

## Bounds

Seven cut-offs bound what the analysis makes. Six are constants of the
code, the same for every program. The seventh, the cap on the objects of
a node, is the one parameter of the analysis that its user sets
(`CallGraphGenerator(..., cap=...)`, `--cap`): it trades precision and
recall against cost, and what suits a small library does not suit a large
closure of the standard library. The document records it (`tool.cap`).

| Bound | Value | Why | Past it |
|---|---|---|---|
| Names that a computed attribute name may hold (`getattr`, `hasattr`, `setattr`, `delattr`; `DYNAMIC_NAMES_MAX`) | 4 str constants | Precision and cost: a name that may be any of many strings would load every name in the program | The access is dynamic and gets no more names (see *Computed attribute names*) |
| Alternative MROs of a class (`HIERARCHIES_PER_CLASS_MAX`) | 8 | Cost: the hierarchies are the product of the candidates of each base expression | One exhaustive order stands for all of them and finds every definition (see *Alternative hierarchies*) |
| Steps of an outside name past its root (`EXTERNAL_STEPS_PAST_ROOT_MAX`) | 2; 3 for a member found in a stubbed outside base | Termination and precision: loads on generic values would make names without end, which no code calls; a stub class has finitely many members. Only attribute loads extend a name: the result of a call of code without stubs has none | One external without a name (see *External names*) |
| Receivers that a call passes before its arguments (`RECEIVERS_PER_CALL_MAX`) | 3 | Termination: callables that pass receivers on add one at each step (`C.__new__ = D`, `D.__new__ = C`) | The outermost receivers are dropped (see *Termination*) |
| Layers of generic arguments in the stub data (`GENERIC_ARGUMENT_DEPTH_MAX` of `tools/generate_stubs.py`) | 2 | Termination and size: the types of recursive aliases nest without end, and the containers of stubbed results are keyed by the position in the type | A deeper argument keeps its class without its type arguments (see *Stub data*) |
| Nested attachments of constraints in the solver (`_ATTACH_NESTING_MAX`) | 50 | The Python stack: a chain of constraints that attach constraints to nodes that already hold objects would nest calls without end | The application waits for the solve; the result is the same (see *The solver*) |
| Objects that a node holds (the cap, a parameter; `DEFAULT_CAP`) | 5,000 by default; any positive integer, or none | Cost and precision: a hub of generic code (a parameter that every strategy of a library reaches) costs its size times its constraints, and its calls are noise; real registries (the lexers of pygments) stay under it | The node holds the saturated value only: calls of it are unresolved (`saturated`), what it gives is saturated, stores into it are dropped. What it stood for is lost: code reached only through it is code that no analysed code calls, and a set it would have filled holds less, so a rule that depends on how much a set holds (nothing, or at most four computed names) may apply where it would not without the cap and add edges (`leaf -> fallback`, `main -> C.a` in *The solver*). The bound of hierarchies counts candidates too, but fewer candidates give a part of the hierarchies, which the exhaustive order over-approximates: it adds none; the bound of receivers counts the receivers that a call passes, not the objects of a set. A rule that widens a value adds one object (the pattern rule for a class member, see *Computed attribute names*), so a node saturates one object sooner: at a cap of 1 such a widening may lose a call that the analysis without it keeps |

Without a cap (`cap=None`, `--cap none`) no node saturates, and the
analysis is the one without saturation. It still ends in principle (see
*Termination*: the cap only helps), but on inputs where many values meet
(the closure of `json` in the standard library, the strategies of
hypothesis) it may not end in reasonable time or memory.

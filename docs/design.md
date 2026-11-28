# Analysis design

PyCG computes the call graph of a Python package with a static analysis.
It never imports or runs the code. This document gives the analysis in five
ideas, what it does not do, its bounds and its open problems.

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

## Overview

The analysis runs in five stages: the discovery of the modules that the
entry modules import inside the package root; the scopes, which decide the
scope that binds each name; the builder, which walks each module's syntax
tree once and emits nodes and constraints; the solver, which propagates
objects along the constraints until nothing changes and resolves calls as
it goes; and the call graph that it writes.

## The analysis in five ideas

### 1. An assignment graph over objects named by where they are created

Every value is an object identified by the place that creates it: a
function by its definition, an instance by its class and the call that
creates it, a container by its display or call. Each node holds the objects
that may reach it. Assignments, argument passing and returns are subset
edges between nodes. A load, store or call on a node is a constraint that
acts on each object that reaches the node. A worklist solver applies the
constraints until nothing changes, once for the whole program. A call edge
exists where a call constraint meets a function. Python calls `__getattr__`
only when the normal lookup fails, so a load through an instance calls it
only where no class of the MRO defines the name and no `__init__` of the MRO
assigns the name on its receiver in its own body (`self.x = ...`); a load
that runs before that store loses its `__getattr__` call.

### 2. Local names by definition; code that cannot run is not analysed

A name that only the statements of its own scope bind is followed by
definition: each read gets the definitions that reach it, and where paths
meet, a join holds the definitions of each path. Code that the syntax and
the literal values of names prove cannot run is not walked: its calls give
no edges and its definitions do not exist. The heap (attributes, container
elements) is not followed by definition.

### 3. Outside code is typed from the typeshed stubs

The stubs of the builtins, the standard library and the third-party
libraries that typeshed describes are read as data. A call of an outside
function gives what its stub declares. A method of an outside value is
named by the public name of its class. No name is invented for a value
whose type the stubs give. Outside code is not assumed to call what the
analysed code gives it. Only the builtins of Python apply their arguments:
`map`, `sorted(key=...)`, and the special methods of their protocol
parameters (`len(x)` calls `x.__len__`). The other exceptions are `re.sub`
and `re.subn`, which call a callable replacement, `copy.replace`, which
calls `__replace__`, and a table of selected standard-library operations
(`itertools`, `functools.reduce`, `math.sumprod`, `heapq.nlargest`, ...),
which iterate what they get: at the call, or, for a lazy object, where
analysed code advances it. `threading.Thread` and `multiprocessing.Process`
follow CPython: the constructor stores `target`, `args` and `kwargs` in the
instance's `_target`, `_args` and `_kwargs`, `start` calls the instance's
`run` from the site of `start`, and their own `run` calls
`_target(*_args, **_kwargs)`. An instance that their own constructor makes
is one value per call that makes it, so each holds its own target. Of the
overloads that fit a call by arity and keywords, the result is that of
those whose parameter accepts a value of
the first positional argument whose declared types differ between them: a
value accepts a class that its class derives from, a protocol whose methods
its class has, and `float` or `complex` for an `int`. A value of unknown
class, or an argument that holds nothing once the solve settles, keeps
every overload: `re.sub("a", "b", s)` gives a `str`, `re.sub(p, "b", s)`
with `p` unknown a `str` and a `bytes`. A constrained type variable
(`AnyStr`) is solved to the constraints that the class of its argument
derives from, and an instance of a class whose type parameter is one keeps
the constraint it was made with: `re.compile("x")` is a `Pattern[str]`,
its `match` a `Match[str]` (as receiver it accepts only overloads declared
for `Pattern[str]`), and that receiver solves its class's variable, so
`group` gives a `str`. A value of unknown class keeps every constraint.

### 4. Declared types supply what value flow cannot

A call edge exists only where analysed code makes the call. Values that
only outside callers could supply come from two declarations. A function
that no analysed code calls is an entry point: its receiver is any instance
of its class or of a subclass that inherits it, and its parameters take
their defaults. An annotation of a parameter, or of an assignment, names
what the parameter or the target may hold: the instances of the class it
names and of its subclasses. For an abstract class of outside code, which
no value of its own can be, the subclasses are the analysed classes that
derive from it (`it: AsyncIterator[T]` holds the instances of the analysed
async iterators). For the protocols that the builtin types implement
(`Iterable`, `Sized`, ...), only those that derive from them through
abstract classes count: for a class that reaches one only through a
concrete class (a subclass of `list`), a client most likely passes a
builtin. A stub `x.pyi` that the package ships beside `x.py` gives the
annotations that the source leaves out, and the bases of its classes for
what an annotation names.

### 5. The result does not depend on the order of the solve, and the solve ends

Rules only add facts. A rule subscribes to a points-to set and acts on each
object that arrives, in any order. The few decisions that read what a node
holds (does a base hold anything, does a receiver hold anything) run only
at a fixpoint, in a fixed order, and they add facts too. A class lookup
waits until the class hierarchy is complete. A node that would hold more
objects than the cap holds one saturated value instead, about which nothing
is known; the solve applies rules to a node's objects only once propagation
has filled it, in rounds, so which objects a node's rules saw before it
saturated does not depend on the order either. The solve ends because every
object and every call is keyed by finite things: source positions, names
from the source, and a bounded context (see [Bounds](#bounds)). So
`x = x.parent` on an outside value adds one name, and a class stored as its
own `__iter__` makes one instance per loop.

## What the analysis does not do

- **No flow-sensitive heap.** An attribute or container element holds
  every value ever stored there, so `d["k"] = a; d["k"] = b; d["k"]()`
  calls both.
- **No calling context.** A parameter holds what every caller passes, so a
  helper that forwards its arguments mixes the values of all its callers.
- **No model of what outside code calls.** A function given to outside
  code (a callback) gets no edge from that code, except for the exceptions
  that idea 3 names; if no analysed code calls it, it is an entry point and
  its body is analysed.
- **No code built at run time.** `eval`, `exec`, and attribute names
  computed from more than four strings are not followed, so the calls that
  they make give no edges.

## Bounds

The cap on the objects of a node is the one setting of the analysis
(`--cap`, 5,000 by default, or none): it trades precision and recall against
cost, and the document records it. Every other bound is the same for every
program, and reaching any bound is visible in the output.

| Bound | Value | Past it |
|---|---|---|
| Names that a computed attribute name may hold (`getattr`, `hasattr`, `setattr`, `delattr`) | 4 string constants, besides, for a load, the names of a class whose namespace the code reads by name | The access is dynamic and gets no more names; a call through it is unresolved (`computed name`) |
| Alternative method resolution orders of a class | 8 | One exhaustive order stands for all of them and finds every definition |
| Steps of an outside name past its root | 2; 3 for a member of a stubbed outside base | One outside value without a name; a call of it is unresolved (`outside value`) |
| Receivers that a call passes before its arguments | 3 | The outermost receivers are dropped |
| Layers of generic arguments in the stub data (the stub generator) | 2 | A deeper argument keeps its class without its type arguments |
| Nested attachments of constraints in the solver | 50 | The application waits in a queue for the solve |
| Nesting of a top-level statement | 247 levels | The builder stops before the statement; the module is `partial`, with the cause `DeepNesting` |
| The parser, as CPython 3.14 | At most 99 levels of indentation, 200 nested brackets, 149 nested f-strings or t-strings, and a statement depth of 43,482 | The module fails with the error that CPython gives (`IndentationError`, `SyntaxError`, `RecursionError`) |
| Objects that a node holds (the cap) | 5,000 by default | The node holds the saturated value only: calls of it are unresolved (`saturated`), what it gives is saturated, and stores into it are dropped |

The solver applies a constraint attached to a node that already holds
objects at once, by recursion; the bound of 50 keeps that recursion within
the stack. The result does not depend on its value, since the solve does
not depend on its order.

The bound of 247 levels was measured for the Python engine: the deepest
nesting that a recursive walk of the syntax tree built at Python's default
recursion limit. No stack forces it in the Rust engine, whose parse thread
has a stack sized from the source; it remains because it defines when a
module is `partial`. The deepest statement of the micro, macro and scale
sets is 31 levels.

What a saturated node stood for is lost: code reached only through it is
code that no analysed code calls, and a rule that depends on how much a set
holds may apply where it would not without the cap. Without a cap no node
saturates; the analysis still ends in principle, but on inputs where many
values meet it may not end in reasonable time or memory.

## Open problems

- **It does not finish on the standard library as analysed code.** Without
  calling context, code that calls a stored callable with stored arguments
  passes every argument to every callable, and the fixpoint grows without
  practical end.
- **`type(x)` gives a typed `type`, not the class of `x`.** Following the
  class would make hubs of values instantiate their own classes until
  memory ends.
- **Overloads are selected by one argument.** A call of an outside
  function gives the union of the overloads that the first deciding
  argument accepts (idea 3); later arguments do not narrow it, so
  `os.path.join(p, "a")` with `p` unknown gives a `str` and a `bytes`. The
  mode of an opened file is selected by a table of Python's rule.
- **Small measured imprecisions.** The result of a coroutine function names
  any attribute.

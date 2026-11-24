"""Names of the standard library, looked up by static inspection.

Not part of the scoring: score.py matches names through the committed
table common/same_function.json and imports nothing. This module serves
the test of the table (tests/test_same_function_table.py), which checks
that the names of each group are one object.

The lookup imports only the modules of ALLOWED_MODULES and reads the
`__dict__` of each object; no property, descriptor or `__getattr__` runs.
An allowed module may still import others and initialise its own objects
when it is imported, so what a name finds can depend on what was imported
before (this is why the scoring does not use it).
"""

import builtins
import importlib
import inspect
import types
import warnings


def same_object(first, second):
    """Whether two names resolve to one function (resolve)."""
    a, b = resolve(first), resolve(second)
    return a[0] == b[0] == "object" and a[1] is b[1]


# The only modules that the name lookup imports: standard-library modules
# and submodules that do nothing but define names when imported. A name
# through any other module (third-party, a `__main__` entry point,
# `antigravity`, `this`, a GUI toolkit) is not looked up.
ALLOWED_MODULES = frozenset(
    """
    _collections_abc _io _random
    abc argparse array ast asyncio atexit base64 binascii bisect builtins bz2
    calendar codecs collections collections.abc colorsys concurrent
    concurrent.futures configparser contextlib contextvars copy copyreg csv
    dataclasses datetime decimal difflib dis email email.message email.utils
    enum errno fnmatch fractions functools gc getopt gettext glob graphlib gzip
    hashlib heapq hmac html html.parser http http.client importlib
    importlib.machinery importlib.metadata importlib.resources importlib.util
    inspect io ipaddress itertools json json.decoder json.encoder keyword
    linecache locale logging logging.config logging.handlers lzma math
    mimetypes multiprocessing numbers operator os os.path pathlib pickle
    pkgutil platform posixpath pprint queue quopri random re reprlib sched
    secrets select selectors shlex shutil signal socket stat statistics string
    struct subprocess sys sysconfig tarfile tempfile textwrap threading time
    timeit token tokenize tomllib traceback types typing unicodedata urllib
    urllib.error urllib.parse urllib.request uuid warnings weakref xml
    xml.etree xml.etree.ElementTree zipfile zlib zoneinfo
    """.split()
)
_MISSING = object()


def resolve(name):
    """("object", the function), ("missing", last object found) or
    ("unknown", None), by static inspection only.

    The longest dotted prefix of `name` in ALLOWED_MODULES is imported, with
    warnings ignored (`<builtin>` is the builtins module); nothing else is
    imported. The rest is looked up in the `__dict__` of each object: of a
    module (a submodule is never taken from it: it is there only if
    something imported it), of a class and its MRO (not its metaclass), of
    an instance and then its type (inspect.getattr_static). No property,
    descriptor or `__getattr__` runs. The function is function_of the
    object found. Any exception makes the name unknown."""
    parts = name.split(".")
    if parts[0] == "<builtin>":
        obj, rest = builtins, parts[1:]
    else:
        prefixes = [".".join(parts[:i]) for i in range(len(parts), 0, -1)]
        allowed = [m for m in prefixes if m in ALLOWED_MODULES]
        if not allowed:
            return "unknown", None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                obj = importlib.import_module(allowed[0])
        except BaseException:  # an import must not stop the lookup
            return "unknown", None
        rest = parts[len(allowed[0].split(".")) :]
    try:
        for part in rest:
            if is_function(obj):
                return "missing", obj  # a path through the return value
            found = _attribute(obj, part)
            if found is _MISSING:
                return "missing", obj
            obj = found
        function = function_of(obj)
    except BaseException:  # nothing of the lookup may stop its caller
        return "unknown", None
    if function is None:
        return "missing", obj
    return "object", function


def is_function(obj):
    """A function or method, not a class: its attributes are not callees."""
    return callable(obj) and not inspect.isclass(obj) and not inspect.ismodule(obj)


def _attribute(obj, name):
    """An attribute as the static `__dict__` of `obj` holds it (resolve)."""
    if inspect.ismodule(obj):
        found = vars(obj).get(name, _MISSING)
        return _MISSING if inspect.ismodule(found) else found
    if inspect.isclass(obj):
        for klass in obj.__mro__:
            if name in vars(klass):
                return vars(klass)[name]
        return _MISSING
    return inspect.getattr_static(obj, name, _MISSING)


def function_of(obj):
    """The function that a call through `obj` runs, without calling
    anything, or None: a static or class method is its function, a property
    its getter, a bound method its function, a method bound to an object
    of a builtin type the descriptor of that type; a function, a class or a
    descriptor of a builtin type is itself. Anything else (a module, an
    object that is not callable, a cached property) is None."""
    if isinstance(obj, (staticmethod, classmethod)):
        return obj.__func__
    if isinstance(obj, property):
        return obj.fget
    if isinstance(obj, types.MethodType):
        return obj.__func__
    if isinstance(obj, types.BuiltinMethodType):
        owner = obj.__self__
        if owner is None or inspect.ismodule(owner):
            return obj  # a builtin function
        klass = owner if inspect.isclass(owner) else type(owner)
        found = _attribute(klass, obj.__name__)
        # The type may hold this very builtin (object.__new__): it is itself.
        return obj if found is obj else function_of(found)
    if inspect.ismodule(obj) or not callable(obj):
        return None
    return obj

import builtins
import importlib
import inspect
import types
import warnings

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
        except BaseException:
            return "unknown", None
        rest = parts[len(allowed[0].split(".")) :]
    try:
        for part in rest:
            path_through_return_value = is_function_not_class(obj)
            if path_through_return_value:
                return "missing", obj
            found = _static_attribute(obj, part)
            if found is _MISSING:
                return "missing", obj
            obj = found
        function = function_of(obj)
    except BaseException:
        return "unknown", None
    if function is None:
        return "missing", obj
    return "object", function


def is_function_not_class(obj):
    return callable(obj) and not inspect.isclass(obj) and not inspect.ismodule(obj)


def _static_attribute(obj, name):
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
    if isinstance(obj, (staticmethod, classmethod)):
        return obj.__func__
    if isinstance(obj, property):
        return obj.fget
    if isinstance(obj, types.MethodType):
        return obj.__func__
    if isinstance(obj, types.BuiltinMethodType):
        owner = obj.__self__
        is_builtin_function = owner is None or inspect.ismodule(owner)
        if is_builtin_function:
            return obj
        klass = owner if inspect.isclass(owner) else type(owner)
        found = _static_attribute(klass, obj.__name__)
        type_holds_this_very_builtin = found is obj
        return obj if type_holds_this_very_builtin else function_of(found)
    if inspect.ismodule(obj) or not callable(obj):
        return None
    return obj

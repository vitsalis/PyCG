import argparse
import ast
import json
import os
import struct
import sys
import tempfile
import tokenize
import warnings
from pathlib import Path

DESCRIPTION = """\
Writes the test vectors of pycg_syntax from the Python of the oracle:
reading.txt, the text or the failure that reading a file of given bytes
gives (program._read, then program._parse, with program._cause), and
positions.txt, the kind and position of every node of each program of
programs/, in ast.walk order, and constants.txt, the value of every
Constant of each program of constants/, in that order, and for each
program of scopes/ the D1 scopes dump of its scope pass (scopes.py) in
scopes/<program>.txt, as `pycg_dump d1-scopes FILE m` writes it. Run it
with the Python of the oracle; the output is committed.
"""

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pycg.analysis.scopes import analyse_scopes  # noqa: E402

OUT = ROOT / "crates" / "pycg_syntax" / "tests" / "vectors"

READING = {
    "empty": b"",
    "plain": b"x = 1\n",
    "bom": b"\xef\xbb\xbfx = 1\n",
    "bom-only": b"\xef\xbb\xbf",
    "bom-bad-first-line": b"\xef\xbb\xbfx = '\xff'\n",
    "bom-bad-later": b"\xef\xbb\xbfa = 1\nb = '\xe2\x82'\n",
    "bom-cookie-utf8": b"\xef\xbb\xbf# coding: utf-8\nx = 1\n",
    "bom-cookie-latin1": b"\xef\xbb\xbf# coding: latin-1\nx = 1\n",
    "bad-first-line": b"x = '\xff'\n",
    "bad-later": b"a = 1\nb = '\xe2\x82'\n",
    "bad-truncated-end": b"a = 1\n# \xe2\x82",
    "surrogate": b"a = 1\n# \xed\xa0\x80\n",
    "latin1-cookie": b"# -*- coding: latin-1 -*-\nx = '\xff'\n",
    "cookie-second-line": b"#!/usr/bin/env python\n# coding=latin-1\nx = '\xe9'\n",
    "cookie-after-code": b"x = 1\n# coding: latin-1\ny = '\xe9'\n",
    "cookie-third-line": b"#\n#\n# coding: latin-1\ny = '\xe9'\n",
    "cookie-blank-first": b"\n# coding: latin-1\ny = '\xe9'\n",
    "cookie-unknown": b"# coding: klingon\nx = 1\n",
    "cookie-bad-line": b"# \xff coding: latin-1\nx = 1\n",
    "cookie-space-name": b"# vim: set fileencoding = latin-1 :\nx = '\xe9'\n",
    "cookie-equals": b"# coding=cp1252\nx = '\x80'\n",
    "cookie-cp1252-undefined": b"# coding: cp1252\nx = '\x81'\n",
    "cookie-utf8-variant": b"# coding: UTF8\nx = 1\n",
    "cookie-utf8-long": b"# coding: utf-8-unix\nx = 1\n",
    "cookie-latin-variant": b"# coding: ISO_8859_1\nx = '\xe9'\n",
    "cookie-ascii": b"# coding: ascii\nx = '\xe9'\n",
    "cookie-koi8": b"# coding: koi8-r\nx = '\xc1'\n",
    "cookie-mac-roman": b"# coding: mac-roman\nx = '\x8a'\n",
    "cookie-dashed-unknown": b"# coding: cp-1252\nx = 1\n",
    "cookie-not-comment": b"x = 1  # coding: latin-1\ny = '\xe9'\n",
    "crlf": b"a = 1\r\nb = 2\r\n",
    "cr": b"a = 1\rb = 2\r",
    "mixed-newlines": b"a = 1\r\nb = 2\rc = 3\n",
    "nul-first-line": b"a = 1\x00\n",
    "nul-third-line": b"a = 1\nb = 2\nc\x00 = 3\n",
    "syntax-error": b"a = (\n",
    "indentation": b"if x:\npass\n",
    "unexpected-indent": b"a = 1\n  b = 2\n",
    "parentheses-200": b"(" * 200 + b"1" + b")" * 200 + b"\n",
    "parentheses-201": b"(" * 201 + b"1" + b")" * 201 + b"\n",
    "indentation-99": b"".join(b" " * i + b"if x:\n" for i in range(99))
    + b" " * 99
    + b"pass\n",
    "indentation-100": b"".join(b" " * i + b"if x:\n" for i in range(100))
    + b" " * 100
    + b"pass\n",
    "unindent-mismatch": b"if x:\n  a\n b\n",
    "tab-then-spaces": b"if x:\n\ta\n        b\n",
    "spaces-then-tab": b"if x:\n        a\n\tb\n",
    "tabs-consistent": b"if x:\n\tif y:\n\t\ta\n\tb\n",
    "unclosed": b"a = (\n",
    "unclosed-before-error": b"a = (\nb = 2\n",
    "unclosed-inner": b"a = [1,\n  (2,\n",
    "unclosed-no-newline": b"x = 1\ny = (\nz",
    "mismatched-close": b"a = (]\n",
    "unmatched-close": b"a = )\n",
    "unmatched-before-unclosed": b"x = )\ny = (\n",
    "python-315-lazy-import": b"lazy import json\n",
    "python-315-unpacking": b"[*x for x in y]\n",
}

PROGRAMS = OUT / "programs"
CONSTANTS = OUT / "constants"
SCOPES = OUT / "scopes"
SCOPES_MODULE = "m"


def cause(error):
    name = type(error).__name__
    if isinstance(error, SyntaxError) and error.lineno:
        return f"{name} (line {error.lineno})"
    if isinstance(error, UnicodeDecodeError):
        return f"{name} (byte {error.start})"
    return name


def read(data):
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "module.py")
        Path(path).write_bytes(data)
        try:
            with tokenize.open(path) as file:
                source = file.read()
        except (OSError, SyntaxError, UnicodeDecodeError) as error:
            return "failed", cause(error)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ast.parse(source, path)
        except (SyntaxError, ValueError, RecursionError) as error:
            return "failed", cause(error)
        return "ok", source.encode("utf-8").hex()


def positions(source):
    for node in ast.walk(ast.parse(source)):
        if hasattr(node, "lineno") and not isinstance(node, ast.TypeIgnore):
            yield (
                f"{type(node).__name__} {node.lineno} {node.col_offset} "
                f"{node.end_lineno} {node.end_col_offset}"
            )


def value(constant):
    if constant is ...:
        return "Ellipsis"
    match constant:
        case None:
            return "None"
        case bool():
            return f"Bool {constant}"
        case int():
            return f"Int {constant}"
        case float():
            return f"Float {struct.pack('>d', constant).hex()}"
        case complex():
            real = struct.pack(">d", constant.real).hex()
            return f"Complex {real} {struct.pack('>d', constant.imag).hex()}"
        case str():
            return " ".join(["Str", *(f"{ord(c):x}" for c in constant)])
        case bytes():
            return f"Bytes {constant.hex()}"
    raise AssertionError(constant)


def constants_lines():
    for path in sorted(CONSTANTS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        yield f"case {path.stem} {source.encode('utf-8').hex()}"
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant):
                yield value(node.value)
        yield "end"


def place(node):
    return [node.lineno, node.col_offset] if hasattr(node, "lineno") else None


def compact(value):
    return json.dumps(value, separators=(",", ":"))


def scope_record(scopes, scope):
    definitions = scope.definitions
    return {
        "scope": scope.name,
        "kind": scope.kind,
        "local": scope.local_name,
        "position": place(scope.node),
        "generator": scope.generator,
        "async": scope.asynchronous,
        "bound": list(scope.bound),
        "defined": list(scope.defined),
        "globals": sorted(scope.globals),
        "nonlocals": sorted(scope.nonlocals),
        "rebound": sorted(scope.rebound),
        "shared": sorted(scope.shared),
        "star_import": scope.star_import,
        "dynamic": scope.dynamic,
        "imports": [[name, scope.imports[name]] for name in sorted(scope.imports)],
        "definitions": [
            [name, None if definitions[name] is None else place(definitions[name])]
            for name in sorted(definitions)
        ],
        "resolved": [
            [name, scopes.resolve(scope, name).name] for name in sorted(scope.reads)
        ],
    }


def scope_lines(tree):
    scopes = analyse_scopes(tree, SCOPES_MODULE)
    for scope in scopes.scopes:
        yield compact(scope_record(scopes, scope))
    loops = sorted(
        (place(node), [[name, unbinds] for name, unbinds in names.items()])
        for node, names in scopes._loops.items()
    )
    for at, names in loops:
        yield compact({"loop": at, "names": names})
    unread = [
        place(alias)
        for alias in ast.walk(tree)
        if isinstance(alias, ast.alias) and alias in scopes.unread_lazy
    ]
    yield compact({"unread_lazy": unread})


def reading_lines():
    for name, data in READING.items():
        status, value = read(data)
        yield f"{name}\t{data.hex()}\t{status}\t{value}"


def positions_lines():
    for path in sorted(PROGRAMS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        yield f"case {path.stem} {source.encode('utf-8').hex()}"
        yield from positions(source)
        yield "end"


def main(argv):
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.parse_args(argv)
    version = f"python {sys.version.split()[0]}"
    written = (
        ("reading", reading_lines()),
        ("positions", positions_lines()),
        ("constants", constants_lines()),
    )
    for name, lines in written:
        text = "".join(f"{line}\n" for line in (version, *lines))
        (OUT / f"{name}.txt").write_text(text, encoding="ascii")
    for path in sorted(SCOPES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        text = "".join(f"{line}\n" for line in scope_lines(tree))
        path.with_suffix(".txt").write_text(text, encoding="ascii")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

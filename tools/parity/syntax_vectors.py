import argparse
import ast
import json
import os
import struct
import subprocess
import sys
import tempfile
import tokenize
import unicodedata
import warnings
from pathlib import Path

DESCRIPTION = """\
Writes the test vectors of pycg_syntax from the Python of the oracle:
reading.txt, the text or the failure that reading a file of given bytes
gives (program._read, then program._parse, with program._cause), and
positions.txt, the kind and position of every node of each program of
programs/, in ast.walk order, and constants.txt, the value of every
Constant of each program of constants/, in that order, and for each
program of d1/ the D1 records of its module, as tools/parity/dump.py
writes them, in d1/<program>.jsonl, and
names.txt, the NFKC normalisation of strings and the answer of
str.isidentifier at the bounds of the identifier ranges. Run it with the
Python of the oracle; the output is committed.
"""

ROOT = Path(__file__).resolve().parents[2]

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
D1 = OUT / "d1"
DUMP = ROOT / "tools" / "parity" / "dump.py"


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


def d1_lines(path):
    with tempfile.TemporaryDirectory() as out:
        command = [sys.executable, "-I", str(DUMP), "input", "--checkout", str(ROOT)]
        command += ["--out", out, "--package", str(path.parent), str(path)]
        subprocess.run(command, check=True)
        records = Path(out, "D1.jsonl").read_text(encoding="utf-8").splitlines()
    return [line for line in records if json.loads(line)["module"] == path.stem]


NFKC_SEQUENCES = (
    "e\u0301",
    "a\u0328\u0301",
    "a\u0301\u0328",
    "\u1e9b\u0323",
    "\u1100\u1161\u11a8",
    "\uac00\u11a8",
    "\u1100\u1161",
    "\ufb01le",
    "\u2126\u212b",
    "\u0344\u0301",
    "o\u0308\u0304\u0301",
    "\u0b47\u0b3e",
    "\u1fbf\u0301",
)


def hexes(text):
    return ",".join(f"{ord(c):x}" for c in text) or "-"


def names_lines():
    single = (chr(p) for p in range(0x110000) if not 0xD800 <= p < 0xE000)
    changed = (c for c in single if unicodedata.normalize("NFKC", c) != c)
    for text in (*changed, *NFKC_SEQUENCES):
        yield f"nfkc {hexes(text)} {hexes(unicodedata.normalize('NFKC', text))}"
    for point in identifier_bounds():
        character = chr(point)
        yield f"start {point:x} {character.isidentifier()}"
        yield f"continue {point:x} {('a' + character).isidentifier()}"


def identifier_bounds():
    points = set()
    previous_start = previous_continue = False
    for point in range(0x110001):
        surrogate = 0xD800 <= point < 0xE000
        inside = point < 0x110000 and not surrogate
        start = inside and chr(point).isidentifier()
        continuing = inside and ("a" + chr(point)).isidentifier()
        if start != previous_start or continuing != previous_continue:
            points.update(p for p in (point - 1, point) if 0 <= p < 0x110000)
        previous_start, previous_continue = start, continuing
    return sorted(p for p in points if not 0xD800 <= p < 0xE000)


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
        ("names", names_lines()),
    )
    for name, lines in written:
        text = "".join(f"{line}\n" for line in (version, *lines))
        (OUT / f"{name}.txt").write_text(text, encoding="ascii")
    for path in sorted(D1.glob("*.py")):
        text = "".join(f"{line}\n" for line in d1_lines(path))
        path.with_suffix(".jsonl").write_text(text, encoding="ascii")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

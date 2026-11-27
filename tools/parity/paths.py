import argparse
import itertools
import ntpath
import os
import posixpath
import sys
from pathlib import Path

DESCRIPTION = """\
Writes crates/analysis/src/program/path_vectors.rs, what the path functions of
pycg_analysis::program are tested against: every function that program.py,
imports.py and document.py take from os.path, run by Python 3.14's posixpath
and ntpath on paths made of the roots, bodies and names below; where Python
raises ValueError, the case expects "ValueError: " and its message.

    python3 -I tools/parity/paths.py
"""

ROOT = Path(__file__).resolve().parents[2]
VECTORS_PATH = ROOT / "crates" / "analysis" / "src" / "program" / "path_vectors.rs"
FLAVOURS = {"posix": posixpath, "nt": ntpath}
ROOTS = {
    "posix": ("", "/", "//", "///"),
    "nt": (
        "",
        "\\",
        "/",
        "C:",
        "c:\\",
        "C:/",
        "\\\\srv\\shr",
        "//srv/shr/",
        "\\\\srv",
        "\\\\?\\C:\\",
        "\\\\?\\UNC\\srv\\shr\\",
        "\\\\.\\dev\\",
    ),
}
BODIES = (
    "",
    "a",
    "a/b",
    "a\\b",
    "a//b/",
    "./a",
    "a/./b",
    "a/..",
    "../a",
    "a/../..",
    "A/B.py",
    "a.b.py",
    "..",
    ".",
    "a/b/../../..",
)
CWDS = {"posix": ("/w/x", "/"), "nt": ("C:\\w\\x", "\\\\srv\\shr\\w", "D:\\")}
NAMES = ("a.py", ".bashrc", "..a.b", "a.", "a..", "...", "a.tar.gz", "name", "")


def paths(flavour):
    for root, body in itertools.product(ROOTS[flavour], BODIES):
        yield root + body


def cases():
    for flavour, module in FLAVOURS.items():
        found = list(dict.fromkeys(paths(flavour)))
        absolute = [module.abspath(path) for path in found]
        for path in found:
            yield flavour, "normpath", (path,), module.normpath
            yield flavour, "split", (path,), module.split
            for cwd in CWDS[flavour]:
                yield flavour, "abspath", (path, cwd), module.abspath
        for path, other in itertools.product(found[:: len(BODIES)], found):
            yield flavour, "join", (path, other), module.join
        for path, start in itertools.product(absolute[::3], absolute[::5]):
            for cwd in CWDS[flavour][:1]:
                yield flavour, "relpath", (path, start, cwd), module.relpath
        for first, second in itertools.combinations(absolute[::4], 2):
            yield flavour, "commonpath", (first, second), module.commonpath
            if flavour == "nt":
                upper = (first, second.upper())
                yield flavour, "commonpath", upper, module.commonpath
        for name in NAMES:
            yield flavour, "splitext", (name,), module.splitext


def call(function, name, arguments):
    if name == "abspath":
        path, cwd = arguments
        os.getcwd = lambda: cwd
        return function(path)
    if name == "relpath":
        path, start, cwd = arguments
        os.getcwd = lambda: cwd
        return function(path, start)
    if name == "commonpath":
        return function(list(arguments))
    return function(*arguments)


def shown(result):
    return "|".join(result) if isinstance(result, tuple) else result


def rust_text(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def rust_case(flavour, name, arguments, result):
    listed = ", ".join(rust_text(argument) for argument in arguments)
    return (
        f"    Case {{ flavour: {rust_text(flavour)}, function: {rust_text(name)}, "
        f"arguments: &[{listed}], expected: {rust_text(shown(result))} }},"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args(argv)
    assert sys.version_info[:2] == (3, 14), sys.version
    getcwd = os.getcwd
    lines = []
    refused = 0
    for flavour, name, arguments, function in cases():
        try:
            result = call(function, name, arguments)
        except ValueError as error:
            refused += 1
            result = f"ValueError: {error}"
        lines.append(rust_case(flavour, name, arguments, result))
    os.getcwd = getcwd
    text = "\n".join(
        [
            "pub struct Case {",
            "    pub flavour: &'static str,",
            "    pub function: &'static str,",
            "    pub arguments: &'static [&'static str],",
            "    pub expected: &'static str,",
            "}",
            "",
            "#[rustfmt::skip]",
            "pub const CASES: &[Case] = &[",
            *lines,
            "];",
            "",
        ]
    )
    VECTORS_PATH.write_text(text, encoding="utf-8")
    path = VECTORS_PATH.relative_to(ROOT)
    print(f"{len(lines)} cases in {path}, {refused} of them ValueError")


if __name__ == "__main__":
    main()

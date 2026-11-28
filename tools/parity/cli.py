import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DESCRIPTION = """\
Writes what the Rust command line is tested against, from Python 3.14 in the
pycg-eval-runner image (docs/rust/PLAN.md, section 5, Command line):

- crates/pycg/tests/cli/vectors.rs: every argument vector of VECTORS, run
  under every name of PROGRAMS and every COLUMNS of WIDTHS, and the cases of
  NAMED and SIZED. Each runs pycg.__main__.main as the console script pycg
  runs it, with CallGraphGenerator.analyze replaced by a stop, and records
  the exit status, standard output and standard error, or, when the
  arguments reach the analysis, the parsed namespace.
- crates/pycg/src/unicode.rs: the characters that str.isdecimal, int(),
  str.isspace and str.isprintable accept.

    python3 -I tools/parity/cli.py
"""

ROOT = Path(__file__).resolve().parents[2]
VECTORS_PATH = ROOT / "crates" / "pycg" / "tests" / "cli" / "vectors.rs"
TABLES_PATH = ROOT / "crates" / "pycg" / "src" / "unicode.rs"
ANALYSED_STATUS = 3
CODE_POINTS = 0x110000
ASCII_END = 0x80
DIGITS_PER_BLOCK = 10
INT_DIGITS_MAX = 4300
WIDTHS = ("40", "80", "200")
PROGRAMS = (b"pycg", b"/opt/tools/bin/callgraph")
LONG_PROGRAM = b"/opt/" + b"a_program_name_long_enough_for_its_own_usage_line" * 2
VECTORS = (
    (),
    ("a.py",),
    ("a.py", "--cap", "5", "b.py"),
    ("--cap",),
    ("--cap", "x"),
    ("--cap", "0"),
    ("--cap", "none"),
    ("--cap=7", "a.py"),
    ("--pack", "x"),
    ("--package-n", "n", "a.py"),
    ("-o",),
    ("-ofile", "a.py"),
    ("--foo", "a.py"),
    ("a.py", "--", "--cap"),
    ("-h", "--cap", "x"),
    ("--cap", "x", "-h"),
    ("-x",),
    ("--cap", "+5"),
    ("--cap", "05"),
    ("--cap", "٣"),
    ("--package",),
    ("--output=o.json",),
    ("--cap", "-1"),
    ("a.py", "b.py", "--package", "p"),
    ("-h",),
    ("--help",),
    ("--package-name",),
    ("--package-version",),
    ("--output",),
    ("-hx",),
    ("-h=1",),
    ("--help=x",),
    ("--cap=",),
    ("--package=",),
    ("-q", "a.py"),
    ("--unknown",),
    ("--foo=1", "a.py"),
    ("-o=",),
    ("-o=x", "a.py"),
    ("--pack=x",),
    ("--p",),
    ("--=x",),
    ("--h",),
    ("--he=1",),
    ("-h-",),
    ("-ho",),
    ("-hofile",),
    ("-oh", "a.py"),
    ("--c", "3", "a.py"),
    ("--package-version=1.0", "--package-name=n", "a.py"),
    ("--cap", "none", "--cap", "4"),
    ("--cap", "3", "--cap", "x"),
    ("--foo", "-h"),
    ("-h", "--foo"),
    ("a.py", "--cap", "5", "--", "b.py"),
    ("--", "-h"),
    ("--", "--", "a.py"),
    ("-", "a.py"),
    ("-1",),
    ("-.5", "a.py"),
    ("-.x",),
    ("-a b",),
    ("--package x",),
    ("-o", "-"),
    ("-o", "-x"),
    ("-o", "-1"),
    ("--package", "--cap"),
    ("--cap", "1٣"),
    ("--cap", "٠"),
    ("--cap", "𝟗"),
    ("--cap", "²"),
    ("--cap", " 5"),
    ("--cap", "5_0"),
    ("--cap", "99999999999999999999999999"),
    ("--cap", "1" * INT_DIGITS_MAX),
    ("--cap", "1" * (INT_DIGITS_MAX + 1)),
    ("--cap", "it's"),
    ("--cap", "a\"b'c"),
    ("--cap", "\t\n\r\x7f\x01\\"),
    ("--cap", "​\xa0é\U0001f600\U000e0001"),
    ("--foo", "-y", "--bar=1", "a.py"),
    ("a.py", "b.py", "c.py"),
    (
        "--package-name",
        "n",
        "--package-version",
        "1.0",
        "-o",
        "out.json",
        "--package",
        "p",
        "--cap",
        "none",
        "x.py",
        "y.py",
    ),
    (b"--cap", b"\xff"),
    (b"a\xff.py", b"--package", b"p\xe2\x82"),
    (b"--\xff",),
    (b"-h\xff",),
    ("view", "d.json"),
)
NAMED = (
    (LONG_PROGRAM, ("--foo",)),
    (LONG_PROGRAM, ("-h",)),
    (b"/bin/py\xffcg", ("--foo",)),
    (b"/bin/py\xffcg", ("-h",)),
    (b"pycg\n\n\n", ("--foo",)),
    (b"", ("-h",)),
)
SIZED = (
    None,
    "",
    "0",
    "-5",
    "1",
    "20",
    "33",
    " 60 ",
    " 60",
    "6_0",
    "6__0",
    "_60",
    "+60",
    "٦٠",
    "\x1c60",
    "x",
    "1" * 30,
    "1" * (INT_DIGITS_MAX + 1),
)
SIZED_VECTORS = (("-h",), ("--foo",))
ORACLE = f"""\
import argparse
import json
import sys

sys.path.insert(0, sys.argv[1])
sys.argv = sys.argv[2:]

import pycg.__main__ as main

parsed = []
parse_args = argparse.ArgumentParser.parse_args


def record(parser, *arguments, **keywords):
    namespace = parse_args(parser, *arguments, **keywords)
    parsed.append(namespace)
    return namespace


class Analysed(Exception):
    pass


def analyse(generator):
    raise Analysed


argparse.ArgumentParser.parse_args = record
main.CallGraphGenerator.analyze = analyse
try:
    main.main()
except Analysed:
    namespace = vars(parsed[0])
    cap = namespace["cap"]
    namespace["cap"] = None if cap is None else str(cap)
    sys.stdout.write(json.dumps(namespace))
    sys.exit({ANALYSED_STATUS})
"""


def encoded(text):
    return text if isinstance(text, bytes) else os.fsencode(text)


def run_oracle(program, arguments, columns):
    environment = dict(os.environ)
    environment.pop("COLUMNS", None)
    environment.pop("LINES", None)
    if columns is not None:
        environment["COLUMNS"] = columns
    command = [sys.executable, "-I", "-c", ORACLE, str(ROOT), program]
    completed = subprocess.run(
        command + [encoded(argument) for argument in arguments],
        env=environment,
        capture_output=True,
        check=False,
    )
    if completed.returncode == ANALYSED_STATUS:
        assert completed.stderr == b"", completed.stderr
        return {"parsed": json.loads(completed.stdout)}
    assert completed.returncode in (0, 2), completed
    return {
        "status": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def rust_bytes(data):
    escapes = {ord('"'): '\\"', ord("\\"): "\\\\", ord("\n"): "\\n", ord("\t"): "\\t"}
    pieces = []
    for byte in data:
        if byte in escapes:
            pieces.append(escapes[byte])
        elif 0x20 <= byte < 0x7F:
            pieces.append(chr(byte))
        else:
            pieces.append(f"\\x{byte:02x}")
    return 'b"' + "".join(pieces) + '"'


def rust_text(text):
    return "None" if text is None else f"Some({rust_bytes(encoded(text))})"


def rust_list(texts):
    return "&[" + ", ".join(rust_bytes(encoded(text)) for text in texts) + "]"


def rust_outcome(outcome):
    if "parsed" in outcome:
        namespace = outcome["parsed"]
        fields = [
            f"entry_points: {rust_list(namespace['entry_point'])}",
            f"package: {rust_text(namespace['package'])}",
            f"package_name: {rust_text(namespace['package_name'])}",
            f"package_version: {rust_text(namespace['package_version'])}",
            f"output: {rust_text(namespace['output'])}",
            f"cap: {rust_text(namespace['cap'])}",
        ]
        return "Outcome::Parsed(Parsed { " + ", ".join(fields) + " })"
    return (
        f"Outcome::Exit {{ status: {outcome['status']}, "
        f"stdout: {rust_bytes(outcome['stdout'])}, "
        f"stderr: {rust_bytes(outcome['stderr'])} }}"
    )


def rust_case(program, arguments, columns):
    outcome = run_oracle(program, arguments, columns)
    return (
        f"    Case {{ program: {rust_bytes(program)}, "
        f"arguments: {rust_list(arguments)}, "
        f"columns: {rust_text(columns)}, "
        f"outcome: {rust_outcome(outcome)} }},"
    )


def cases():
    for program in PROGRAMS:
        for columns in WIDTHS:
            for arguments in VECTORS:
                yield program, arguments, columns
    for program, arguments in NAMED:
        for columns in WIDTHS:
            yield program, arguments, columns
    for columns in SIZED:
        for arguments in SIZED_VECTORS:
            yield PROGRAMS[0], arguments, columns


def write_vectors():
    lines = [rust_case(*case) for case in cases()]
    text = "\n".join(
        [
            "use super::{Case, Outcome, Parsed};",
            "",
            "#[rustfmt::skip]",
            "pub const CASES: &[Case] = &[",
            *lines,
            "];",
            "",
        ]
    )
    VECTORS_PATH.write_text(text, encoding="utf-8")
    return len(lines)


def decimal_zeros():
    zeros = []
    point = 0
    while point < CODE_POINTS:
        if not chr(point).isdecimal():
            point += 1
            continue
        block = [chr(point + offset) for offset in range(DIGITS_PER_BLOCK)]
        assert all(digit.isdecimal() for digit in block), hex(point)
        assert [int(digit) for digit in block] == list(range(10)), hex(point)
        zeros.append(point)
        point += DIGITS_PER_BLOCK
    return zeros


def spaces():
    found = [p for p in range(ASCII_END, CODE_POINTS) if chr(p).isspace()]
    assert all(int(f"1{chr(p)}") == 1 for p in found)
    return found


def not_printable_ranges():
    ranges = []
    for point in range(CODE_POINTS):
        if chr(point).isprintable():
            continue
        if ranges and ranges[-1][1] == point - 1:
            ranges[-1][1] = point
        else:
            ranges.append([point, point])
    return ranges


def rust_points(name, points):
    rows = [f"    0x{point:06x}," for point in points]
    return [
        "#[rustfmt::skip]",
        f"pub const {name}: [u32; {len(points)}] = [",
        *rows,
        "];",
    ]


def write_tables():
    ranges = not_printable_ranges()
    rows = [f"    (0x{first:06x}, 0x{last:06x})," for first, last in ranges]
    text = "\n".join(
        [
            *rust_points("DECIMAL_ZEROS", decimal_zeros()),
            "",
            *rust_points("SPACES_NOT_ASCII", spaces()),
            "",
            "#[rustfmt::skip]",
            f"pub const NOT_PRINTABLE: [(u32, u32); {len(ranges)}] = [",
            *rows,
            "];",
            "",
        ]
    )
    TABLES_PATH.write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args(argv)
    assert sys.version_info[:2] == (3, 14), sys.version
    write_tables()
    print(f"{write_vectors()} cases in {VECTORS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

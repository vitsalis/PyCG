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
  The vectors whose first argument is view run pycg.view.main under the
  program name followed by view, with pycg.view.read replaced by a stop.
- crates/pycg/tests/cli/view_vectors.rs: every case of DOCUMENTS, run by
  pycg.view.main in a directory of its own, with the exit status and the
  file the page went to with the document block of the page.
- crates/pycg/src/unicode.rs: the characters that str.isdecimal, int(),
  str.isspace and str.isprintable accept.

    python3 -I tools/parity/cli.py
"""

ROOT = Path(__file__).resolve().parents[2]
VECTORS_PATH = ROOT / "crates" / "pycg" / "tests" / "cli" / "vectors.rs"
VIEW_VECTORS_PATH = ROOT / "crates" / "pycg" / "tests" / "cli" / "view_vectors.rs"
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
    ("views", "a.py"),
    ("a.py", "view"),
    ("--", "view"),
    ("view",),
    ("view", "d.json"),
    ("view", "-h"),
    ("view", "--help"),
    ("view", "-o"),
    ("view", "--output"),
    ("view", "-o", "x.html", "d.json"),
    ("view", "d.json", "-o", "x.html"),
    ("view", "d.json", "-o", "a", "-o", "b"),
    ("view", "d.json", "e.json"),
    ("view", "--", "-h"),
    ("view", "--", "--", "x"),
    ("view", "d.json", "--"),
    ("view", "d.json", "--", "e.json"),
    ("view", "-oout.html", "d.json"),
    ("view", "--out=o.html", "d.json"),
    ("view", "--o", "o.html", "d.json"),
    ("view", "-o=", "d.json"),
    ("view", "-o", "", "d.json"),
    ("view", "-x"),
    ("view", "-x", "d.json"),
    ("view", "--package", "p", "d.json"),
    ("view", "--cap", "5", "d.json"),
    ("view", "-", "d.json"),
    ("view", "-1"),
    ("view", "-h", "-o"),
    ("view", "d.json", "-h"),
    ("view", "-ho"),
    ("view", "-oh", "d.json"),
    ("view", "--he"),
    ("view", "--h"),
    ("view", "view"),
    ("view", "view", "d.json"),
    (b"view", b"d\xff.json"),
)
NAMED = (
    (LONG_PROGRAM, ("--foo",)),
    (LONG_PROGRAM, ("-h",)),
    (b"/bin/py\xffcg", ("--foo",)),
    (b"/bin/py\xffcg", ("-h",)),
    (b"pycg\n\n\n", ("--foo",)),
    (b"", ("-h",)),
    (LONG_PROGRAM, ("view", "--foo")),
    (LONG_PROGRAM, ("view", "-h")),
    (b"pycg\n\n\n", ("view", "--foo")),
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


VIEW_ORACLE = f"""\
import argparse
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
sys.argv = sys.argv[2:]

import pycg.view as view

prog = os.path.basename(sys.argv[0]) + " view"
parsed = []
init = argparse.ArgumentParser.__init__
parse_args = argparse.ArgumentParser.parse_args


def named(parser, *arguments, **keywords):
    keywords["prog"] = prog
    init(parser, *arguments, **keywords)


def record(parser, *arguments, **keywords):
    namespace = parse_args(parser, *arguments, **keywords)
    parsed.append(namespace)
    return namespace


class Analysed(Exception):
    pass


def read(path):
    raise Analysed


argparse.ArgumentParser.__init__ = named
argparse.ArgumentParser.parse_args = record
view.read = read
try:
    view.main(sys.argv[2:])
except Analysed:
    sys.stdout.write(json.dumps(vars(parsed[0])))
    sys.exit({ANALYSED_STATUS})
"""
DOCUMENT_ORACLE = """\
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])

import pycg.view as view

head, tail = view.template().split(view.MARKER)
results = []
for case in json.load(sys.stdin):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        inputs = {}
        for name, data in case["files"]:
            path = root / os.fsdecode(bytes.fromhex(name))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bytes.fromhex(data))
            inputs[path] = bytes.fromhex(data)
        os.chdir(directory)
        hexes = case["arguments"]
        arguments = [os.fsdecode(bytes.fromhex(argument)) for argument in hexes]
        try:
            view.main(arguments)
            status = 0
        except SystemExit as stop:
            assert isinstance(stop.code, str), stop.code
            status = 1
        except ValueError as error:
            assert "has an empty name" in str(error), error
            status = 1
        os.chdir("/")
        written = []
        for path in sorted(root.rglob("*")):
            if path.is_file() and inputs.get(path) != path.read_bytes():
                page = path.read_bytes().decode("utf-8")
                assert page.startswith(head) and page.endswith(tail), path
                block = page[len(head) : len(page) - len(tail)]
                name = os.fsencode(path.relative_to(root))
                written.append([name.hex(), block.encode("utf-8").hex()])
        assert len(written) <= 1, written
        assert (status == 0) == bool(written), (case, status, written)
        results.append({"status": status, "written": written})
json.dump(results, sys.stdout)
"""
MINIMAL = (
    '{"calls":{},"definitions":{},"exports":{},"format":"pycg/1",'
    '"modules":{},"outside":{},"package":{"name":null,"version":null},'
    '"tool":{"name":"pycg","typeshed":"abc","version":"1.0.0"}}'
)


def document_with(**parts):
    document = json.loads(MINIMAL)
    document.update(parts)
    return json.dumps(document)


def minimal_with(old, new):
    assert MINIMAL.count(old) == 1, old
    return MINIMAL.replace(old, new)


DOCUMENT_TEXTS = (
    MINIMAL,
    json.dumps(json.loads(MINIMAL), indent=2).replace("\n", "\r\n"),
    minimal_with('"format"', '"\\u0066ormat"'),
    minimal_with('"format":"pycg/1"', '"format":"pycg\\/1"'),
    minimal_with('"format":"pycg/1"', '"format":"pycg/2","format":"pycg/1"'),
    minimal_with('"format":"pycg/1"', '"format":"pycg/1","format":"pycg/2"'),
    minimal_with('"calls":{}', '"calls":[],"calls":{}'),
    minimal_with('"calls":{}', '"calls":{},"calls":[]'),
    minimal_with('"exports":{}', '"exports":{"a":"\\ud800","b":"\\ud83d\\ude00"}'),
    minimal_with('"exports":{}', '"exports":{"\\udc00\\ud800x":"\\ud800\\u0041"}'),
    minimal_with('"exports":{}', '"exports":{"n":[1e400,-0,1E+5,0.5e-3,-1.25]}'),
    minimal_with('"exports":{}', '"exports":' + "[" * 200 + "]" * 200),
    minimal_with('"exports":{}', '"exports":{"s":"</script><!--<script>é名"}'),
    minimal_with(
        '"exports":{}',
        '"exports":{"t":true,"f":false,"z":null,"e":"\\b\\f\\n\\r\\t\\"\\\\"}',
    ),
    minimal_with('"exports":{}', '"exports":{"x":NaN}'),
    minimal_with('"exports":{}', '"exports":[Infinity]'),
    minimal_with('"exports":{}', '"exports":[-Infinity]'),
    minimal_with('"exports":{}', '"exports":[-Inf]'),
    minimal_with('"exports":{}', '"exports":[1,]'),
    minimal_with('"exports":{}', '"exports":{"a":1,}'),
    minimal_with('"exports":{}', '"exports":{"a" 1}'),
    minimal_with('"exports":{}', '"exports":{"a":1 "b":2}'),
    minimal_with('"exports":{}', '"exports":[1 2]'),
    minimal_with('"exports":{}', '"exports":{1:2}'),
    minimal_with('"exports":{}', '"exports":"a\x01b"'),
    minimal_with('"exports":{}', '"exports":"a\x7fb"'),
    minimal_with('"exports":{}', '"exports":"\\x"'),
    minimal_with('"exports":{}', '"exports":"\\u12g4"'),
    minimal_with('"exports":{}', '"exports":"\\ud800\\u12g4"'),
    minimal_with('"exports":{}', '"exports":[01]'),
    minimal_with('"exports":{}', '"exports":[1.]'),
    minimal_with('"exports":{}', '"exports":[1e]'),
    minimal_with('"exports":{}', '"exports":[-]'),
    minimal_with('"exports":{}', '"exports":[tru]'),
    minimal_with('"exports":{}', '"exports":[nullx]'),
    MINIMAL + " \t\r\n",
    " \n" + MINIMAL,
    MINIMAL + "x",
    MINIMAL + "{}",
    "\ufeff" + MINIMAL,
    MINIMAL[:-1],
    MINIMAL[:40],
    '"unterminated',
    "",
    "   ",
    "not json",
    "[]",
    '"pycg/1"',
    "null",
    "1",
    "{}",
    '{"node":["callee"]}',
    minimal_with('"format":"pycg/1"', '"format":"pycg/2"'),
    minimal_with('"format":"pycg/1"', '"format":1'),
    minimal_with('"format":"pycg/1"', '"format":null'),
    minimal_with('"format":"pycg/1"', '"format":["pycg/1"]'),
    minimal_with('"format":"pycg/1"', '"format":"PYCG/1"'),
    minimal_with('"calls":{},', ""),
    minimal_with('"calls":{}', '"calls":[]'),
    minimal_with('"calls":{}', '"calls":null'),
    minimal_with('"calls":{}', '"calls":"x"'),
    minimal_with(',"tool":{"name":"pycg","typeshed":"abc","version":"1.0.0"}', ""),
    minimal_with('"package":{"name":null,"version":null}', '"package":1'),
    minimal_with('"modules":{},', ""),
    minimal_with('"definitions":{},', ""),
    minimal_with('"exports":{},', ""),
    minimal_with('"outside":{},', ""),
    document_with(package={"name": "</script>", "version": "<!--"}),
)
DOCUMENT_BYTES = (
    MINIMAL.encode("utf-8").replace(b'"abc"', b'"\xff"'),
    MINIMAL.encode("utf-8").replace(b'"abc"', b'"\xed\xa0\x80"'),
    MINIMAL.encode("utf-8").replace(b'"abc"', b'"\xc3"'),
    MINIMAL.encode("utf-16"),
)
PATHS = (
    ("d.json", ()),
    ("d", ()),
    (".d", ()),
    ("d.", ()),
    ("d..", ()),
    ("..d", ()),
    ("...json", ()),
    ("d.tar.gz", ()),
    ("d.json.", ()),
    ("d. b", ()),
    ("d.html", ()),
    ("d.HTML", ()),
    ("d.html", ("-o", "out.html")),
    ("d.json", ("-o", "out.html")),
    ("d.json", ("-o", "")),
    ("d.json", ("-o", "d.json")),
    ("sub/d.json", ()),
    ("sub/d.json", ("-o", "sub/x.html")),
    ("sub/d.json", ("-o", "missing/x.html")),
    ("sub/d.json", ("-o", "sub")),
)
PATH_ARGUMENTS = (
    ("./d.json",),
    ("sub//d.json",),
    ("sub/./d.json",),
    ("sub/../sub/d.json",),
    ("sub/.",),
    ("sub",),
    (".",),
    ("missing.json",),
    ("missing.json", "-o", "x.html"),
)


def document_cases():
    for text in DOCUMENT_TEXTS:
        yield [("d.json", text.encode("utf-8"))], ("d.json",)
    for data in DOCUMENT_BYTES:
        yield [("d.json", data)], ("d.json",)
    for name, options in PATHS:
        yield [(name, MINIMAL.encode("utf-8"))], (name, *options)
    for arguments in PATH_ARGUMENTS:
        yield [("sub/d.json", MINIMAL.encode("utf-8"))], arguments


def run_document_oracle(cases):
    request = [
        {
            "files": [[encoded(name).hex(), data.hex()] for name, data in files],
            "arguments": [encoded(argument).hex() for argument in arguments],
        }
        for files, arguments in cases
    ]
    completed = subprocess.run(
        [sys.executable, "-I", "-c", DOCUMENT_ORACLE, str(ROOT)],
        input=json.dumps(request).encode("utf-8"),
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def rust_files(files):
    pairs = [
        f"({rust_bytes(encoded(name))}, {rust_bytes(data)})" for name, data in files
    ]
    return "&[" + ", ".join(pairs) + "]"


def rust_document_case(case, result):
    files, arguments = case
    if result["written"]:
        [[name, block]] = result["written"]
        written = (
            f"Some(({rust_bytes(bytes.fromhex(name))}, "
            f"{rust_bytes(bytes.fromhex(block))}))"
        )
    else:
        written = "None"
    return (
        f"    DocumentCase {{ files: {rust_files(files)}, "
        f"arguments: {rust_list(arguments)}, "
        f"status: {result['status']}, written: {written} }},"
    )


def write_view_vectors():
    cases = list(document_cases())
    results = run_document_oracle(cases)
    lines = [rust_document_case(case, result) for case, result in zip(cases, results)]
    text = "\n".join(
        [
            "use super::DocumentCase;",
            "",
            "#[rustfmt::skip]",
            "pub const DOCUMENT_CASES: &[DocumentCase] = &[",
            *lines,
            "];",
            "",
        ]
    )
    VIEW_VECTORS_PATH.write_text(text, encoding="utf-8")
    return len(lines)


def encoded(text):
    return text if isinstance(text, bytes) else os.fsencode(text)


def run_oracle(program, arguments, columns):
    environment = dict(os.environ)
    environment.pop("COLUMNS", None)
    environment.pop("LINES", None)
    if columns is not None:
        environment["COLUMNS"] = columns
    viewing = bool(arguments) and encoded(arguments[0]) == b"view"
    oracle = VIEW_ORACLE if viewing else ORACLE
    command = [sys.executable, "-I", "-c", oracle, str(ROOT), program]
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
    if "parsed" in outcome and "document" in outcome["parsed"]:
        namespace = outcome["parsed"]
        fields = [
            f"document: {rust_bytes(encoded(namespace['document']))}",
            f"output: {rust_text(namespace['output'])}",
        ]
        return "Outcome::Viewed(Viewed { " + ", ".join(fields) + " })"
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
            "use super::{Case, Outcome, Parsed, Viewed};",
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
    count = write_view_vectors()
    print(f"{count} cases in {VIEW_VECTORS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

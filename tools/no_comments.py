import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

DESCRIPTION = """\
Fails on a comment or a docstring in the repository's own code: the Python
and shell files of SCANNED_DIRECTORIES, but the analysed programs and the
data of NOT_SCANNED_DIRECTORIES. Allowed: a shebang, an encoding line, the
licence header block at the top of a file, and the pragmas that tools read
(TOOL_PRAGMA_PREFIXES). Prints one line per finding, `path:line: text`.
"""

ROOT = Path(__file__).resolve().parents[1]
SCANNED_DIRECTORIES = ("pycg/", "tests/", "tools/", "evaluation/")
NOT_SCANNED_DIRECTORIES = (
    "evaluation/micro-benchmark/snippets/",
    "evaluation/macro-benchmark/projects/",
    "evaluation/macro-benchmark/selection/",
    "tests/fixtures/",
)
SCANNED_SUFFIXES = (".py", ".sh")
TOOL_PRAGMA_PREFIXES = (
    "# noqa",
    "# type:",
    "# pragma",
    "# fmt:",
    "# ruff:",
    "# shellcheck ",
)
LICENCE_MARKERS = ("Copyright", "SPDX-License-Identifier", "Licensed under")
ENCODING_LINE = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+")
DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def is_tool_pragma(comment):
    return comment.startswith(TOOL_PRAGMA_PREFIXES)


def allowed_header_lines(lines):
    allowed = set()
    number = 1
    if lines and lines[0].startswith("#!"):
        allowed.add(1)
        number = 2
    for candidate in (number, number + 1):
        if candidate <= len(lines) and ENCODING_LINE.match(lines[candidate - 1]):
            allowed.add(candidate)
            number = candidate + 1
    header = []
    while number <= len(lines) and lines[number - 1].lstrip().startswith("#"):
        header.append(number)
        number += 1
    header_text = "\n".join(lines[n - 1] for n in header)
    if any(marker in header_text for marker in LICENCE_MARKERS):
        allowed.update(header)
    return allowed


def python_findings(text):
    lines = text.splitlines()
    allowed = allowed_header_lines(lines)
    findings = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type != tokenize.COMMENT:
            continue
        line_number = token.start[0]
        if line_number in allowed or is_tool_pragma(token.string):
            continue
        findings.append((line_number, token.string))
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, DOCSTRING_OWNERS) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            summary = first.value.value.strip().splitlines()[:1]
            findings.append((first.lineno, f"docstring: {''.join(summary)}"))
    return sorted(findings)


def shell_comment_start(line):
    quote = None
    parameter_depth = 0
    previous = " "
    for index, character in enumerate(line):
        if quote:
            if character == quote and previous != "\\":
                quote = None
        elif character in "'\"" and previous != "\\":
            quote = character
        elif character == "{" and previous == "$":
            parameter_depth += 1
        elif character == "}" and parameter_depth:
            parameter_depth -= 1
        elif character == "#" and not parameter_depth and previous.isspace():
            return index
        previous = character
    return None


def shell_findings(text):
    lines = text.splitlines()
    allowed = allowed_header_lines(lines)
    findings = []
    for line_number, line in enumerate(lines, 1):
        start = shell_comment_start(line)
        if start is None or line_number in allowed:
            continue
        comment = line[start:]
        if not is_tool_pragma(comment):
            findings.append((line_number, comment))
    return findings


def scanned_paths(root):
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others"]
        + ["--exclude-standard", "--", *SCANNED_DIRECTORIES],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [
        path
        for path in sorted(set(listing))
        if path.endswith(SCANNED_SUFFIXES)
        and not path.startswith(NOT_SCANNED_DIRECTORIES)
        and (root / path).is_file()
    ]


def findings_of(path, text):
    if path.endswith(".sh"):
        return shell_findings(text)
    return python_findings(text)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args(argv)
    count = 0
    for path in scanned_paths(ROOT):
        text = (ROOT / path).read_text(encoding="utf-8")
        for line_number, comment in findings_of(path, text):
            print(f"{path}:{line_number}: {comment}")
            count += 1
    if count:
        print(
            f"comments or docstrings found: {count}; names carry the meaning, "
            "the reasons go to docs/ and commit messages (AGENTS.md, Rules)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

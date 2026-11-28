import importlib.util
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

_spec = importlib.util.spec_from_file_location(
    "tools_no_comments",
    Path(__file__).resolve().parents[2] / "tools" / "no_comments.py",
)
no_comments = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(no_comments)

APACHE_HEADER = """\
# Copyright (c) 2026 Vitalis Salis.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""


def lines_found(path, text):
    return [line for line, _ in no_comments.findings_of(path, dedent(text))]


def test_a_comment_in_python_fails():
    assert lines_found("a.py", "x = 1\n# why x is one\ny = 2  # and y\n") == [2, 3]


def test_a_docstring_of_a_module_class_or_function_fails():
    text = '''
        """The module."""

        class C:
            """The class."""

            def f(self):
                """The method."""
                return "not a docstring"
    '''
    assert lines_found("a.py", text) == [2, 5, 8]


@pytest.mark.parametrize(
    "pragma",
    [
        "# noqa: E501",
        "# type: ignore",
        "# pragma: no cover",
        "# fmt: off",
        "# ruff: noqa",
    ],
)
def test_a_tool_pragma_passes(pragma):
    assert lines_found("a.py", f"x = 1  {pragma}\n") == []


def test_a_licence_header_a_shebang_and_an_encoding_line_pass():
    text = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n" + APACHE_HEADER
    assert lines_found("a.py", text + "\nx = 1\n") == []


def test_a_comment_block_at_the_top_without_a_licence_fails():
    assert lines_found("a.py", "# the plan\n# of this module\nx = 1\n") == [1, 2]


def test_a_comment_after_the_licence_header_fails():
    text = APACHE_HEADER + "\n# a note\nx = 1\n"
    assert lines_found("a.py", text) == [6]


def test_a_hash_inside_a_python_string_is_data():
    assert lines_found("a.py", 'SOURCE = "x = 1  # analysed"\n') == []


def test_a_comment_in_a_shell_script_fails():
    text = "#!/bin/sh\n# what it does\nset -eu  # strict\n"
    assert lines_found("a.sh", text) == [2, 3]


def test_shell_syntax_with_a_hash_is_not_a_comment():
    text = """\
        #!/bin/sh
        [ $# -eq 2 ] || exit 2
        printf '%s\\n' "${line# }"
        echo "a # b" 'c # d' a#b
        # shellcheck disable=SC2016
        prefix='$PATH'
    """
    assert lines_found("a.sh", text) == []


def test_only_the_code_of_the_repository_is_scanned(tmp_path):
    files = {
        "crates/a/src/lib.rs": "fn f() {}\n",
        "tools/b.sh": "#!/bin/sh\n",
        "tests/triage.py": "x = 1\n",
        "evaluation/micro-benchmark/snippets/c/d/main.py": "# analysed\n",
        "evaluation/macro-benchmark/selection/e.py": "# evidence\n",
        "tools/tests/fixtures/f.py": "# analysed\n",
        "tests/cases/g/h/program/main.py": "# analysed\n",
        "crates/pycg/tests/termination/i/main.py": "# analysed\n",
        "crates/syntax/tests/vectors/d1/j.py": "# analysed\n",
        "docs/k.py": "# not scanned\n",
        "crates/a/l.json": "{}\n",
    }
    for relative, text in files.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert no_comments.scanned_paths(tmp_path) == [
        "crates/a/src/lib.rs",
        "tests/triage.py",
        "tools/b.sh",
    ]


def test_a_comment_in_rust_fails():
    text = """\
        /// what f does
        fn f() {}
        //! the module
        let x = 1; // why
        /* a /* nested */ block
        over lines */
        let y = 2;
    """
    assert lines_found("a.rs", text) == [1, 3, 4, 5]


@pytest.mark.parametrize(
    "text",
    [
        'let url = "https://example.org"; let s = "a\\\\" ;\n',
        'let quote = "a \\" // b";\n',
        'let raw = r#"// "quoted" /* */"#;\n',
        'let bytes = br"//";\n',
        "let c = '\"'; let d = '\\''; let e = '/';\n",
        "fn f<'a>(x: &'a str) -> &'a str { x }\n",
        "let slash = 4 / 2; let star = 2 * 3;\n",
        "let r = for_each; let b = 1;\n",
    ],
)
def test_rust_without_a_comment_passes(text):
    assert lines_found("a.rs", text) == []

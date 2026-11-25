import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from pycg import view

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = Path(__file__).resolve().parent / "data" / "view" / "sample.json"
BLOCK = re.compile(
    r'<script type="application/json" id="pycg-document">(.*?)</script>', re.S
)

HOSTILE = [
    "</script><script>alert(1)</script>",
    "</SCRIPT >",
    "<!--<script>",
    "<script>",
    "-->",
    "]]>",
    "<\\/script>",
    "&lt;b&gt;",
    "\"'`",
    "  ",
    "constructor",
    "__proto__",
    "toString",
    "ünïcödé.名前",
]


def document(**parts):
    base = {
        "format": "pycg/1",
        "tool": {"name": "pycg", "version": "1.0.0", "typeshed": "abc"},
        "package": {"name": None, "version": None},
        "modules": {},
        "definitions": {},
        "exports": {},
        "outside": {},
        "calls": {},
    }
    base.update(parts)
    return base


def hostile_document():
    modules = {}
    definitions = {}
    outside = {}
    calls = {}
    for i, text in enumerate(HOSTILE):
        module = f"m{i}.{text}"
        modules[module] = {"file": f"{text}.py", "kind": "source", "status": "analysed"}
        definitions[module] = {"kind": "module", "module": module, "lines": [1, 2]}
        outside[f"x.{text}"] = {"known": "name"}
        calls[module] = [
            {"line": 1, "col": 0, "end": [1, 4], "callees": [f"x.{text}"]},
            {"line": 2, "col": 0, "end": [2, 4], "callees": [], "unresolved": text},
        ]
    modules["broken"] = {
        "file": "broken.py",
        "kind": "source",
        "status": "failed",
        "cause": HOSTILE[0],
    }
    return document(
        package={"name": HOSTILE[0], "version": HOSTILE[2]},
        modules=modules,
        definitions=definitions,
        outside=outside,
        calls=calls,
    )


def write_json(path, value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return text


def embedded(html):
    blocks = BLOCK.findall(html)
    assert len(blocks) == 1
    return blocks[0]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "pycg.view", *map(str, args)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_writes_the_page_to_the_output_path(tmp_path):
    source = tmp_path / "graph.json"
    source.write_bytes(SAMPLE.read_bytes())
    output = tmp_path / "page.html"
    result = run_cli(source, "-o", output)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert embedded(output.read_text(encoding="utf-8")).startswith("{")


def test_writes_next_to_the_input_without_an_output_path(tmp_path):
    source = tmp_path / "graph.json"
    source.write_bytes(SAMPLE.read_bytes())
    assert view.main([str(source)]) is None
    assert (tmp_path / "graph.html").is_file()


def test_default_output_of_a_file_without_suffix(tmp_path):
    source = tmp_path / "graph"
    source.write_bytes(SAMPLE.read_bytes())
    view.main([str(source)])
    assert (tmp_path / "graph.html").is_file()


def test_refuses_to_overwrite_the_input(tmp_path):
    source = tmp_path / "graph.html"
    original = SAMPLE.read_bytes()
    source.write_bytes(original)
    with pytest.raises(SystemExit) as exit:
        view.main([str(source)])
    assert exit.value.code != 0
    assert "would overwrite the input" in str(exit.value.code)
    assert source.read_bytes() == original


def test_refuses_an_unknown_format_version(tmp_path):
    source = tmp_path / "graph.json"
    write_json(source, document(format="pycg/2"))
    result = run_cli(source)
    assert result.returncode == 1
    assert "pycg/2" in result.stderr
    assert "pycg/1" in result.stderr
    assert not (tmp_path / "graph.html").exists()


def test_refuses_a_document_without_format(tmp_path):
    source = tmp_path / "graph.json"
    write_json(source, {"node": ["callee"]})
    result = run_cli(source)
    assert result.returncode == 1
    assert "no 'format'" in result.stderr


@pytest.mark.parametrize(
    "text",
    ["", "{", "not json", '{"format": "pycg/1",}', "\ufeff{}"],
    ids=["empty", "truncated", "text", "trailing comma", "byte order mark"],
)
def test_refuses_a_file_that_is_not_json(tmp_path, text):
    source = tmp_path / "graph.json"
    source.write_text(text, encoding="utf-8")
    result = run_cli(source)
    assert result.returncode == 1
    assert "is not JSON" in result.stderr
    assert "Traceback" not in result.stderr


def test_refuses_a_file_that_is_not_utf8(tmp_path):
    source = tmp_path / "graph.json"
    source.write_bytes(b'{"format": "\xff"}')
    result = run_cli(source)
    assert result.returncode == 1
    assert "UTF-8" in result.stderr


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_refuses_numbers_that_javascript_cannot_read(tmp_path, constant):
    source = tmp_path / "graph.json"
    text = json.dumps(document()).replace(
        '"version": null}', f'"version": {constant}}}'
    )
    assert constant in text
    source.write_text(text, encoding="utf-8")
    result = run_cli(source)
    assert result.returncode == 1
    assert constant in result.stderr


@pytest.mark.parametrize(
    "value",
    [[], "pycg/1", None],
    ids=["list", "string", "null"],
)
def test_refuses_a_document_that_is_not_an_object(tmp_path, value):
    source = tmp_path / "graph.json"
    write_json(source, value)
    result = run_cli(source)
    assert result.returncode == 1
    assert "not a JSON object" in result.stderr


@pytest.mark.parametrize(
    "part", ["tool", "package", "modules", "definitions", "exports", "outside", "calls"]
)
def test_refuses_a_document_with_a_missing_part(tmp_path, part):
    source = tmp_path / "graph.json"
    value = document()
    del value[part]
    write_json(source, value)
    result = run_cli(source)
    assert result.returncode == 1
    assert f"'{part}'" in result.stderr


def test_refuses_a_part_that_is_not_an_object(tmp_path):
    source = tmp_path / "graph.json"
    write_json(source, document(calls=[]))
    result = run_cli(source)
    assert result.returncode == 1
    assert "'calls'" in result.stderr


def test_reports_a_missing_file(tmp_path):
    result = run_cli(tmp_path / "missing.json")
    assert result.returncode == 1
    assert "missing.json" in result.stderr
    assert "Traceback" not in result.stderr


def test_reports_an_output_path_that_cannot_be_written(tmp_path):
    source = tmp_path / "graph.json"
    source.write_bytes(SAMPLE.read_bytes())
    result = run_cli(source, "-o", tmp_path / "no" / "such" / "dir.html")
    assert result.returncode == 1
    assert "dir.html" in result.stderr
    assert "Traceback" not in result.stderr


def test_console_script_runs_the_viewer():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = project["project"]["scripts"]
    assert scripts["pycg-view"] == "pycg.view:main"
    assert scripts["pycg"] == "pycg.__main__:main"


def test_page_holds_the_document_byte_for_byte(tmp_path):
    for source_text in [SAMPLE.read_text(encoding="utf-8"), json.dumps(document())]:
        html = view.render(source_text)
        block = embedded(html)
        assert block.replace("\\u003c", "<") == source_text
        assert json.loads(block) == json.loads(source_text)


def test_page_is_the_template_with_the_document_in_its_block():
    text = SAMPLE.read_text(encoding="utf-8")
    html = view.render(text)
    assert html.replace(embedded(html), view.MARKER, 1) == view.template()


def test_no_name_can_end_the_document_block(tmp_path):
    source = tmp_path / "graph.json"
    text = write_json(source, hostile_document())
    output = tmp_path / "graph.html"
    view.main([str(source), "-o", str(output)])
    html = output.read_text(encoding="utf-8")
    block = embedded(html)
    assert "<" not in block
    assert json.loads(block) == json.loads(text)
    assert block.replace("\\u003c", "<") == text
    template = view.template()
    for tag in ("<script", "</script", "<!--"):
        assert html.lower().count(tag) == template.lower().count(tag)


def test_page_bytes_are_utf8_without_newline_translation(tmp_path):
    source = tmp_path / "graph.json"
    text = write_json(source, hostile_document())
    output = tmp_path / "graph.html"
    view.main([str(source), "-o", str(output)])
    raw = output.read_bytes()
    assert text.replace("<", "\\u003c").encode("utf-8") in raw
    assert b"\r\n" not in raw


def test_template_has_exactly_one_document_marker():
    assert view.template().count(view.MARKER) == 1


FORBIDDEN = {
    "an absolute URL": r"\b(?:https?|ftp|file|wss?)://|\b(?:data|blob):[\w-]+[/:]",
    "a protocol-relative URL": r"""["'`(=]\s*//""",
    "an attribute that loads a file": r"\b(?:src|href|action|srcset|poster)\s*=",
    "a property that loads a file": r"\.(?:src|href|action)\b",
    "a CSS resource": r"url\(|@import",
    "a module import": r"\bimport\b",
    "a network request": r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\b",
    "a beacon": r"sendBeacon",
    "a worker": r"\b(?:Worker|importScripts)\b",
    "a navigation away": r"location\.(?:assign|replace|reload)|window\.open",
    "an element that loads a file": r"<(?:link|iframe|img|object|embed|base|frame)\b",
    "HTML parsing of text": r"innerHTML|outerHTML|insertAdjacentHTML|document\.write",
    "code built from text": r"\beval\b|new Function|setTimeout\(\s*['\"`]",
}


@pytest.mark.parametrize("what", FORBIDDEN)
def test_template_has_no(what):
    matches = re.findall(FORBIDDEN[what], view.template())
    assert matches == [], f"the template has {what}: {matches}"


def test_template_forbids_every_request():
    policy = re.search(
        r'<meta http-equiv="Content-Security-Policy" content="([^"]*)">',
        view.template(),
    )
    assert policy is not None
    directives = [part.strip() for part in policy.group(1).split(";")]
    assert "default-src 'none'" in directives

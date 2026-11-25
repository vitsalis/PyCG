import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from pycg.formats import FORMAT

DOCUMENT_PARTS = (
    "tool",
    "package",
    "modules",
    "definitions",
    "exports",
    "outside",
    "calls",
)
MARKER = "@@PYCG_DOCUMENT@@"


class DocumentError(Exception):
    pass


def template():
    return resources.files(__name__).joinpath("template.html").read_text("utf-8")


def check_document(text):
    def refuse_constant(name):
        raise DocumentError(f"is not JSON that a browser reads: it has {name}")

    try:
        document = json.loads(text, parse_constant=refuse_constant)
    except json.JSONDecodeError as error:
        raise DocumentError(f"is not JSON: {error}") from None
    if not isinstance(document, dict):
        raise DocumentError("is not a JSON object")
    if "format" not in document:
        raise DocumentError("has no 'format': it is not a PyCG call graph document")
    if document["format"] != FORMAT:
        raise DocumentError(
            f"has format {document['format']!r}; this viewer reads {FORMAT!r}"
        )
    for part in DOCUMENT_PARTS:
        if not isinstance(document.get(part), dict):
            raise DocumentError(f"has no object {part!r}")


def render(text):
    head, tail = template().split(MARKER)
    text_script_safe = text.replace("<", "\\u003c")
    return head + text_script_safe + tail


def read(path):
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        raise DocumentError(f"cannot be read: {error.strerror}") from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise DocumentError("is not UTF-8 text") from None
    check_document(text)
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pycg-view",
        description="Write a PyCG call graph document as one HTML page.",
    )
    parser.add_argument("document", help="call graph document (JSON) written by pycg")
    parser.add_argument(
        "-o",
        "--output",
        help="HTML file to write (default: the document's path with .html)",
    )
    arguments = parser.parse_args(argv)
    source = Path(arguments.document)
    output = Path(arguments.output) if arguments.output else source.with_suffix(".html")
    if not arguments.output and output == source:
        sys.exit(f"pycg-view: {output} would overwrite the input; give -o")
    try:
        page = render(read(source))
    except DocumentError as error:
        sys.exit(f"pycg-view: {source} {error}")
    try:
        output.write_text(page, encoding="utf-8", newline="")
    except OSError as error:
        sys.exit(f"pycg-view: cannot write {output}: {error.strerror}")

"""Write a call graph document as one self-contained HTML page.

    pycg-view graph.json [-o graph.html]

The page is `template.html` with the document in its JSON block. The page
needs no server and makes no network request; its script does the rest.
"""

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from pycg.formats import FORMAT

PARTS = ("tool", "package", "modules", "definitions", "exports", "outside", "calls")
MARKER = "@@PYCG_DOCUMENT@@"


class DocumentError(Exception):
    """The input is not a call graph document that this viewer reads."""


def template():
    return resources.files(__name__).joinpath("template.html").read_text("utf-8")


def check(text):
    """Raise `DocumentError` unless `text` is a document of the known format."""

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
    for part in PARTS:
        if not isinstance(document.get(part), dict):
            raise DocumentError(f"has no object {part!r}")


def render(text):
    """The page for the document `text`.

    The document goes into a `<script type="application/json">` block. A
    `<` in JSON is always inside a string, where `\\u003c` means the same
    character, so the block holds no `<` at all and no name can end it.
    """
    head, tail = template().split(MARKER)
    return head + text.replace("<", "\\u003c") + tail


def read(path):
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        raise DocumentError(f"cannot be read: {error.strerror}") from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise DocumentError("is not UTF-8 text") from None
    check(text)
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
    args = parser.parse_args(argv)
    source = Path(args.document)
    output = Path(args.output) if args.output else source.with_suffix(".html")
    if not args.output and output == source:
        sys.exit(f"pycg-view: {output} would overwrite the input; give -o")
    try:
        page = render(read(source))
    except DocumentError as error:
        sys.exit(f"pycg-view: {source} {error}")
    try:
        output.write_text(page, encoding="utf-8", newline="")
    except OSError as error:
        sys.exit(f"pycg-view: cannot write {output}: {error.strerror}")

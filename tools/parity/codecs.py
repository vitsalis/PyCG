import argparse
import encodings
import encodings.aliases
import importlib
import pkgutil
import sys
from pathlib import Path

DESCRIPTION = """\
Writes the codec data that pycg-syntax reads a source file with: the
aliases of encodings.aliases, each module of the encodings package that
is a codec with how it decodes (utf-8, utf-8-sig, ascii, latin-1, a
charmap table, or unsupported), and the decoding table of each charmap
codec, one code point per byte or '-' where the byte is undefined. Run it
with the Python of the oracle; the output is committed.
"""

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "crates" / "syntax" / "data" / "codecs.txt"
BUILTIN = {
    "utf_8": "utf-8",
    "utf_8_sig": "utf-8-sig",
    "ascii": "ascii",
    "latin_1": "latin-1",
}
UNDEFINED = "\ufffe"


def codec_modules():
    found = {}
    for info in sorted(pkgutil.iter_modules(encodings.__path__), key=lambda m: m.name):
        try:
            module = importlib.import_module(f"encodings.{info.name}")
        except ImportError:
            continue
        if not hasattr(module, "getregentry"):
            continue
        if info.name in BUILTIN:
            found[info.name] = (BUILTIN[info.name], None)
        elif hasattr(module, "decoding_table"):
            found[info.name] = ("charmap", module.decoding_table)
        else:
            found[info.name] = ("unsupported", None)
    return found


def lines():
    yield f"python {sys.version.split()[0]}"
    for alias, module in sorted(encodings.aliases.aliases.items()):
        yield f"alias {alias} {module}"
    for name, (how, table) in codec_modules().items():
        yield f"module {name} {how}"
        if table is not None:
            assert len(table) == 256, name
            points = ("-" if c == UNDEFINED else f"{ord(c):x}" for c in table)
            yield f"table {name} {' '.join(points)}"


def main(argv):
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.parse_args(argv)
    OUT.write_text("".join(f"{line}\n" for line in lines()), encoding="ascii")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

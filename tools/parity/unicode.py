import argparse
import sys
import unicodedata
from pathlib import Path

DESCRIPTION = """\
Writes the Unicode data that pycg-syntax normalises identifiers with, as
CPython's parser does (NFKC), and tests identifiers with, as
str.isidentifier does: the full compatibility decomposition of each code
point that has one, the canonical combining class of each code point
whose class is not 0, the canonical compositions that NFC makes (the
Hangul syllables are composed and decomposed by their formula, not
listed), and the ranges of the code points that may start and continue
an identifier. Run it with the Python of the oracle; the output is
committed.
"""

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "crates" / "syntax" / "data" / "unicode.txt"
CODE_POINTS = 0x110000
HANGUL_SYLLABLES = range(0xAC00, 0xD7A4)
SURROGATES = range(0xD800, 0xE000)


def characters():
    for point in range(CODE_POINTS):
        if point not in SURROGATES and point not in HANGUL_SYLLABLES:
            yield point, chr(point)


def hexes(text):
    return " ".join(f"{ord(c):x}" for c in text)


def compositions():
    for point, character in characters():
        decomposition = unicodedata.decomposition(character)
        if not decomposition or decomposition.startswith("<"):
            continue
        parts = "".join(chr(int(part, 16)) for part in decomposition.split())
        if len(parts) == 2 and unicodedata.normalize("NFC", parts) == character:
            yield f"compose {hexes(parts)} {point:x}"


def ranges(test):
    start = None
    for point in range(CODE_POINTS + 1):
        inside = point < CODE_POINTS and point not in SURROGATES and test(chr(point))
        if inside and start is None:
            start = point
        elif not inside and start is not None:
            yield f"{start:x}-{point - 1:x}"
            start = None


def lines():
    yield f"unicode {unicodedata.unidata_version}"
    for point, character in characters():
        decomposed = unicodedata.normalize("NFKD", character)
        if decomposed != character:
            yield f"decompose {point:x} {hexes(decomposed)}"
    for point, character in characters():
        combining = unicodedata.combining(character)
        if combining:
            yield f"combining {point:x} {combining}"
    yield from compositions()
    yield "start " + " ".join(ranges(str.isidentifier))
    yield "continue " + " ".join(ranges(lambda c: ("a" + c).isidentifier()))


def main(argv):
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.parse_args(argv)
    OUT.write_text("".join(f"{line}\n" for line in lines()), encoding="ascii")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

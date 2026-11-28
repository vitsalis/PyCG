import argparse
import sys
from pathlib import Path

DESCRIPTION = """\
Writes crates/pycg/src/unicode.rs, the characters that the command line
reads as CPython 3.14 does: the zero of each block of ten decimal digits
that str.isdecimal and int() accept, the spaces beyond ASCII that
str.isspace accepts and int() strips, and the ranges of the characters
that str.isprintable rejects. Run it on CPython 3.14.10, the interpreter
that the syntax data pins; the output is committed.

    python3 -I tools/data/text.py
"""

ROOT = Path(__file__).resolve().parents[2]
TABLES_PATH = ROOT / "crates" / "pycg" / "src" / "unicode.rs"
CODE_POINTS = 0x110000
ASCII_END = 0x80
DIGITS_PER_BLOCK = 10


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


if __name__ == "__main__":
    main()

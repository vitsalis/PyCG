"""The command line: analyse a package and write its document
(docs/format.md)."""

import argparse

from pycg import formats
from pycg.analysis.solver import DEFAULT_CAP
from pycg.pycg import CallGraphGenerator


def cap(text):
    """The value of `--cap`: a positive integer, or `none`."""
    if text == "none":
        return None
    if text.isdecimal() and int(text) > 0:
        return int(text)
    raise argparse.ArgumentTypeError(f"{text!r} is not a positive integer or none")


def main():
    parser = argparse.ArgumentParser(
        description="Write the call graph of a Python package as one JSON document."
    )
    parser.add_argument("entry_point", nargs="*", help="Entry points to be processed")
    parser.add_argument(
        "--package",
        help=(
            "Package root: module names are relative to it and only modules "
            "under it are analysed. Default: the deepest directory that "
            "contains every entry point"
        ),
        default=None,
    )
    parser.add_argument(
        "--package-name", help="Name of the analysed package", default=None
    )
    parser.add_argument(
        "--package-version", help="Version of the analysed package", default=None
    )
    parser.add_argument("-o", "--output", help="Output path", default=None)
    parser.add_argument(
        "--cap",
        type=cap,
        metavar="N",
        default=DEFAULT_CAP,
        help=(
            "The most objects that the analysis keeps for one variable or "
            "expression: past it the value is treated as unknown, and calls "
            "through it are reported as unresolved (saturated). 'none' "
            "removes the cap: the analysis may then not finish, or run out "
            f"of memory, on large inputs. Default: {DEFAULT_CAP}"
        ),
    )

    args = parser.parse_args()

    cg = CallGraphGenerator(args.entry_point, args.package, args.cap)
    cg.analyze()
    text = formats.dumps(cg.document(args.package_name, args.package_version))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()

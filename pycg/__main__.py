import os
import sys
import json
import argparse

from pycg.pycg import CallGraphGenerator
from pycg import formats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("entry_point",
        nargs="*",
        help="Entry points to be processed")
    parser.add_argument(
        "--package",
        help="Package containing the code to be analyzed",
        default=None
    )
    parser.add_argument(
        "--fasten",
        help="Produce call graph using the FASTEN format",
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--product",
        help="Package name",
        default=""
    )
    parser.add_argument(
        "--forge",
        help="Source the product was downloaded from",
        default=""
    )
    parser.add_argument(
        "--version",
        help="Version of the product",
        default=""
    )
    parser.add_argument(
        "--timestamp",
        help="Timestamp of the package's version",
        default=0
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output path",
        default=None
    )

    args = parser.parse_args()

    cg = CallGraphGenerator(args.entry_point, args.package)
    cg.analyze()

    if args.fasten:
        formatter = formats.Fasten(cg, args.package, \
            args.product, args.forge, args.version, args.timestamp)
    else:
        formatter = formats.Simple(cg)

    if args.output:
        with open(args.output, "w+") as f:
            f.write(json.dumps(formatter.generate()))
    else:
        print (json.dumps(formatter.generate()))

if __name__ == "__main__":
    main()

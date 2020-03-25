import os
import sys
import json
import argparse

from pycg.pycg import CallGraphGenerator

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
        "--try-complete",
        help="Try to produce a complete call graph",
        action="store_true",
        default=False
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

    args = parser.parse_args()

    cg = CallGraphGenerator(args.entry_point, args.package)
    cg.analyze()

    output_cg = {}

    if args.fasten:
        output_cg["product"] = args.product
        output_cg["forge"] = args.forge
        output_cg["depset"] = []
        output_cg["version"] = args.version
        output_cg["timestamp"] = args.timestamp
        output_cg["cha"] = {}
        output_cg["graph"] = cg.output_edges()
    else:
        output = cg.output()
        for node in output:
            output_cg[node] = list(output[node])

    print (json.dumps(output_cg))

if __name__ == "__main__":
    main()

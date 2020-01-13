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

    args = parser.parse_args()

    cg = CallGraphGenerator(args.entry_point, args.package, args.try_complete)
    cg.analyze()
    output_cg = {}
    output = cg.output()
    for node in output:
        output_cg[node] = list(output[node])
    print (json.dumps(output_cg))

if __name__ == "__main__":
    main()

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

    args = parser.parse_args()

    cg = CallGraphGenerator(args.entry_point)
    cg.analyze()
    output_cg = {}
    output = cg.output()
    for node in output:
        output_cg[node] = list(output[node])
    print (json.dumps(output_cg))

if __name__ == "__main__":
    main()

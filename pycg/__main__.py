import os
import sys
import json

from pycg.pycg import CallGraphGenerator

def discover_entry(input_file):
    return os.path.join(input_file, "__main__.py")

def main():
    if len(sys.argv) < 2:
        print ("Usage: main.py <file_to_analyze>")
        sys.exit(1)

    input_file = input_pkg = sys.argv[1]

    if not input_file.endswith(".py"):
        input_pkg = os.path.abspath(input_file)
        input_file = os.path.abspath(discover_entry(input_file))

    cg = CallGraphGenerator(input_file, input_pkg)
    cg.analyze()
    output_cg = {}
    output = cg.output()
    for node in output:
        output_cg[node] = list(output[node])
    print (json.dumps(output_cg))

if __name__ == "__main__":
    main()

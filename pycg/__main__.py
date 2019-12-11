import sys
import json

from pycg.pycg import CallGraphGenerator

def main():
    if len(sys.argv) < 2:
        print ("Usage: main.py <file_to_analyze>")
        sys.exit(1)

    cg = CallGraphGenerator(sys.argv[1])
    cg.analyze()
    output_cg = {}
    output = cg.output()
    for node in output:
        output_cg[node] = list(output[node])
    print (json.dumps(output_cg))

if __name__ == "__main__":
    main()

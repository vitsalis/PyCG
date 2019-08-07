import sys

from pycg.prepycg import Visitor
from pycg.utils import to_mod_name

def main():
    if len(sys.argv) < 2:
        print ("Usage: main.py <file_to_analyze>")
        sys.exit(1)

    modname = to_mod_name(sys.argv[1]).split(".")[-1]
    visitor = Visitor(modname, sys.argv[1])
    visitor.analyze()
    print (visitor.output_call_graph())

if __name__ == "__main__":
    main()

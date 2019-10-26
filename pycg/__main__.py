import sys

from pycg.pycg import CallGraphGenerator

def main():
    if len(sys.argv) < 2:
        print ("Usage: main.py <file_to_analyze>")
        sys.exit(1)

    cg = CallGraphGenerator(sys.argv[1])
    print (cg.output())

if __name__ == "__main__":
    main()

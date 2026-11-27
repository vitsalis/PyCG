
import argparse
class Parser(argparse.ArgumentParser):
    def run(self): pass
def parsers():
    return LATE
subparsers = parsers().add_subparsers()
subparsers.add_parser("info").add_argument("x")
subparsers.add_parser("run", parents=[Parser()]).run()
LATE = argparse.ArgumentParser()

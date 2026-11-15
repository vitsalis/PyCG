import argparse

class Store(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

parser = argparse.ArgumentParser()
parser.add_argument("--name", action=Store)
parser.parse_args(["--name", "ann"])

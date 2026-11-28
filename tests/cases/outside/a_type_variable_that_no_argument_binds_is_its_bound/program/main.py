
import argparse
subparsers = argparse.ArgumentParser().add_subparsers()
subparsers.add_parser("info").add_argument("x")

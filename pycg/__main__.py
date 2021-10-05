import os
import sys
import json
import argparse

from pycg.pycg import CallGraphGenerator
from pycg import formats
from pycg.utils.constants import CALL_GRAPH_OP, KEY_ERR_OP, JSON_EXT
from pycg import utils

def parse_cmd_args():
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
    parser.add_argument(
        "--max-iter",
        type=int,
        help=("Maximum number of iterations through source code. " +
            "If not specified a fix-point iteration will be performed."),
        default=-1
    )
    parser.add_argument(
        '--operation',
        type=str,
        choices=[CALL_GRAPH_OP, KEY_ERR_OP],
        help=("Operation to perform. " +
             "Choose " + CALL_GRAPH_OP + " for call graph generation (default)" +
             " or " + KEY_ERR_OP + " for key error detection on dictionaries."),
        default=CALL_GRAPH_OP
    )

    parser.add_argument(
        "--as-graph-output",
        help="Output for the assignment graph",
        default=None
    )
    parser.add_argument(
        "--lineno",
        help="Produce line numbers graph of the code",
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--dir",
        help="Directory path containing independent code to be analyzed",
        default=None
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output path",
        default=None
    )

    args = parser.parse_args()
    return args

def prepare_lineno_output(args, cg):
    formatter = formats.LineNumber(cg)
    output_lg = formatter.generate()
    filename = os.path.splitext(os.path.basename(args.entry_point[0]))[0]
    if args.output:
        #TODO: Is there any better ways to generate multiple outputs
        output_dir = args.output + "_pycg"
        output_json = os.sep.join([output_dir, filename + JSON_EXT])
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        with open(output_json, "w+") as f:
            print("Generated data is in JSON file:", output_json)
            f.write(json.dumps(output_lg))
    else:
        print("Analysing result is:\n", json.dumps(output_lg))

#TODO: Add properly passed args and relatively the output results
def prepare_output(args, cg):
    if args.operation == CALL_GRAPH_OP:
        if args.fasten:
            formatter = formats.Fasten(cg, args.package,
                args.product, args.forge, args.version, args.timestamp)
        else:
            formatter = formats.Simple(cg)
        output = formatter.generate()
    else:
        output = cg.output_key_errs()

    as_formatter = formats.AsGraph(cg)

    if args.output:
        if args.lineno:
            prepare_lineno_output(args, cg)
        else:
            with open(args.output, "w+") as f:
                f.write(json.dumps(output))
    else:
        print("Analysing result is:\n", json.dumps(output))

    if args.as_graph_output:
        with open(args.as_graph_output, "w+") as f:
            f.write(json.dumps(as_formatter.generate()))

def run_analysing(args, filename):
    msg = utils.check_file_content(filename[0])
    if msg:
        print("Found broken content in file:", filename, msg)
        return
    else:
        args.entry_point = filename
        try:
            #TODO: make CG argument passing vector understandable
            cg = CallGraphGenerator(args.entry_point, args.package,
                                args.max_iter, args.operation)
            cg.analyze()
        except Exception as e:
            msg = "\nSomething went wrong while analysing " + filename[0]
            print(msg, str(e))
            return
        #TODO: Handle the return/raise part properly
        prepare_output(args, cg)

# This function walks through directory and parallelly runs
# separated threads for each independent file.
def analyze_multiple_files(args):
    fileslist = []
    for (dirpath, dirnames, filenames) in os.walk(args.dir):
        for filename in filenames:
            fileslist.append(os.sep.join([dirpath, filename]))
    for i in range(len(fileslist)):
        print("Running analysing for file:", i, fileslist[i])
        run_analysing(args, [fileslist[i]])

def initiate_analyzing(args):
    call_graphs = []
    if args.dir:
        analyze_multiple_files(args)
    else:
        run_analysing(args, args.entry_point)

def main():
    args = parse_cmd_args()
    initiate_analyzing(args)

if __name__ == "__main__":
    main()

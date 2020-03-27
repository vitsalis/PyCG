import os
import sys
import json
import argparse
from pkg_resources import Requirement

from pycg.pycg import CallGraphGenerator

def to_uri(product, modname, name):
    if not name.startswith(modname):
        raise Exception("name should start with modname")

    cleared = name[len(modname):]
    if cleared.startswith("."):
        cleared = cleared[1:]

    return f"//{product}/{modname}/{cleared}"

def find_dependencies(package_path):
    res = []
    requirements_path = os.path.join(package_path, "requirements.txt")

    if not os.path.exists(requirements_path):
        return res

    reqs = []
    with open(requirements_path, "r") as f:
        lines = [l.strip() for l in f.readlines()]

    for line in lines:
        req = Requirement.parse(line)

        product = req.unsafe_name
        specs = req.specs

        constraints = []

        def add_range(begin, end):
            if begin and end:
                if begin[1] and end[1]:
                    constraints.append(f"[{begin[0]}..{end[0]}]")
                elif begin[1]:
                    constraints.append(f"[{begin[0]}..{end[0]})")
                elif end[1]:
                    constraints.append(f"({begin[0]}..{end[0]}]")
                else:
                    constraints.append(f"({begin[0]}..{end[0]})")
            elif begin:
                if begin[1]:
                    constraints.append(f"[{begin[0]}..]")
                else:
                    constraints.append(f"({begin[0]}..]")
            elif end:
                if end[1]:
                    constraints.append(f"[..{end[0]}]")
                else:
                    constraints.append(f"[..{end[0]})")

        begin = None
        end = None
        for key, val in sorted(specs, key=lambda x: x[1]):
            # if begin, then it is already in a range
            if key == "==":
                if begin and end:
                    add_range(begin, end)
                    begin = None
                    end = None
                if not begin:
                    constraints.append(f"[{val}]")

            if key == ">":
                if end:
                    add_range(begin, end)
                    end = None
                    begin = None
                if not begin:
                    begin = (val, False)
            if key == ">=":
                if end:
                    add_range(begin, end)
                    begin = None
                    end = None
                if not begin:
                    begin = (val, True)

            if key == "<":
                end = (val, False)
            if key == "<=":
                end = (val, True)
        add_range(begin, end)

        res.append({"forge": "PyPI", "product": req.name, "constraints": constraints})

    return res

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

    args = parser.parse_args()

    cg = CallGraphGenerator(args.entry_point, args.package)
    cg.analyze()

    output_cg = {}

    if args.fasten:
        output_cg["product"] = args.product
        output_cg["forge"] = args.forge
        output_cg["depset"] = find_dependencies(args.package)
        output_cg["version"] = args.version
        output_cg["timestamp"] = args.timestamp
        output_cg["cha"] = {}
        output_cg["graph"] = []

        edges, modules = cg.output_edges()
        for src, dst in edges:
            src_mod = modules.get(src, "")
            dst_mod = modules.get(dst, "")
            output_cg["graph"].append([
                to_uri(args.product, src_mod, src),
                to_uri(args.product, dst_mod, dst)
            ])
    else:
        output = cg.output()
        for node in output:
            output_cg[node] = list(output[node])

    print (json.dumps(output_cg))

if __name__ == "__main__":
    main()

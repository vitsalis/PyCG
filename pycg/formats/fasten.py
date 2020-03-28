import os

from pkg_resources import Requirement

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

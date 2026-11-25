import random
import re
import sys

SITE = re.compile(r"^(\d+):(\d+) (\S+)  (.*)$")


def read_skeleton(path):
    modules = []
    sites = []
    module = node = None
    last = None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("== "):
            module = line[3:].strip()
            modules.append(module)
        elif line.startswith("[") and line.endswith("]"):
            node = line[1:-1]
        else:
            m = SITE.match(line)
            if m:
                last = {
                    "module": module,
                    "node": node,
                    "line": int(m.group(1)),
                    "col": int(m.group(2)),
                    "kind": m.group(3),
                    "text": m.group(4),
                    "value": False,
                }
                sites.append(last)
            elif "a value site" in line:
                last["value"] = True
    order = {m: i for i, m in enumerate(modules)}
    sites.sort(key=lambda s: (order[s["module"]], s["line"], s["col"]))
    for i, s in enumerate(sites, 1):
        s["n"] = i
    return sites


def main():
    sites = read_skeleton(sys.argv[1])
    explicit = [s for s in sites if s["kind"] in ("call", "decorator")]
    implicit = [s for s in sites if s["kind"] not in ("call", "decorator")]
    rng = random.Random(20261124)
    drawn = rng.sample(explicit, 100) + rng.sample(implicit, 40)
    numbers = {s["n"] for s in drawn}
    added = [s for s in sites if s["value"] and s["n"] not in numbers]
    print(f"# {len(sites)} sites: {len(explicit)} explicit, {len(implicit)} implicit, "
          f"{sum(s['value'] for s in sites)} value sites")
    print(f"# draw: 100 explicit, 40 implicit; {len(added)} value sites added")
    for group, items in (("explicit", drawn[:100]), ("implicit", drawn[100:]), ("value", added)):
        for s in sorted(items, key=lambda s: s["n"]):
            flag = " value" if s["value"] else ""
            print(f"{s['n']:5d} {group:8s} {s['module']} [{s['node']}] "
                  f"{s['line']}:{s['col']} {s['kind']}{flag}  {s['text']}")


main()

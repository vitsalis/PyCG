import random
import re
import sys

SITE = re.compile(r"^(\d+):(\d+) (\S+)\s+(.*)$")


def sites(skeleton):
    module = None
    node = None
    found = []
    for line in open(skeleton, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("== "):
            module = line[3:]
        elif line.startswith("["):
            node = line[1:-1]
        else:
            match = SITE.match(line)
            if match:
                found.append((module, node, int(match[1]), int(match[2]), match[3], match[4]))
    order = {}
    for module, *_ in found:
        order.setdefault(module, len(order))
    found.sort(key=lambda s: (order[s[0]], s[2], s[3]))
    return found


def value_sites(report):
    lines = open(report, encoding="utf-8").read().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("  value sites:"))
    keys = set()
    for line in lines[start + 1:]:
        if not line.startswith("    "):
            break
        module, position = line.split()[:2]
        row, column = position.split(":")
        keys.add((module, int(row), int(column)))
    return keys


def main(skeleton, report):
    all_sites = sites(skeleton)
    values = value_sites(report)
    rng = random.Random(20261124)
    drawn = set(rng.sample(range(len(all_sites)), 70))
    keys = [(s[0], s[2], s[3]) for s in all_sites]
    assert values <= set(keys)
    added = {i for i, k in enumerate(keys) if k in values and i not in drawn}
    for i in sorted(drawn | added):
        module, node, row, column, kind, text = all_sites[i]
        origin = "drawn" if i in drawn else "value"
        print(f"{i + 1}\t{origin}\t{module}\t{node}\t{row}:{column}\t{kind}\t{text}")


main(sys.argv[1], sys.argv[2])

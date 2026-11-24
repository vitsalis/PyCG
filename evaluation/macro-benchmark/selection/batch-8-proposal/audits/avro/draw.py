import random
import re
import sys

SEED = 20261124
EXPLICIT = ("call", "decorator")


def read_sites(skeleton):
    sites = []
    module = node = None
    for line in open(skeleton, encoding="utf-8"):
        if line.startswith("== "):
            module = line[3:].strip()
        elif line.startswith("["):
            node = line.strip()[1:-1]
        elif re.match(r"\d+:\d+ ", line):
            pos, kind, text = line.rstrip("\n").split(None, 2)
            row, col = pos.split(":")
            sites.append((module, int(row), int(col), kind, node, text))
    order = list(dict.fromkeys(s[0] for s in sites))
    sites.sort(key=lambda s: (order.index(s[0]), s[1], s[2]))
    return sites


def read_value_sites(report):
    found = []
    inside = False
    for line in open(report, encoding="utf-8"):
        if line.startswith("  value sites:"):
            inside = True
            continue
        if inside and not line.startswith("    "):
            break
        if inside:
            module, pos = line.split()[:2]
            row, col = pos.split(":")
            found.append((module, int(row), int(col)))
    return found


def main(skeleton, report):
    sites = read_sites(skeleton)
    numbered = list(enumerate(sites, 1))
    explicit = [s for s in numbered if s[1][3] in EXPLICIT]
    implicit = [s for s in numbered if s[1][3] not in EXPLICIT]
    n_explicit = round(70 * len(explicit) / len(sites))
    rng = random.Random(SEED)
    drawn = rng.sample(explicit, n_explicit) + rng.sample(implicit, 70 - n_explicit)
    drawn_keys = {s[1][:3] for s in drawn}
    values = read_value_sites(report)
    index = {s[1][:3]: s for s in numbered}
    added = [index[v] for v in values if v not in drawn_keys]
    print(f"# sites {len(sites)}: explicit {len(explicit)}, implicit {len(implicit)}")
    print(f"# drawn {n_explicit} explicit and {70 - n_explicit} implicit with random.Random({SEED})")
    print(f"# value sites {len(values)}, of them {len(values) - len(added)} drawn; {len(added)} added")
    for group, items in (("drawn", drawn), ("value", added)):
        for number, (module, row, col, kind, node, text) in sorted(items):
            print(f"{group}\t{number}\t{module}\t{row}:{col}\t{kind}\t[{node}]\t{text}")


if __name__ == "__main__":
    main(*sys.argv[1:])

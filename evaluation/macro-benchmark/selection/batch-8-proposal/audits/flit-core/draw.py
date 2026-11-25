import random
import re
import sys

SEED = 20261124
N_EXPLICIT = 50
N_IMPLICIT = 20
EXPLICIT = {"call", "decorator"}

SITE = re.compile(r"^(\d+):(\d+) (\S+)  (.*)$")
VALUE = re.compile(r"^    (\S+) (\d+):(\d+) (\S+) \[")


def read_sites(skeleton):
    modules = []
    sites = {}
    module = node = None
    with open(skeleton) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("== "):
                module = line[3:].strip()
                modules.append(module)
                sites[module] = []
            elif line.startswith("["):
                node = line[1:line.index("]")]
            else:
                m = SITE.match(line)
                if m:
                    sites[module].append((module, int(m[1]), int(m[2]), m[3], node, m[4]))
    numbered = []
    for module in modules:
        numbered.extend(sorted(sites[module], key=lambda s: (s[1], s[2])))
    return numbered


def read_value_sites(report):
    keys = set()
    inside = False
    with open(report) as f:
        for line in f:
            if line.startswith("  value sites:"):
                inside = True
                continue
            if inside:
                m = VALUE.match(line)
                if not m:
                    break
                keys.add((m[1], int(m[2]), int(m[3])))
    return keys


def main(skeleton, report):
    sites = read_sites(skeleton)
    explicit = [i for i, s in enumerate(sites) if s[3] in EXPLICIT]
    implicit = [i for i, s in enumerate(sites) if s[3] not in EXPLICIT]
    rng = random.Random(SEED)
    drawn = rng.sample(explicit, N_EXPLICIT) + rng.sample(implicit, N_IMPLICIT)
    values = read_value_sites(report)
    index = {s[:3]: i for i, s in enumerate(sites)}
    added = sorted(index[k] for k in values if index[k] not in drawn)
    print(f"# {len(sites)} sites: {len(explicit)} explicit, {len(implicit)} implicit")
    print(f"# drawn: {N_EXPLICIT} explicit, {N_IMPLICIT} implicit; value sites added: {len(added)}")
    for i in sorted(drawn):
        tag = " value" if sites[i][:3] in values else ""
        print(f"{i + 1} {sites[i][0]} {sites[i][1]}:{sites[i][2]} {sites[i][3]} [{sites[i][4]}] {sites[i][5]}{tag}")
    print("# value sites not drawn")
    for i in added:
        print(f"{i + 1} {sites[i][0]} {sites[i][1]}:{sites[i][2]} {sites[i][3]} [{sites[i][4]}] {sites[i][5]} value")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

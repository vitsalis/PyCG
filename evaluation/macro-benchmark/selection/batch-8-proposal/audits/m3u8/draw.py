import random
import re
import sys

SITE = re.compile(r"^(\d+):(\d+) (\S+)\s+(.*)$")
EXPLICIT = {"call", "decorator"}
VALUE_SITES = {
    ("m3u8.parser", 96, 49),
    ("m3u8.parser", 297, 32),
    ("m3u8.parser", 298, 39),
    ("m3u8.parser", 299, 41),
    ("m3u8.parser", 300, 44),
    ("m3u8.parser", 301, 40),
    ("m3u8.parser", 335, 43),
    ("m3u8.parser", 337, 35),
    ("m3u8.parser", 523, 26),
    ("m3u8.version_matching", 21, 25),
}


def read_skeleton(path):
    modules = []
    sites = {}
    module = node = None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("== "):
                module = line[3:].strip()
                modules.append(module)
                sites[module] = []
            elif line.startswith("["):
                node = line.strip()[1:-1]
            else:
                m = SITE.match(line)
                if m:
                    sites[module].append(
                        (int(m[1]), int(m[2]), m[3], node, m[4])
                    )
    numbered = []
    for module in modules:
        for lineno, col, kind, node, text in sorted(sites[module]):
            numbered.append((module, lineno, col, kind, node, text))
    return numbered


def main(path):
    sites = read_skeleton(path)
    assert len(sites) == 1303
    explicit = [i for i, s in enumerate(sites) if s[3] in EXPLICIT]
    implicit = [i for i, s in enumerate(sites) if s[3] not in EXPLICIT]
    assert len(explicit) == 780 and len(implicit) == 523
    rng = random.Random(20261124)
    drawn = sorted(rng.sample(explicit, 42)) + sorted(rng.sample(implicit, 28))
    value = [
        i for i, s in enumerate(sites) if (s[0], s[1], s[2]) in VALUE_SITES
    ]
    assert len(value) == len(VALUE_SITES)
    added = [i for i in value if i not in drawn]
    for label, group in (("drawn", drawn), ("value", added)):
        for i in group:
            module, lineno, col, kind, node, text = sites[i]
            print(f"{i + 1:4d} {label:5s} {module} [{node}] {lineno}:{col} {kind}  {text}")


main(sys.argv[1])

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pycg.analysis import mro, stubs  # noqa: E402

VECTORS_DIRECTORY = ROOT / "crates" / "pycg_stubs" / "tests" / "vectors"
SEED = 20261126
CASES_PER_FUNCTION = 400
POOL_SIZE = 8
BASES_MAX = 4
MRO_LENGTH_MAX = 6
SLOTS_MAX = 3
SLOT_CANDIDATES_MAX = 3
MROS_PER_CANDIDATE_MAX = 3
LIMIT_MAX = 12


def pool_names(generator):
    return [f"C{index}" for index in range(generator.randint(2, POOL_SIZE))]


def random_mro(generator, name, pool):
    tail = generator.sample(pool, generator.randint(0, min(len(pool), MRO_LENGTH_MAX)))
    return [name] + [item for item in tail if item != name]


def linearize_cases(generator):
    cases = []
    for _ in range(CASES_PER_FUNCTION):
        pool = pool_names(generator)
        cls = generator.choice(pool)
        bases = [generator.choice(pool) for _ in range(generator.randint(0, BASES_MAX))]
        mros = {base: random_mro(generator, base, pool) for base in sorted(set(bases))}
        expected = mro.linearize(cls, bases, mros.__getitem__)
        cases.append({"class": cls, "bases": bases, "mros": mros, "expected": expected})
    return cases


def slots_and_mros(generator):
    pool = pool_names(generator)
    cls = generator.choice(pool)
    slots = []
    for _ in range(generator.randint(0, SLOTS_MAX)):
        slot = []
        for _ in range(generator.randint(0, SLOT_CANDIDATES_MAX)):
            slot.append(None if generator.random() < 0.15 else generator.choice(pool))
        slots.append(slot)
    names = sorted({candidate for slot in slots for candidate in slot if candidate})
    mros = {
        name: [
            random_mro(generator, name, pool)
            for _ in range(generator.randint(0, MROS_PER_CANDIDATE_MAX))
        ]
        for name in names
    }
    return cls, slots, mros


def mros_of(mros):
    return lambda candidate: [[]] if candidate is None else mros[candidate]


def linearizations_cases(generator):
    cases = []
    for _ in range(CASES_PER_FUNCTION):
        cls, slots, mros = slots_and_mros(generator)
        limit = generator.randint(0, LIMIT_MAX)
        expected = mro.linearizations(cls, slots, mros_of(mros), limit)
        cases.append(
            {
                "class": cls,
                "slots": slots,
                "mros": mros,
                "limit": limit,
                "expected": expected,
            }
        )
    return cases


def exhaustive_order_cases(generator):
    cases = []
    for _ in range(CASES_PER_FUNCTION):
        cls, slots, mros = slots_and_mros(generator)
        expected = mro.exhaustive_order(cls, slots, mros_of(mros))
        cases.append({"class": cls, "slots": slots, "mros": mros, "expected": expected})
    return cases


def stub_types(directory):
    found = {}
    files = sorted(directory.glob("*.json")) + sorted(
        (directory / stubs.THIRD_PARTY_DIRECTORY_NAME).glob("*.json")
    )
    for path in files:
        package = json.loads(path.read_text(encoding="utf-8"))
        pending = [
            entry
            for module in package["modules"].values()
            for entry in module["names"].values()
        ]
        while pending:
            entry = pending.pop()
            if entry["k"] != "c":
                continue
            for reduced in [*entry["b"], *([entry["meta"]] if "meta" in entry else [])]:
                found.setdefault(json.dumps(reduced, sort_keys=True), reduced)
            pending.extend(entry["m"].values())
    return [found[key] for key in sorted(found)]


def class_names_cases():
    return [
        {"type": reduced, "expected": stubs.class_names(reduced)}
        for reduced in stub_types(stubs.DATA_DIRECTORY)
        if not isinstance(reduced, str) or not reduced[:1].isalpha()
    ]


def write(name, cases):
    lines = ",\n".join(json.dumps(case, sort_keys=True) for case in cases)
    path = VECTORS_DIRECTORY / name
    path.write_text(f"[\n{lines}\n]\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Write the unit vectors of pycg_stubs from the Python engine."
    )
    parser.parse_args(argv)
    VECTORS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    generator = random.Random(SEED)
    write("linearize.json", linearize_cases(generator))
    write("linearizations.json", linearizations_cases(generator))
    write("exhaustive_order.json", exhaustive_order_cases(generator))
    write("class_names.json", class_names_cases())


if __name__ == "__main__":
    main()

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pycg.analysis import model, mro, stubs  # noqa: E402

VECTORS_DIRECTORY = ROOT / "crates" / "pycg_stubs" / "tests" / "vectors"
MODEL_VECTORS = ROOT / "crates" / "pycg_analysis" / "tests" / "vectors" / "model.rs"
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


CODE_POINT_POOLS = (
    range(0x20, 0x7F),
    (0x22, 0x27, 0x5C, 0x09, 0x0A, 0x0D, 0x00, 0x1F, 0x7F),
    range(0x80, 0x100),
    range(0x100, 0x2000),
    range(0xD800, 0xE000),
    range(0xE000, 0x10000),
    range(0x10000, 0x110000),
)
TEXT_LENGTH_MAX = 12
CONSTANT_NAME_DIGITS_AROUND = (639, 640, 641, 700)
SIGNATURE_NAMES = ("a", "b", "c", "d", "e")
SIGNATURE_CASES = 300
BINDS_PER_SIGNATURE = 6
PATTERN_CASES = 300
MATCHES_PER_PATTERN = 6
PATTERN_ALPHABET = "aAbB_"
SITE_CASES = ("main", "main#1", "main#1#2", "#3", "", "a.b:1:2#site")
STEPS_CASES = (("a.b.c", 0), ("a.b.c", 1), ("a.b.c", 2), ("a.b.c", 3), ("a", 1))


def random_code_points(generator):
    return [
        generator.choice(generator.choice(CODE_POINT_POOLS))
        for _ in range(generator.randint(0, TEXT_LENGTH_MAX))
    ]


def random_bytes(generator):
    return bytes(
        generator.choice((generator.randrange(256), 0x22, 0x27, 0x5C))
        for _ in range(generator.randint(0, TEXT_LENGTH_MAX))
    )


def int_values(generator):
    values = [0, 1, -1, 255, -256]
    for digits in CONSTANT_NAME_DIGITS_AROUND:
        values += [10**digits - 1, 10**digits, 10**digits + 1]
    for _ in range(40):
        values.append(generator.randrange(-(10 ** generator.randint(1, 700)), 10**700))
    return values + [-value for value in values if value]


RUST_ESCAPES = {"\\": "\\\\", '"': '\\"'}


def rust_character(character):
    if character in RUST_ESCAPES:
        return RUST_ESCAPES[character]
    if 0x20 <= ord(character) < 0x7F:
        return character
    return f"\\u{{{ord(character):x}}}"


def rust_text(text):
    return '"' + "".join(map(rust_character, text)) + '"'


def rust_texts(texts):
    return "&[" + ", ".join(rust_text(text) for text in texts) + "]"


def rust_option(text):
    return "None" if text is None else f"Some({rust_text(text)})"


def random_signature(generator):
    names = list(SIGNATURE_NAMES)
    generator.shuffle(names)
    positional_count = generator.randint(0, 3)
    positional = names[:positional_count]
    keyword_only = names[positional_count : positional_count + generator.randint(0, 2)]
    vararg = generator.choice((None, "args"))
    kwarg = generator.choice((None, "kwargs"))
    return model.Signature(
        positional,
        generator.randint(0, positional_count),
        keyword_only,
        vararg,
        kwarg,
    )


def signature_line(generator, signature):
    candidates = [*SIGNATURE_NAMES, "args", "kwargs", "z"]
    queries = []
    for _ in range(BINDS_PER_SIGNATURE):
        given = generator.randint(0, 4)
        keywords = generator.sample(candidates, generator.randint(0, 3))
        if keywords and generator.random() < 0.2:
            keywords.append(keywords[0])
        optional = generator.sample(SIGNATURE_NAMES, generator.randint(0, 3))
        bound = signature.binds(given, keywords, optional)
        queries.append(
            f"({given}, {rust_texts(keywords)}, {rust_texts(optional)}, "
            f"{str(bound).lower()})"
        )
    accepted = [name for name in candidates if signature.accepts_keyword(name)]
    return (
        f"    ({rust_texts(signature.positional)}, "
        f"{signature.positional_only_count}, {rust_texts(signature.keyword_only)}, "
        f"{rust_option(signature.vararg)}, {rust_option(signature.kwarg)}, "
        f"{rust_texts(signature.names())}, {rust_texts(accepted)}, "
        f"&[{', '.join(queries)}]),"
    )


def random_affix(generator):
    return "".join(
        generator.choice(PATTERN_ALPHABET) for _ in range(generator.randint(0, 2))
    )


def pattern_line(generator):
    case = generator.choice((None, "lower", "upper"))
    pattern = model.Pattern(random_affix(generator), random_affix(generator), case)
    candidates = [
        pattern.prefix + random_affix(generator) + pattern.suffix,
        random_affix(generator) + random_affix(generator),
        pattern.prefix + "\u00e9" + pattern.suffix,
        pattern.prefix,
        pattern.prefix + pattern.suffix,
        random_affix(generator),
    ]
    matched = ", ".join(
        f"({rust_text(name)}, {rust_option(pattern.matches(name))})"
        for name in candidates[:MATCHES_PER_PATTERN]
    )
    return (
        f"    ({rust_text(pattern.prefix)}, {rust_text(pattern.suffix)}, "
        f"{rust_option(case)}, {rust_text(pattern.name)}, &[{matched}]),"
    )


def model_vectors(generator):
    texts = [random_code_points(generator) for _ in range(CASES_PER_FUNCTION)]
    texts += [[0x27], [0x22], [0x27, 0x22], [], [0xD800], [0x10FFFF]]
    lines = ["pub const STR_NAMES: &[(&[u32], &str)] = &["]
    for points in texts:
        name = model.constant_name("".join(map(chr, points)))
        lines.append(f"    (&{points}, {rust_text(name)}),")
    lines.append("];")
    lines.append("pub const BYTES_NAMES: &[(&[u8], &str)] = &[")
    for value in [random_bytes(generator) for _ in range(CASES_PER_FUNCTION)]:
        lines.append(f"    (&{list(value)}, {rust_text(model.constant_name(value))}),")
    lines.append("];")
    lines.append("pub const INT_NAMES: &[(&str, &str)] = &[")
    for value in int_values(generator):
        lines.append(f'    ("{value}", "{model.constant_name(value)}"),')
    lines.append("];")
    lines.append("pub const SITE_NAMES: &[(&str, &str)] = &[")
    for site in SITE_CASES:
        lines.append(f"    ({rust_text(site)}, {rust_text(model.site_name(site))}),")
    lines.append("];")
    lines.append("pub const STEPS_PAST_ROOT: &[(&str, usize, &[&str])] = &[")
    for name, steps in STEPS_CASES:
        expected = model.External(name, steps).steps_past_root()
        lines.append(f"    ({rust_text(name)}, {steps}, {rust_texts(expected)}),")
    lines.append("];")
    lines.append(
        "pub type Binding = "
        "(usize, &'static [&'static str], &'static [&'static str], bool);"
    )
    lines.append(
        "pub type SignatureCase = (&'static [&'static str], usize, "
        "&'static [&'static str], Option<&'static str>, Option<&'static str>, "
        "&'static [&'static str], &'static [&'static str], &'static [Binding]);"
    )
    lines.append("pub const SIGNATURES: &[SignatureCase] = &[")
    for _ in range(SIGNATURE_CASES):
        lines.append(signature_line(generator, random_signature(generator)))
    lines.append("];")
    lines.append(
        "pub type PatternCase = (&'static str, &'static str, Option<&'static str>, "
        "&'static str, &'static [(&'static str, Option<&'static str>)]);"
    )
    lines.append("pub const PATTERNS: &[PatternCase] = &[")
    for _ in range(PATTERN_CASES):
        lines.append(pattern_line(generator))
    lines.append("];")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Write the unit vectors of the Rust crates from the Python engine."
    )
    parser.parse_args(argv)
    VECTORS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    generator = random.Random(SEED)
    write("linearize.json", linearize_cases(generator))
    write("linearizations.json", linearizations_cases(generator))
    write("exhaustive_order.json", exhaustive_order_cases(generator))
    write("class_names.json", class_names_cases())
    MODEL_VECTORS.parent.mkdir(parents=True, exist_ok=True)
    MODEL_VECTORS.write_text(model_vectors(random.Random(SEED)), encoding="utf-8")


if __name__ == "__main__":
    main()

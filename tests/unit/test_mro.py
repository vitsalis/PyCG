from hypothesis import given
from hypothesis import strategies as st

from pycg.analysis.mro import linearize


def mro_table(**mros):
    return lambda cls: mros[cls]


def test_class_without_bases():
    assert linearize("A", [], mro_table()) == ["A"]


def test_single_inheritance():
    mro_of = mro_table(A=["A"], B=["B", "A"])

    assert linearize("C", ["B"], mro_of) == ["C", "B", "A"]


def test_diamond():
    mro_of = mro_table(A=["A"], B=["B", "A"], C=["C", "A"])

    assert linearize("D", ["B", "C"], mro_of) == ["D", "B", "C", "A"]


def test_classic_c3_example():
    mro_of = mro_table(
        O=["O"],
        A=["A", "O"],
        B=["B", "O"],
        C=["C", "O"],
        D=["D", "O"],
        E=["E", "O"],
        K1=["K1", "A", "B", "C", "O"],
        K2=["K2", "D", "B", "E", "O"],
        K3=["K3", "D", "A", "O"],
    )

    assert linearize("Z", ["K1", "K2", "K3"], mro_of) == [
        "Z",
        "K1",
        "K2",
        "K3",
        "D",
        "A",
        "B",
        "C",
        "E",
        "O",
    ]


def test_inconsistent_order_falls_back_to_depth_first_order():
    mro_of = mro_table(A=["A"], B=["B"], X=["X", "A", "B"], Y=["Y", "B", "A"])

    assert linearize("Z", ["X", "Y"], mro_of) == ["Z", "X", "A", "B", "Y"]


def test_class_listed_as_its_own_base_is_left_out():
    mro_of = mro_table(A=["A"])

    assert linearize("B", ["B", "A"], mro_of) == ["B", "A"]


def test_base_that_already_inherits_from_the_class_is_left_out():
    mro_of = mro_table(A=["A"], B=["B", "C", "A"])

    assert linearize("C", ["A", "B"], mro_of) == ["C", "A"]


def test_duplicate_base_is_listed_once():
    mro_of = mro_table(A=["A"])

    assert linearize("B", ["A", "A"], mro_of) == ["B", "A"]


@given(st.data())
def test_python_gives_the_same_order_for_every_hierarchy_that_it_accepts(data):
    classes, mros = {}, {}
    for index in range(data.draw(st.integers(1, 9))):
        names = sorted(classes)
        bases = []
        if names:
            bases = data.draw(st.lists(st.sampled_from(names), unique=True, max_size=4))
        name = f"C{index}"
        try:
            cls = type(name, tuple(classes[base] for base in bases), {})
        except TypeError:
            continue
        expected = [c.__name__ for c in cls.__mro__ if c is not object]

        assert linearize(name, bases, mros.__getitem__) == expected
        classes[name], mros[name] = cls, expected


def naive_merge(sequences):
    sequences = [list(sequence) for sequence in sequences if sequence]
    result = []
    while sequences:
        for sequence in sequences:
            head = sequence[0]
            if not any(head in other[1:] for other in sequences):
                break
        else:
            return None
        result.append(head)
        sequences = [s[1:] if s[0] == head else s for s in sequences]
        sequences = [sequence for sequence in sequences if sequence]
    return result


def naive_linearize(cls, bases, mro_of):
    usable = []
    for base in bases:
        if base == cls or base in usable or cls in mro_of(base):
            continue
        usable.append(base)
    base_mros = [list(mro_of(base)) for base in usable]
    merged = naive_merge(base_mros + [list(usable)])
    if merged is None:
        merged = list(dict.fromkeys(item for mro in base_mros for item in mro))
    return [cls] + merged


MRO_TAILS_OF_ANY_SHAPE = st.lists(st.sampled_from("ABCDEFZ"), max_size=6)


@given(
    st.lists(st.sampled_from("ABCDEF"), max_size=4),
    st.dictionaries(st.sampled_from("ABCDEF"), MRO_TAILS_OF_ANY_SHAPE, min_size=6),
)
def test_the_merge_gives_what_the_naive_merge_gives(bases, shapes):
    mros = {name: [name, *shape] for name, shape in shapes.items()}

    assert linearize("Z", bases, mros.__getitem__) == naive_linearize(
        "Z", bases, mros.__getitem__
    )

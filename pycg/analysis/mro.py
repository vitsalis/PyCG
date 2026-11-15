"""C3 linearization of class hierarchies (the method resolution order).

Python computes the MRO of a class with the C3 algorithm and rejects class
statements whose bases have no C3 order. The analysis sees hierarchies that
Python would reject and must still order them, so it falls back to a simpler
order instead of failing. A base expression may also refer to several
classes (`A if flag else B`); each choice is a separate hierarchy with its
own MRO.
"""

import itertools
import math
from collections import Counter, deque


def linearize(cls, bases, mro_of):
    """Return the MRO of `cls`, whose direct bases are `bases`, in order.

    `mro_of(base)` returns the current MRO of a base. A base that would make
    the hierarchy cyclic (the class itself, or a base whose MRO already
    contains the class) is left out, and so is a repeated base. If the bases
    have no C3 order, the result is the class followed by the MROs of its
    bases, left to right, each class at its first position.
    """
    usable = []
    for base in bases:
        if base == cls or base in usable or cls in mro_of(base):
            continue
        usable.append(base)

    base_mros = [list(mro_of(base)) for base in usable]
    merged = _merge(base_mros + [list(usable)])
    if merged is None:
        merged = _first_occurrences(item for mro in base_mros for item in mro)
    return [cls] + merged


def _merge(sequences):
    """Merge `sequences` as C3 does. Return None if no order exists.

    Repeatedly take the first head that is in no sequence's tail. `tails`
    counts the occurrences of each item in the tails, so that test is one
    look-up, not a search of every tail.
    """
    sequences = [deque(sequence) for sequence in sequences if sequence]
    tails = Counter(
        item for sequence in sequences for item in itertools.islice(sequence, 1, None)
    )
    result = []
    while sequences:
        for sequence in sequences:
            head = sequence[0]
            if not tails[head]:
                break
        else:
            return None
        result.append(head)
        for sequence in sequences:
            if sequence[0] == head:
                sequence.popleft()
                if sequence:
                    tails[sequence[0]] -= 1
        sequences = [sequence for sequence in sequences if sequence]
    return result


def _first_occurrences(items):
    """`items` without repeats, each at its first position."""
    return list(dict.fromkeys(items))


def linearizations(cls, slots, mros_of, limit):
    """Return the MROs of `cls` when a base expression may refer to several
    classes, or None if there would be more than `limit` of them.

    `slots` holds, per base expression, its candidate classes, and
    `mros_of(candidate)` the candidate's own MROs. Each choice of one
    candidate and one of its MROs per slot is a hierarchy that may exist at
    run time; the result has the MRO of each, without repeats. A candidate
    None stands for no base at all.
    """
    choices = [
        [(candidate, mro) for candidate in slot for mro in mros_of(candidate)]
        for slot in slots
    ]
    if math.prod(len(choice) for choice in choices) > limit:
        return None
    result = []
    for combination in itertools.product(*choices):
        chosen = {}
        for candidate, mro in combination:
            if candidate is not None:
                chosen.setdefault(candidate, mro)
        mro = linearize(cls, list(chosen), chosen.__getitem__)
        if mro not in result:
            result.append(mro)
    return result


def merged_order(cls, slots, mros_of):
    """Return `cls` followed by every class in the MROs of every candidate
    base, each at its first position: the classes of all hierarchies at once,
    including those of candidates on a cycle with `cls`."""
    candidates = [
        candidate
        for slot in slots
        for candidate in slot
        if candidate is not None and candidate is not cls
    ]
    return [cls] + _first_occurrences(
        item
        for candidate in candidates
        for mro in mros_of(candidate)
        for item in mro
        if item is not cls
    )

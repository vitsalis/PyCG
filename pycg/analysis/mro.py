import itertools
import math
from collections import Counter, deque


def linearize(cls, bases, mro_of):
    usable = []
    for base in bases:
        if base == cls or base in usable or cls in mro_of(base):
            continue
        usable.append(base)

    base_mros = [list(mro_of(base)) for base in usable]
    merged = _c3_merge(base_mros + [list(usable)])
    if merged is None:
        merged = _first_occurrences(item for mro in base_mros for item in mro)
    return [cls] + merged


def _c3_merge(sequences):
    sequences = [deque(sequence) for sequence in sequences if sequence]
    tail_occurrences = Counter(
        item for sequence in sequences for item in itertools.islice(sequence, 1, None)
    )
    result = []
    while sequences:
        for sequence in sequences:
            head = sequence[0]
            if not tail_occurrences[head]:
                break
        else:
            return None
        result.append(head)
        for sequence in sequences:
            if sequence[0] == head:
                sequence.popleft()
                if sequence:
                    tail_occurrences[sequence[0]] -= 1
        sequences = [sequence for sequence in sequences if sequence]
    return result


def _first_occurrences(items):
    return list(dict.fromkeys(items))


def linearizations(cls, slots, mros_of, limit):
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


def exhaustive_order(cls, slots, mros_of):
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

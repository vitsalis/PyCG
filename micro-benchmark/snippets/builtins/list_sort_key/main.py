def by_second(pair):
    return pair[1]

pairs = [(1, "b"), (2, "a")]
pairs.sort(key=by_second)

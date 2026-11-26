import ast

from .flow import FALSE, TRUE, UNKNOWN, State, truth_of, values_of

BUILTIN_CLASSES_SELF_MATCHING = frozenset(
    {
        "bool",
        "bytearray",
        "bytes",
        "dict",
        "float",
        "frozenset",
        "int",
        "list",
        "set",
        "str",
        "tuple",
    }
)


class Matching:
    def _stmt_Match(self, node):
        flow = self._flow
        subject = self.expression(node.subject)
        values = self._literals(node.subject)
        base = flow.state
        start, ends = base, []
        for case in node.cases:
            if not start.reachable:
                break
            flow.branch(start)
            matches = self._pattern(case.pattern, subject, values)
            holds = TRUE
            if case.guard is not None and matches & TRUE:
                self.condition(case.guard)
                holds = self._truth(case.guard)
            matched = flow.state
            flow.branch(matched)
            flow.state.reachable = matched.reachable and bool(matches & holds & TRUE)
            self._statements(case.body)
            ends.append(flow.state)
            failures = []
            if matches & FALSE:
                failures.append(State(start))
            if matches & TRUE and holds & FALSE:
                failures.append(matched)
            failed = flow.branch(start)
            flow.merge(start, failures or [_unreachable_state(start)], target=failed)
            start = failed
        ends.append(start)
        flow.merge(base, ends)

    def _pattern(self, pattern, subject, values):
        match pattern:
            case ast.MatchValue():
                value = self.expression(pattern.value)
                site = self._site(pattern)
                compared = self.rich_comparison(subject, value, ast.Eq(), site)
                if compared is not None:
                    self.analysis.add_truth(compared, self._caller, site)
                literals = self._literals(pattern.value)
                if values and literals:
                    return truth_of(
                        a == b for a in values_of(values) for b in values_of(literals)
                    )
            case ast.MatchSingleton():
                if values:
                    return truth_of(v is pattern.value for v in values_of(values))
            case ast.MatchOr():
                return self._or_pattern(pattern, subject, values)
            case ast.MatchSequence():
                if values:
                    return FALSE
                return self._sequence_pattern(pattern, subject)
            case ast.MatchMapping():
                if values:
                    return FALSE
                return self._mapping_pattern(pattern, subject)
            case ast.MatchClass():
                return self._class_pattern(pattern, subject)
            case ast.MatchStar():
                if pattern.name:
                    self._bind(pattern.name, subject)
                return TRUE
            case _:
                assert isinstance(pattern, ast.MatchAs), pattern
                truth = TRUE
                if pattern.pattern is not None:
                    truth = self._pattern(pattern.pattern, subject, values)
                if pattern.name:
                    self._bind(pattern.name, subject, *_truth_and_literals_of(values))
                return truth
        return UNKNOWN

    def _or_pattern(self, pattern, subject, values):
        flow = self._flow
        start = flow.state
        matched, may_match, always_fails = [], 0, True
        for alternative in pattern.patterns:
            flow.branch(start)
            truth = self._pattern(alternative, subject, values)
            if truth & TRUE:
                matched.append(flow.state)
                may_match = TRUE
            always_fails = always_fails and bool(truth & FALSE)
        flow.merge(start, matched or [_unreachable_state(start)])
        return may_match | (FALSE if always_fails else 0)

    def _sequence_pattern(self, pattern, subject):
        patterns = pattern.patterns
        star = next(
            (i for i, p in enumerate(patterns) if isinstance(p, ast.MatchStar)), None
        )
        site = self._site(pattern)
        self._length(subject, site)
        truths = []
        for index, inner in enumerate(patterns):
            if index == star:
                part = self._rest(subject, star, patterns, site)
            else:
                key = index if star is None or index < star else index - len(patterns)
                part = self._item(subject, key, site)
            truths.append(self._pattern(inner, part, None))
        return _truth_of_all_parts(truths)

    def _mapping_pattern(self, pattern, subject):
        site = self._site(pattern)
        keys = [self.expression(key) for key in pattern.keys]
        if keys:
            self._length(subject, site)
        truths = [
            self._pattern(inner, self._item(subject, key, site, node=True), None)
            for inner, key in zip(pattern.patterns, keys)
        ]
        if pattern.rest:
            container = self.analysis.container("dict", site)
            if subject is not None:
                self.analysis.add_dict_items(container, subject, self._caller, site)
            self._bind(pattern.rest, self.analysis.constant(container))
        return _truth_of_all_parts(truths)

    def _class_pattern(self, pattern, subject):
        cls = self.expression(pattern.cls)
        truths = []
        if (
            isinstance(pattern.cls, ast.Name)
            and pattern.cls.id in BUILTIN_CLASSES_SELF_MATCHING
            and self._is_builtin_reference(pattern.cls, pattern.cls.id)
            and len(pattern.patterns) == 1
        ):
            truths.append(self._pattern(pattern.patterns[0], subject, None))
        else:
            for index, inner in enumerate(pattern.patterns):
                part = self._matched_arg(subject, cls, index, inner)
                truths.append(self._pattern(inner, part, None))
        for attr, inner in zip(pattern.kwd_attrs, pattern.kwd_patterns):
            part = None
            if subject is not None:
                part = self.analysis.node()
                attr, site = self._scope.mangle(attr), self._site(inner)
                self.analysis.add_load(subject, attr, part, self._caller, site)
            truths.append(self._pattern(inner, part, None))
        return _truth_of_all_parts(truths)

    def _length(self, subject, site):
        if subject is not None:
            call = self.analysis.site_call(self._caller, site, ("special", "__len__"))
            self.analysis.add_special_call(subject, "__len__", call)

    def _item(self, subject, key, site, node=False):
        if subject is None:
            return None
        if not node:
            key = self.analysis.constant(self.analysis.const(key))
        if key is None:
            key = self.analysis.node()
        item = self.analysis.node()
        self.analysis.add_subscript(subject, key, item, None, self._caller, site)
        return item

    def _rest(self, subject, star, patterns, site):
        if subject is None:
            return None
        before = [self.analysis.node() for _ in range(star)]
        after = [self.analysis.node() for _ in range(len(patterns) - star - 1)]
        rest = self.analysis.node()
        self.analysis.add_unpack(subject, before, rest, after, self._caller, site)
        return rest

    def _matched_arg(self, subject, cls, index, inner):
        if subject is None or cls is None:
            return None
        site = self._site(inner)
        names, name = self.analysis.node(), self.analysis.node()
        self.analysis.add_load(cls, "__match_args__", names, self._caller, site)
        key = self.analysis.constant(self.analysis.const(index))
        self.analysis.add_subscript(names, key, name, None, self._caller, site)
        attribute = self.analysis.node()
        self.analysis.add_named_load(subject, name, attribute, self._caller, site)
        return attribute


def _truth_of_all_parts(truths):
    return (TRUE if all(part & TRUE for part in truths) else 0) | FALSE


def _unreachable_state(start):
    state = State(start)
    state.reachable = False
    return state


def _truth_and_literals_of(values):
    if values is None:
        return (UNKNOWN, None)
    return (truth_of(values_of(values)) or UNKNOWN, values)

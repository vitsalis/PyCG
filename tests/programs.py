"""Helpers that write a small program to a directory and analyse it."""

import textwrap

from pycg.pycg import CallGraphGenerator


def write(root, files):
    for path, source in files.items():
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, bytes):
            file.write_bytes(source)
        else:
            file.write_text(textwrap.dedent(source))


def analysed(root, files, entry_points=("main.py",), package=True, **options):
    """Analyse `files`, written under `root`; `options` go to the generator
    (`cap`)."""
    write(root, files)
    generator = CallGraphGenerator(
        [str(root / entry) for entry in entry_points],
        str(root) if package else None,
        **options,
    )
    generator.analyze()
    return generator


def call_graph(root, files, entry_points=("main.py",), package=True):
    return analysed(root, files, entry_points, package).output()


def main_graph(root, source):
    """The call graph of a program that is the single module `main`."""
    return call_graph(root, {"main.py": source})


def callees(graph, caller):
    return graph.get(caller, [])


def no_rule_sees_what_is_opaque(monkeypatch):
    """Fail if a rule's code receives the saturated value, an unknown class
    or an instance of one: as the object that a constraint applies to, as an
    object that the constraint holds (the arguments of an `Each`, the
    receiver of a binding, any other object in its slots), as the receiver
    that a rule binds or delivers to, and in the rules that come back to an
    object they remembered. Both ways into a constraint are checked: one
    object (`apply`) and the objects of a set (`apply_each`). Each object is
    checked when it arrives, against what is opaque then."""
    from pycg.analysis import hierarchy
    from pycg.analysis.model import Object
    from pycg.analysis.semantics import Analysis
    from pycg.analysis.solver import Constraint, Each, Watch

    def check(function, obj):
        assert not hierarchy.opaque(obj), f"{function.__qualname__}({obj!r})"

    def guard(function, *positions):
        def guarded(*args, **kwargs):
            for position in positions:
                check(function, args[position])
            return function(*args, **kwargs)

        return guarded

    def held(constraint):
        if isinstance(constraint, Each):
            return constraint.args
        slots = (
            name
            for kind in type(constraint).__mro__
            for name in vars(kind).get("__slots__", ())
        )
        values = (getattr(constraint, name, None) for name in slots)
        return [value for value in values if isinstance(value, Object)]

    def guard_apply(apply):
        def guarded(constraint, obj):
            check(apply, obj)
            for value in held(constraint):
                check(apply, value)
            return apply(constraint, obj)

        return guarded

    def guard_apply_each(apply_each):
        # The solver applies a constraint to a set of objects in one call,
        # and a constraint may pass them to its rule without `apply` (an
        # `Each` does): each object is checked as the constraint takes it.
        def guarded(constraint, objects):
            def checked():
                for obj in objects:
                    check(apply_each, obj)
                    for value in held(constraint):
                        check(apply_each, value)
                    yield obj

            return apply_each(constraint, checked())

        return guarded

    pending = [Constraint]
    while pending:
        kind = pending.pop()
        pending.extend(kind.__subclasses__())
        if "apply" in vars(kind):
            monkeypatch.setattr(kind, "apply", guard_apply(kind.apply))
        if "apply_each" in vars(kind):
            monkeypatch.setattr(kind, "apply_each", guard_apply_each(kind.apply_each))

    # A rule that waits until a class may answer a name runs at the wake,
    # for each receiver that it waited for (see `Hierarchy.later`).
    def guard_wake(wake):
        def guarded(watch):
            if watch.waiting:
                watch.waiting = {
                    (guard(rule, 0), *args): receivers
                    for (rule, *args), receivers in watch.waiting.items()
                }
            return wake(watch)

        return guarded

    monkeypatch.setattr(Watch, "wake", guard_wake(Watch.wake))
    for name in ("call_dunder", "_pattern_candidate", "load", "store", "call"):
        monkeypatch.setattr(Analysis, name, guard(getattr(Analysis, name), 1))
    # The receiver of a binding or a delivery, and the class that gets a
    # base.
    for name in ("bind", "deliver", "add_base"):
        monkeypatch.setattr(Analysis, name, guard(getattr(Analysis, name), 2))

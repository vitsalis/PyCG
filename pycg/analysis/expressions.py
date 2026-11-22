"""The expressions of a module: the constraints of each expression and the
node of its value.

`Expressions` is part of `ModuleBuilder` (see builder.py), whose names,
scopes and context it uses. An expression handler returns the node of the
expression's value, or None if the analysis does not track the value. A
construct without a handler is walked, so calls inside it are found.
"""

import ast
import operator as operators
import string

from .flow import FALSE, LITERALS, TRUE, UNKNOWN, literals_of, truth_of, values_of

# The modules whose `TYPE_CHECKING` is false at run time (and true only for
# a type checker).
TYPING_MODULES = ("typing", "typing_extensions")
TYPE_CHECKING_IMPORTS = frozenset(
    f"{module}.TYPE_CHECKING" for module in TYPING_MODULES
)

# The operator of each comparison of literal values.
_LITERAL_COMPARISONS = {
    ast.Eq: operators.eq,
    ast.NotEq: operators.ne,
    ast.Lt: operators.lt,
    ast.LtE: operators.le,
    ast.Gt: operators.gt,
    ast.GtE: operators.ge,
    ast.Is: operators.is_,
    ast.IsNot: operators.is_not,
}

# The values whose identity is the same on every Python: `is` decides on
# them.
_SINGLETONS = (None, True, False)

# The special method of each binary operator, without the underscores.
_OPERATORS = {
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.MatMult: "matmul",
    ast.Div: "truediv",
    ast.FloorDiv: "floordiv",
    ast.Mod: "mod",
    ast.Pow: "pow",
    ast.LShift: "lshift",
    ast.RShift: "rshift",
    ast.BitOr: "or",
    ast.BitXor: "xor",
    ast.BitAnd: "and",
}

_UNARY_OPERATORS = {ast.USub: "__neg__", ast.UAdd: "__pos__", ast.Invert: "__invert__"}

# The special method of each comparison, and that of its right operand.
_COMPARISONS = {
    ast.Eq: ("__eq__", "__eq__"),
    ast.NotEq: ("__ne__", "__ne__"),
    ast.Lt: ("__lt__", "__gt__"),
    ast.LtE: ("__le__", "__ge__"),
    ast.Gt: ("__gt__", "__lt__"),
    ast.GtE: ("__ge__", "__le__"),
}

# The conversion of a value in an f-string, by its `!` flag.
_CONVERSIONS = {ord("s"): "str", ord("r"): "repr", ord("a"): "repr"}

_DISPLAYS = {ast.Tuple: "tuple", ast.List: "list", ast.Set: "set"}


# The conversion that `!r`, `!a` and `!s` in a format field make.
FORMAT_CONVERSIONS = {"r": "repr", "a": "repr", "s": "str"}


def _is_str(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _format_fields(text):
    """The fields of the format string `text`: (argument, attribute names
    or None if the field indexes, conversion, spec); the argument is "" for
    an automatic number, an int, a keyword, or None for an index that no
    call supplies. Nothing if `text` is not a valid format."""
    try:
        parsed = list(string.Formatter().parse(text))
    except ValueError:
        return []
    fields = []
    for _, name, spec, conversion in parsed:
        if name is None:
            continue
        first, *attributes = name.split(".")
        if "[" in name:
            attributes = None
        if first.isascii() and first.isdigit():
            first = _format_index(first)
        fields.append((first, attributes, conversion, spec or ""))
    return fields


def _format_index(digits):
    """The position that the digits of a format field name, whatever their
    leading zeros; None past 19 digits: Python rejects an index past
    `sys.maxsize`, and no call has that many arguments."""
    digits = digits.lstrip("0") or "0"
    return int(digits) if len(digits) <= 19 else None


class Expressions:
    def expression(self, node):
        """Emit the constraints of the expression `node` and return the node
        of its value, or None."""
        handler = getattr(self, f"_expr_{type(node).__name__}", None)
        if handler is None:
            self._walk(node)
            return None
        value = handler(node)
        if isinstance(node, (ast.BinOp, ast.JoinedStr, ast.Call)):
            # A str built from a constant and another value (patterns.py).
            pattern = self.string_pattern(node)
            if pattern is not None:
                value = self._join([value, pattern])
                for operand in self._pattern_operands(node):
                    self.analysis.add_pattern_operand(operand, value)
        return value

    def _pattern_operands(self, node):
        """The nodes of the operands of the `+` chain or the right operand
        of the `%` of `node` whose values may decide its result (see
        `Patterns.add_pattern_operand`), with None for one whose value is
        not a node: a constant and an f-string that CPython joins into a
        new str (one of more than one part) are left out; a single-field
        f-string gives what `format` returns, which may be a str subclass,
        so it counts as None."""
        if not isinstance(node, ast.BinOp):
            return []
        if isinstance(node.op, ast.Mod):
            return _dynamic_operands([(node.right, self._binop_operands[node][1])])
        operands = []
        while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self._binop_operands[node]
            operands.append((node.right, right))
            node = node.left
        operands.append((node, left))
        return _dynamic_operands(operands)

    def _walk(self, node):
        """Visit the parts of a node that the builder does not model."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                self.statement(child)
            elif isinstance(child, ast.expr):
                self.expression(child)
            else:
                self._walk(child)

    def _truth(self, node):
        """What `bool()` of the value of the expression `node`, which has
        been evaluated, may give (see `TRUE` in flow.py). Known for values
        whose truth cannot change: literals, tuple displays, lambdas, names
        whose reaching definitions agree, and `not`, `and`, `or`,
        comparisons and conditional expressions of those. A list, set or
        dict display is not: the container may change."""
        return self._facts(node)[0]

    def _literals(self, node):
        """The literal values that the evaluated expression `node` may have
        (see `LITERALS` in flow.py), or None if it may have another."""
        return self._facts(node)[1]

    def _facts(self, node):
        """`(truth, literal values)` of the evaluated expression `node`."""
        facts = self._known_facts.get(node)
        if facts is not None:
            return facts
        if type(node) is ast.Constant:
            value = node.value
            if isinstance(value, LITERALS):
                return (TRUE if value else FALSE, literals_of(value))
            return (TRUE if value else FALSE, None)
        return (UNKNOWN, None)

    def _known(self, node, truth=UNKNOWN, values=None):
        """Record the truth of `node`, or its literal values (which decide
        its truth)."""
        if values is not None:
            truth = truth_of(values_of(values))
        if truth != UNKNOWN or values is not None:
            self._known_facts[node] = (truth, values)

    def _names_type_checking(self, name, value):
        """Whether the name `name`, whose value is the node `value`, is the
        `TYPE_CHECKING` of a typing module (see `TYPING_MODULES`)."""
        if any(
            value is self.analysis.constant(self.analysis.external(target))
            for target in TYPE_CHECKING_IMPORTS
        ):
            return True
        name = self._scope.mangle(name)
        scope = self.scopes.resolve(self._scope, name)
        return self.scopes.imported(scope, name) in TYPE_CHECKING_IMPORTS

    def _is_typing_module(self, expression, node):
        """Whether the expression `expression`, whose value is `node`, is an
        outside typing module (see `TYPING_MODULES`), whose `TYPE_CHECKING`
        is false: the value of its import, or a name that only imports of
        it bind."""
        if any(
            node is self.analysis.constant(self.analysis.external(module))
            for module in TYPING_MODULES
        ):
            return True
        if not isinstance(expression, ast.Name):
            return False
        name = self._scope.mangle(expression.id)
        scope = self.scopes.resolve(self._scope, name)
        return self.scopes.imported(scope, name) in TYPING_MODULES

    def _join(self, values):
        """A node that holds what any of `values` holds."""
        values = [value for value in values if value is not None]
        if len(values) <= 1:
            return values[0] if values else None
        joined = self.analysis.node()
        for value in values:
            self.analysis.add_edge(value, joined)
        return joined

    def _expr_Name(self, node):
        value, facts = self._read_name(node.id)
        self._known(node, *facts)
        if facts[0] == FALSE and self._names_type_checking(node.id, value):
            self._type_checking[node] = True
        return value

    def _expr_Attribute(self, node):
        base = self.expression(node.value)
        if base is None:
            return None
        if node.attr == "TYPE_CHECKING" and self._is_typing_module(node.value, base):
            self._known(node, values=literals_of(False))
            self._type_checking[node] = True
        value = self.analysis.node()
        attr = self._scope.mangle(node.attr)
        self.analysis.add_load(base, attr, value, self._caller, self._site(node))
        return value

    def _expr_Call(self, node):
        callee = self.expression(node.func)
        args, star = self._implicit_super_arguments(node), []
        nones = frozenset(
            index
            for index, arg in enumerate(node.args)
            if isinstance(arg, ast.Constant)
            and arg.value is None
            and not any(isinstance(a, ast.Starred) for a in node.args[:index])
        )
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                value = self.expression(arg.value)
                star.append((value, True))
                if value is not None:
                    # The interpreter builds a tuple or a list of the
                    # unpacked argument, whatever the callee: it asks its
                    # length (see `LENGTH_HINT`).
                    site = self._site(node)
                    self.analysis.add_length_hint(value, self._caller, site)
            elif star:
                star.append((self.expression(arg), False))
            else:
                args.append(self.expression(arg))
        keywords, double_star = [], []
        for keyword in node.keywords:
            value = self.expression(keyword.value)
            if keyword.arg is None:
                double_star.append(value)
            else:
                keywords.append((keyword.arg, value))
        self.class_test(node, args)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            if _is_str(node.func.value):
                self._format_fields(node, args, dict(keywords))
        if callee is None:
            # A call whose callee has no value: listed as unresolved.
            self.analysis.add_call(None, self._caller, [], [], None, self._site(node))
            return None
        # An import by a str literal gives the module (see builder.py),
        # recorded before the call, which acts at once on a constant callee.
        module = self.literal_import(node)
        if module is not None:
            self.analysis.literal_imports[self._site(node)] = module
        if nones:
            self.analysis.none_arguments[self._caller, self._site(node)] = nones
        result = self.analysis.node()
        self.analysis.add_call(
            callee,
            self._caller,
            args,
            keywords,
            result,
            self._site(node),
            star,
            double_star,
        )
        return result

    def _format_fields(self, node, args, keywords):
        """`"{0.name!r:>8}".format(...)` with a literal format: each field
        loads the attributes it names from its argument and converts the
        result (`!r` and `!a` with repr, `!s` with str, else with format and
        the field's spec). A field that indexes (`{0[key]}`) or that the
        call does not supply is skipped."""
        auto = 0
        for index, (first, attributes, conversion, spec) in enumerate(
            _format_fields(node.func.value.value)
        ):
            if first == "":
                first, auto = auto, auto + 1
            if isinstance(first, int):
                value = args[first] if first < len(args) else None
            else:
                value = keywords.get(first)
            if value is None or attributes is None:
                continue
            site = f"{self._site(node)}#{index}"
            for attr in attributes:
                loaded = self.analysis.node()
                self.analysis.add_load(value, attr, loaded, self._caller, site)
                value = loaded
            kind = FORMAT_CONVERSIONS.get(conversion, "format")
            spec = self.analysis.constant(self.analysis.const(spec))
            self.analysis.add_conversion(value, kind, self._caller, site, spec)

    def _implicit_super_arguments(self, node):
        """The arguments that `super()` without arguments takes from its
        function: the class around it (the `__class__` cell) and the first
        parameter. Empty for any other call."""
        if node.args or node.keywords:
            return []
        if not self._is_builtin_reference(node.func, "super"):
            return []
        function = self._function
        if function is None or not function.signature.positional:
            return []
        cell = self._load_name("__class__")
        first = function.parameters[function.signature.positional[0]]
        self.analysis.zero_argument_super.add(self._site(node))
        return [cell, first]

    def _expr_Lambda(self, node):
        self._known(node, TRUE)
        scope = self.scopes.scope_of(node)
        function = self._function_object(node, scope)
        with self._inside(scope, function):
            if self._returns_parameter(node.body):
                value = None
            else:
                value = self.expression(node.body)
        if value is not None:
            self.analysis.add_edge(value, function.return_node)
        return self.analysis.constant(function)

    def _expr_IfExp(self, node):
        return self.choice(node, self.expression)

    def _expr_BoolOp(self, node):
        return self.choice(node, self.expression)

    def condition(self, node):
        """Evaluate the condition `node` (of `if`, `while`, `assert`, a
        conditional expression, a comprehension, a case guard), whose truth
        Python tests: `__bool__`, else `__len__`. Which branch the builder
        walks depends on the syntax only (see `_truth`)."""
        value = self.expression(node)
        if value is not None:
            self.analysis.add_truth(value, self._caller, self._site(node))
        return value

    def choice(self, node, evaluate):
        """The value of a conditional expression or an `and`/`or` (`node`):
        the join of what `evaluate` gives for each part that may give the
        result, called within that part's branch of the flow (a `return`
        passes parameters through this way, see `ModuleBuilder._returned`).
        """
        if isinstance(node, ast.IfExp):
            return self._choose_arm(node, evaluate)
        return self._choose_operand(node, evaluate)

    def _choose_arm(self, node, evaluate):
        """An arm runs only if the test may have its truth; the other one is
        not walked (see *Code that cannot run* in the design)."""
        self.condition(node.test)
        test = self._truth(node.test)
        flow = self._flow
        base = flow.state
        values, ends, facts = [], [], []
        for arm, runs in ((node.body, test & TRUE), (node.orelse, test & FALSE)):
            if runs:
                flow.branch(base)
                self.narrow(node.test, arm is node.body)
                values.append(evaluate(arm))
                ends.append(flow.state)
                facts.append(self._facts(arm))
        flow.merge(base, ends)
        self._known(node, *_join_facts(facts))
        return self._join(values)

    def _choose_operand(self, node, evaluate):
        """`a or b` is `a` if it is true, else `b`; `a and b` is `a` if it is
        false, else `b`. An operand gives the result only if it may decide
        it (or is the last), and runs only if those before it may not
        decide it; the operands that cannot run are not walked."""
        decides = TRUE if isinstance(node.op, ast.Or) else FALSE
        goes_on = UNKNOWN ^ decides
        flow = self._flow
        base = flow.state
        values, ends, facts = [], [], []
        last = len(node.values) - 1
        for index, operand in enumerate(node.values):
            if index > 0:
                ends.append(flow.state)
                flow.branch(flow.state)
                self.narrow(node.values[index - 1], goes_on == TRUE)
            value = evaluate(operand)
            if index < last:
                # Python tests the truth of each operand but the last. A
                # returned parameter is passed through without a value (see
                # `ModuleBuilder._returned`): read it for the test.
                tested = value
                if tested is None and isinstance(operand, ast.Name):
                    tested = self.expression(operand)
                if tested is not None:
                    self.analysis.add_truth(tested, self._caller, self._site(operand))
            operand_truth, literals = self._facts(operand)
            if index == last:
                values.append(value)
                facts.append((operand_truth, literals))
                break
            if operand_truth & decides:
                values.append(value)
                # Only its values of that truth are the result.
                if literals is not None:
                    literals = frozenset(
                        entry for entry in literals if truth_of(entry[1:]) == decides
                    )
                facts.append((decides, literals))
            if not operand_truth & goes_on:
                break
        ends.append(flow.state)
        flow.merge(base, ends)
        self._known(node, *_join_facts(facts))
        return self._join(values)

    def _expr_NamedExpr(self, node):
        value = self.expression(node.value)
        facts = self._facts(node.value)
        self._bind(node.target.id, value, *facts)
        self._known(node, *facts)
        return value

    def _expr_Await(self, node):
        value = self.expression(node.value)
        if value is None:
            return None
        result = self.analysis.node()
        self.analysis.add_await(value, result, self._caller, self._site(node))
        return result

    def _expr_Yield(self, node):
        """`yield value`: the function yields `value`, and the expression is
        what is sent to the generator."""
        value = self.expression(node.value) if node.value is not None else None
        function = self._function
        if function is None or function.yield_node is None:
            return None
        if value is not None:
            self.analysis.add_edge(value, function.yield_node)
        return function.sent_node

    def _expr_YieldFrom(self, node):
        value = self.expression(node.value)
        function = self._function
        if value is None or function is None or function.yield_node is None:
            return None
        result = self.analysis.node()
        self.analysis.add_yield_from(
            value, function, result, self._caller, self._site(node)
        )
        return result

    def _expr_BinOp(self, node):
        # Long chains such as `a + b + c + ...` nest on the left; walk them in
        # a loop, so that they do not exhaust the Python stack.
        chain = []
        while isinstance(node, ast.BinOp):
            chain.append(node)
            node = node.left
        value = self.expression(node)
        for operation in reversed(chain):
            right = self.expression(operation.right)
            self._binop_operands[operation] = (value, right)
            value = self._operator(value, right, operation, inplace=False)
        return value

    def _expr_Constant(self, node):
        # Its facts are those of its value (see `_facts`).
        value = node.value
        if isinstance(value, (str, bytes, int)) and not isinstance(value, bool):
            return self.analysis.constant(self.analysis.const(value))
        return None

    def _expr_UnaryOp(self, node):
        value = _int_literal(node)
        if value is not None:
            self._known(node, values=literals_of(value))
            return self.analysis.constant(self.analysis.const(value))
        operand = self.expression(node.operand)
        if isinstance(node.op, ast.Not):
            if operand is not None:
                self.analysis.add_truth(operand, self._caller, self._site(node))
            if node.operand in self._type_checking:
                self._type_checking[node] = not self._type_checking[node.operand]
            # A bool, whatever the operand.
            truth = self._truth(node.operand)
            results = {False} if truth & TRUE else set()
            if truth & FALSE:
                results.add(True)
            self._known(node, values=literals_of(*results))
        method = _UNARY_OPERATORS.get(type(node.op))
        if operand is None or method is None:
            return None
        result = self.analysis.node()
        self.analysis.add_operator(
            operand,
            None,
            method,
            None,
            False,
            result,
            self._caller,
            self._site(node),
            unary=True,
        )
        return result

    def _expr_Compare(self, node):
        """Each comparison calls the special method of its left operand and
        the reflected one of its right operand, and gives what they return
        (`a < b < c` gives the result of either comparison); Python tests
        the truth of each result but the last to decide whether to go on.
        `in` calls `__contains__` of the right operand and tests the truth
        of its result; `in`, `not in`, `is` and `is not` give bools, which
        are not tracked."""
        left = self.expression(node.left)
        results = []
        # A comparison after the first runs only where those before it
        # held, and not at all after one that cannot hold.
        flow = self._flow
        base, ends, outcomes = flow.state, [], set()
        previous = node.left
        last = len(node.ops) - 1
        for index, (operator, comparator) in enumerate(zip(node.ops, node.comparators)):
            if index > 0:
                ends.append(flow.state)
                flow.branch(flow.state)
            right = self.expression(comparator)
            outcome = self._comparison(operator, previous, comparator)
            # Each comparison of a chain is its own construct, from its left
            # operand to its right one: the whole expression for one link.
            site = self._span(previous, comparator)
            previous = comparator
            if outcomes is not None:
                outcomes = None if outcome is None else outcomes | outcome
            if type(operator) in _COMPARISONS:
                result = self.rich_comparison(left, right, operator, site)
                if result is not None:
                    results.append(result)
                    if index < last:
                        self.analysis.add_truth(result, self._caller, site)
            elif isinstance(operator, (ast.In, ast.NotIn)):
                # A container that is not tracked is searched too.
                container = right if right is not None else self.analysis.node()
                contained = self.analysis.node()
                self.analysis.add_operator(
                    container,
                    left,
                    "__contains__",
                    None,
                    False,
                    contained,
                    self._caller,
                    site,
                )
                self.analysis.add_truth(contained, self._caller, site)
            left = right
            if outcome == {False}:
                # The chain is false here, whatever came before.
                outcomes = {False} if outcomes is not None else None
                break
        ends.append(flow.state)
        flow.merge(base, ends)
        if outcomes is not None:
            self._known(node, values=literals_of(*outcomes))
        return self._join(results)

    def rich_comparison(self, left, right, operator, site):
        """The node of what `left <operator> right` gives, for a rich
        comparison (`operator` an `ast.Lt`...): it calls the special method
        of the left operand and the reflected one of the right operand.
        Either operand may be None, if it is not tracked; None if neither
        is."""
        if left is None and right is None:
            return None
        method, reflected = _COMPARISONS[type(operator)]
        result = self.analysis.node()
        self.analysis.add_operator(
            left, right, method, reflected, False, result, self._caller, site
        )
        return result

    def _comparison(self, operator_node, left, right):
        """The bools that `left <operator> right` may give, if decided by
        the literal values of the operands; else None."""
        lefts = values_of(self._literals(left) or ())
        if not lefts:
            return None
        if isinstance(operator_node, (ast.In, ast.NotIn)):
            members = self._members(right)
            if members is None:
                return None
            outcome = {any(value == member for member in members) for value in lefts}
            if isinstance(operator_node, ast.NotIn):
                outcome = {not result for result in outcome}
            return outcome
        rights = values_of(self._literals(right) or ())
        if not rights:
            return None
        compare = _LITERAL_COMPARISONS[type(operator_node)]
        if compare in (operators.is_, operators.is_not):
            # The identity of other literals depends on the interpreter.
            if not all(_is_singleton(value) for value in lefts + rights):
                return None
        try:
            return {bool(compare(a, b)) for a in lefts for b in rights}
        except TypeError:
            return None

    def _members(self, node):
        """The literal values of the elements of a tuple, list or set
        display whose elements each have one literal value; else None."""
        if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return None
        members = []
        for element in node.elts:
            literals = self._literals(element)
            if literals is None or len(literals) != 1:
                return None
            members.extend(values_of(literals))
        return members

    def _expr_JoinedStr(self, node):
        """An f-string converts each value to str, passing the format spec
        to `__format__`. Without values, it is a str constant."""
        if all(isinstance(value, ast.Constant) for value in node.values):
            text = "".join(value.value for value in node.values)
            self._known(node, values=literals_of(text))
            return self.analysis.constant(self.analysis.const(text))
        for value in node.values:
            if not isinstance(value, ast.FormattedValue):
                continue
            operand = self.expression(value.value)
            if value.format_spec is not None:
                spec = self.expression(value.format_spec)
            else:
                spec = self.analysis.constant(self.analysis.const(""))
            if operand is not None:
                kind = _CONVERSIONS.get(value.conversion, "format")
                site = self._site(value)
                self.analysis.add_conversion(operand, kind, self._caller, site, spec)
        return None

    def _expr_Subscript(self, node):
        base, index = self._subscript_parts(node)
        if base is None:
            return None
        result = self.analysis.node()
        self._subscript(base, index, result, None, node)
        return result

    def _expr_Tuple(self, node):
        """A tuple, list or set display. Elements after an unpacked one have
        no known position."""
        kind = _DISPLAYS[type(node)]
        positional = kind != "set"
        unpacked = any(isinstance(elt, ast.Starred) for elt in node.elts)
        if kind == "tuple" and not unpacked:
            self._known(node, TRUE if node.elts else FALSE)
        length = len(node.elts) if positional and not unpacked else None
        container = self.analysis.container(kind, self._site(node), length)
        # The nodes of what the display stores without a position, and of
        # what a set hashes among them and compares with all of them.
        unordered, hashed = [], []
        for index, elt in enumerate(node.elts):
            if isinstance(elt, ast.Starred) and kind == "set":
                entering = self._entering_keys(elt.value)
                if entering is not None:
                    unordered.extend(entering)
                    hashed.append(entering[0])
                continue
            if isinstance(elt, ast.Starred):
                positional = False
                # A list or tuple display extends a list with the
                # unpacked iterable, which asks its length.
                elements = self._elements_of(elt.value, length_hint=True)
                if elements is not None:
                    unordered.append(elements)
                continue
            value = self.expression(elt)
            if value is None:
                continue
            if positional:
                self.analysis.add_edge(value, self.analysis.element(container, index))
            else:
                unordered.append(value)
                hashed.append(value)
        for value in unordered:
            self.analysis.add_edge(value, self.analysis.unknown(container))
        if kind == "set" and hashed:
            keys, stored = self.analysis.node(), self.analysis.node()
            for value in hashed:
                self.analysis.add_edge(value, keys)
            for value in unordered:
                self.analysis.add_edge(value, stored)
            self.analysis.add_hash(keys, self._caller, self._site(node), stored)
        return self.analysis.constant(container)

    def _entering_keys(self, iterable):
        """Evaluate the expression `iterable`, unpacked into a set, and
        return the nodes of its elements that the set hashes and of those
        whose hashes it reuses (see `Containers.entering_keys`), or None."""
        value = self.expression(iterable)
        if value is None:
            return None
        site = self._site(iterable)
        self.analysis.iterated_expressions.add((self._caller, site))
        construct = ("unpacked", site)
        return self.analysis.entering_keys(value, construct, self._caller, site)

    _expr_List = _expr_Tuple
    _expr_Set = _expr_Tuple

    def _expr_Dict(self, node):
        container = self.analysis.container("dict", self._site(node))
        for key, value in zip(node.keys, node.values):
            # Each key is evaluated before its value.
            key_node = None if key is None else self.expression(key)
            value_node = self.expression(value)
            if key is None:
                # {**mapping}
                if value_node is not None:
                    site = self._site(value)
                    self.analysis.add_dict_items(
                        container, value_node, self._caller, site
                    )
                    self.analysis.iterated_expressions.add((self._caller, site))
                continue
            self.analysis.write_keyed(container, key_node, value_node)
            if key_node is not None:
                stored = self.analysis.keys(container)
                self.analysis.add_hash(key_node, self._caller, self._site(key), stored)
        return self.analysis.constant(container)

    def _comprehension(self, node):
        """The container that a comprehension builds; a generator
        expression is a container of kind `generator`, or `async_generator`
        if it awaits (see `Scope.asynchronous`)."""
        scope = self.scopes.scope_of(node)
        kind = _COMPREHENSIONS[type(node)]
        if kind == "generator" and scope.asynchronous:
            kind = "async_generator"
        container = self.analysis.container(kind, self._site(node))
        generators = node.generators
        # The first iterable is evaluated in the enclosing scope.
        first = generators[0]
        elements = self._elements_of(first.iter, bool(first.is_async))
        with self._inside(scope, self._function):
            for index, generator in enumerate(generators):
                if index > 0:
                    is_async = bool(generator.is_async)
                    elements = self._elements_of(generator.iter, is_async)
                self._assign(generator.target, elements)
                for condition in generator.ifs:
                    self.condition(condition)
            if isinstance(node, ast.DictComp) and node.value is None:
                # `{**mapping for ...}` (PEP 798): the items of each mapping.
                mapping = self.expression(node.key)
                if mapping is not None:
                    site = self._site(node.key)
                    self.analysis.add_dict_items(container, mapping, self._caller, site)
                    self.analysis.iterated_expressions.add((self._caller, site))
            elif isinstance(node, ast.DictComp):
                key = self.expression(node.key)
                value = self.expression(node.value)
                self.analysis.write_keyed(container, key, value)
                if key is not None:
                    stored = self.analysis.keys(container)
                    site = self._site(node.key)
                    self.analysis.add_hash(key, self._caller, site, stored)
            elif isinstance(node.elt, ast.Starred) and kind == "set":
                # `{*iterable for ...}`: the elements of each one, hashed
                # where they come from no set or dict.
                entering = self._entering_keys(node.elt.value)
                if entering is not None:
                    for value in entering:
                        self.analysis.add_edge(value, self.analysis.unknown(container))
                    stored = self.analysis.elements(container)
                    site = self._site(node.elt.value)
                    self.analysis.add_hash(entering[0], self._caller, site, stored)
            elif isinstance(node.elt, ast.Starred):
                # `[*iterable for ...]` (PEP 798): the elements of each one.
                iterable = self.expression(node.elt.value)
                if iterable is not None:
                    target = self.analysis.unknown(container)
                    site = self._site(node.elt)
                    self.analysis.add_iteration(iterable, target, self._caller, site)
            else:
                value = self.expression(node.elt)
                if value is not None:
                    self.analysis.add_edge(value, self.analysis.unknown(container))
                    if kind == "set":
                        stored = self.analysis.elements(container)
                        site = self._site(node.elt)
                        self.analysis.add_hash(value, self._caller, site, stored)
        return self.analysis.constant(container)

    _expr_ListComp = _comprehension
    _expr_SetComp = _comprehension
    _expr_DictComp = _comprehension
    _expr_GeneratorExp = _comprehension

    def _elements_of(self, iterable, is_async=False, length_hint=False):
        """Evaluate the expression `iterable` and return a node with what
        iterating over it (with `async for` if `is_async`) gives, or None;
        with `length_hint`, the iteration first asks its length."""
        value = self.expression(iterable)
        if value is None:
            return None
        elements = self.analysis.node()
        site = self._site(iterable)
        if length_hint:
            self.analysis.add_length_hint(value, self._caller, site)
        self.analysis.add_iteration(value, elements, self._caller, site, is_async)
        self.analysis.iterated_expressions.add((self._caller, site))
        return elements

    def _subscript_parts(self, node):
        """Evaluate the value and the index of a subscript. Return the node of
        the value and either the key node or a `Bounds` for a slice."""
        base = self.expression(node.value)
        if isinstance(node.slice, ast.Slice):
            return base, Bounds(self._slice_bounds(node.slice))
        return base, self.expression(node.slice)

    def _slice_bounds(self, node):
        """Evaluate the parts of a slice and return `(start, stop)` if both
        are int literals or absent and there is no step; else None."""
        parts = [node.lower, node.upper, node.step]
        for part in parts:
            if part is not None:
                self.expression(part)
        if node.step is not None:
            return None
        bounds = []
        for part in (node.lower, node.upper):
            value = None if part is None else _int_literal(part)
            if part is not None and value is None:
                return None
            bounds.append(value)
        return tuple(bounds)

    def _subscript(self, base, index, dst, src, node, delete=False):
        """dst ⊇ base[index] (if `dst`), base[index] ⊇ src (if `src`),
        `del base[index]` (if `delete`)."""
        if dst is None and src is None and not delete:
            return
        site, caller = self._site(node), self._caller
        if isinstance(index, Bounds):
            bounds = index.bounds
            self.analysis.add_slice(base, bounds, dst, src, caller, site, delete)
        else:
            self.analysis.add_subscript(base, index, dst, src, caller, site, delete)

    def _operator(self, left, right, node, inplace=True):
        """The node of the result of the binary operator of `node` (a BinOp
        or an AugAssign) applied to `left` and `right`."""
        if left is None and right is None:
            return None
        name = _OPERATORS[type(node.op)]
        if isinstance(node.op, ast.Mod) and left is not None and right is not None:
            # `fmt % items` formats where `fmt` holds a str (see `add_percent`).
            self.analysis.add_percent(left, right, self._caller, self._site(node))
        result = self.analysis.node()
        self.analysis.add_operator(
            left,
            right,
            f"__{name}__",
            f"__r{name}__",
            inplace,
            result,
            self._caller,
            self._site(node),
        )
        return result


_COMPREHENSIONS = {
    ast.ListComp: "list",
    ast.SetComp: "set",
    ast.DictComp: "dict",
    ast.GeneratorExp: "generator",
}


class Bounds:
    """The index of a slice: `bounds` is `(start, stop)`, or None if they
    are not known (see `ModuleBuilder._slice_bounds`)."""

    __slots__ = ("bounds",)

    def __init__(self, bounds):
        self.bounds = bounds


def _dynamic_operands(operands):
    """The value nodes of the `(expression, node)` pairs `operands` that may
    not be an exact str: not a constant and not an f-string that builds a
    new str. A single-field f-string gives None."""
    found = []
    for expression, node in operands:
        if isinstance(expression, ast.Constant):
            continue
        if isinstance(expression, ast.JoinedStr):
            values = expression.values
            # More than one part (a literal part or two fields) builds a
            # new str; a literal alone is a constant.
            if len(values) != 1 or isinstance(values[0], ast.Constant):
                continue
            node = None
        found.append(node)
    return found


def _join_facts(facts):
    """The facts of a value that may be any of those with `facts`."""
    truth, values = 0, frozenset()
    for bits, literals in facts:
        truth |= bits
        values = None if values is None or literals is None else values | literals
    return (truth or UNKNOWN, values)


def _is_singleton(value):
    return any(value is singleton for singleton in _SINGLETONS)


def _int_literal(node):
    """The value of an int literal, possibly negated, or None."""
    sign = 1
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        sign, node = -1, node.operand
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return sign * node.value
    return None

from pycg.machinery.pointers import NamePointer, LiteralPointer

class DefinitionManager(object):
    LIT_TYPE        = "LITERAL"
    FUN_TYPE        = "FUNCTION"
    NAME_TYPE       = "NAME"

    RETURN_NAME     = "<**RETURN**>"

    def __init__(self):
        self.defs = {}

    def _update_defi(self, defi, info):
        if not info["value"]:
            print ("empty value found")
        if info["type"] == DefinitionManager.LIT_TYPE:
            defi.get_lit_pointer().add(info["value"])
        elif info["type"] == DefinitionManager.NAME_TYPE:
            defi.merge(info["value"])
        else:
            raise Exception("Unknown type")

    def create(self, ns, def_type):
        self.defs[ns] = Definition(ns, def_type)
        return self.defs[ns]

    def assign(self, ns, defi):
        # maybe deep copy
        self.defs[ns] = Definition(ns, defi.get_type())
        self.defs[ns].get_name_pointer().add(defi.get_ns())
        for cnt, arg in defi.get_name_pointer().get_args().items():
            self.defs[ns].get_name_pointer().add_arg(cnt, arg)

        # if it is a function def, we need to create a return pointer
        if defi.is_function_def():
            return_ns = "{}.{}".format(ns, self.RETURN_NAME)
            self.defs[return_ns] = Definition(return_ns, Definition.NAME_DEF)
            self.defs[return_ns].get_name_pointer().add("{}.{}".format(defi.get_ns(), self.RETURN_NAME))

        return self.defs[ns]

    def get(self, ns):
        if ns in self.defs:
            return self.defs[ns]

    def handle_function_def(self, parent_ns, fn_name, args, defaults):
        full_ns = "{}.{}".format(parent_ns, fn_name)
        defi = self.get(full_ns)
        if not defi:
            defi = self.create(full_ns, Definition.FUN_DEF)
        name_pointer = defi.get_name_pointer()

        for pos, arg in enumerate(args):
            arg_ns = "{}.{}".format(full_ns, arg)
            name_pointer.add_arg(pos, arg_ns)

            arg_def = self.get(arg_ns)
            if not arg_def:
                arg_def = self.create(arg_ns, Definition.NAME_DEF)
            # no default
            if not defaults.get(pos, None):
                continue

            self._update_defi(arg_def, defaults[pos])

        return_ns = "{}.{}".format(full_ns, self.RETURN_NAME)
        self.create(return_ns, Definition.NAME_DEF)

        return defi

    def update_def_args(self, defi, args):
        for pos, arg in args.items():
            if not arg["value"]:
                print ("empty value found")
            if defi.is_function_def():
                pos_arg_names = defi.get_name_pointer().get_arg(pos)
                # if arguments for this position exist update their namespace
                for name in pos_arg_names:
                    arg_def = self.get(name)
                    if not arg_def:
                        arg_def = self.create(name)
                    if arg["type"] == DefinitionManager.LIT_TYPE:
                        arg_def.get_lit_pointer().add(arg["value"])
                    elif arg["type"] == DefinitionManager.NAME_TYPE:
                        arg_def.get_name_pointer().add(arg["value"].get_ns())
                    else:
                        raise Exception("unkown type")
            else:
                # otherwise, add an argument to this definition
                if arg["type"] == DefinitionManager.LIT_TYPE:
                    defi.get_name_pointer().add_lit_arg(pos, arg["value"])
                elif arg["type"] == DefinitionManager.NAME_TYPE:
                    defi.get_name_pointer().add_arg(pos, arg["value"].get_ns())
                else:
                    raise Exception("unkown type")

    def handle_assign(self, targetns, value):
        defi = self.get(targetns)
        if not defi:
            defi = self.create(targetns, Definition.NAME_DEF)

        if not value["value"]:
            print ("empty value found")
        if value["type"] == DefinitionManager.LIT_TYPE:
            defi.get_lit_pointer().add(value["value"])
        elif value["type"] == DefinitionManager.NAME_TYPE:
            defi.merge(value["value"])
            defi.get_name_pointer().add(value["value"].get_ns())
        else:
            raise Exception("Unknown type")

        return defi

    def get_arg_defs(self, ns):
        # expects a function ns
        return [self.defs[list(x)[0]] for x in self.get(ns).get_name_pointer().get_args().values()]

    def transitive_closure(self):
        closured = {}
        def dfs(defi):
            name_pointer = defi.get_name_pointer()
            new_set = set()
            # bottom
            if not name_pointer.get():
                new_set.add(defi.get_ns())

            for name in name_pointer.get():
                new_set = new_set.union(dfs(self.defs[name]))

            closured[defi.get_ns()] = new_set
            return closured[defi.get_ns()]

        for ns, current_def in self.defs.items():
            dfs(current_def)

        return closured

    def complete_definitions(self):
        # THE MOST expensive part of this tool's process
        # TODO: IMPROVE COMPLEXITY
        for i in range(len(self.defs)):
            changed_something = False
            for ns, current_def in self.defs.items():
                # the name pointer of the definition we're currently iterating
                current_name_pointer = current_def.get_name_pointer()
                # iterate the names the current definition points to items
                for name in current_name_pointer.get():
                    # get the name pointer of the points to name
                    pointsto_name_pointer = self.defs[name].get_name_pointer()
                    # iterate the arguments of the definition we're currently iterating
                    for pos, arg in current_name_pointer.get_args().items():
                        pointsto_args = pointsto_name_pointer.get_arg(pos)
                        if not pointsto_args:
                            # Check existence
                            for item in arg:
                                if not item in pointsto_name_pointer.get():
                                    changed_something = True

                            pointsto_name_pointer.add_arg(pos, arg)
                            continue
                        for pointsto_arg in pointsto_args:
                            if not self.defs.get(pointsto_arg, None):
                                continue
                            pointsto_arg_def = self.defs[pointsto_arg].get_name_pointer()
                            # sometimes we may end up with a cycle
                            if pointsto_arg in arg:
                                arg.remove(pointsto_arg)

                            for item in arg:
                                if not item in pointsto_arg_def.get():
                                    changed_something = True
                            pointsto_arg_def.add_set(arg)
            if not changed_something:
                break


class Definition(object):
    FUN_DEF     = "FUNCTIONDEF"
    NAME_DEF    = "NAMEDEF"
    MOD_DEF     = "MODULEDEF"

    def __init__(self, fullns, def_type):
        self.fullns = fullns
        self.points_to = {
            "lit": LiteralPointer(),
            "name": NamePointer()
        }
        self.def_type = def_type

    def get_type(self):
        return self.def_type

    def is_function_def(self):
        return self.def_type == self.FUN_DEF

    def get_lit_pointer(self):
        return self.points_to["lit"]

    def get_name_pointer(self):
        return self.points_to["name"]

    def get_name(self):
        return self.fullns.split(".")[-1]

    def get_ns(self):
        return self.fullns

    def merge(self, to_merge):
        for name, pointer in to_merge.points_to.items():
            self.points_to[name].merge(pointer)

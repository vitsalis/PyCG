from base import TestBase
from pycg.machinery.definitions import Definition, DefinitionManager, DefinitionError
from pycg.machinery.pointers import LiteralPointer

class DefinitionManagerTest(TestBase):
    def test_create(self):
        dm = DefinitionManager()

        dm.create("adefi", Definition.NAME_DEF)

        defi = dm.get("adefi")
        self.assertEqual(defi.get_type(), Definition.NAME_DEF)
        self.assertEqual(defi.get_ns(), "adefi")

        # only non empty strings allowed
        with self.assertRaises(DefinitionError):
            dm.create("", Definition.NAME_DEF)

        with self.assertRaises(DefinitionError):
            dm.create(1, Definition.NAME_DEF)

        # no duplicate defs
        with self.assertRaises(DefinitionError):
            dm.create("adefi", Definition.NAME_DEF)

        # we should provide a valid type
        with self.assertRaises(DefinitionError):
            dm.create("adefi2", "notavalidtype")

    def test_assign(self):
        dm = DefinitionManager()
        defi1 = dm.create("defi1", Definition.NAME_DEF)
        defi1.get_name_pointer().add("item1")
        defi1.get_name_pointer().add("item2")
        defi1.get_name_pointer().add_arg(0, "arg")

        defi2 = dm.assign("defi2", defi1)
        # should have the correct ns
        self.assertEqual(defi2.get_ns(), "defi2")
        # values should be merged
        self.assertEqual(defi2.get_type(), Definition.NAME_DEF)
        self.assertEqual(defi2.get_name_pointer().get(), set(["item1", "item2"]))
        self.assertEqual(defi2.get_name_pointer().get_arg(0), set(["arg"]))

        # for function defs a return def should be created too
        fndefi = dm.create("fndefi", Definition.FUN_DEF)
        fndefi2 = dm.assign("fndefi2", fndefi)
        return_def = dm.get("{}.{}".format("fndefi2", DefinitionManager.RETURN_NAME))
        self.assertIsNotNone(return_def)
        self.assertEqual(return_def.get_name_pointer().get(), set(["{}.{}".format("fndefi", DefinitionManager.RETURN_NAME)]))


    def test_handle_function_def(self):
        # handle parent definition
        parent_ns = "root"
        fn_name = "function"
        fn_ns = "{}.{}".format(parent_ns, fn_name)
        args = ["arg1", "arg2", "arg3"]

        dm = DefinitionManager()
        dm.create("root", Definition.NAME_DEF)
        default_defi = dm.create("root.function2", Definition.FUN_DEF)

        defaults = {
            1: {"type": DefinitionManager.NAME_TYPE, "value": default_defi},
            2: {"type": DefinitionManager.LIT_TYPE, "value": "10"}
        }

        dm.handle_function_def(parent_ns, fn_name, args, defaults)

        # a definition for the function should be created
        fn_def = dm.get(fn_ns)
        self.assertIsNotNone(fn_def)
        # definitions should be created for the arguments
        for cnt, arg in enumerate(args):
            arg_ns = "{}.{}".format(fn_ns, arg)
            self.assertIsNotNone(dm.get(arg_ns))
            self.assertEqual(fn_def.get_name_pointer().get_arg(cnt), set([arg_ns]))

        # defaults should be assigned to function definitions
        name_arg = dm.get("{}.{}".format(fn_ns, "arg2"))
        lit_arg = dm.get("{}.{}".format(fn_ns, "arg3"))

        self.assertEqual(name_arg.get_name_pointer().get(), set([default_defi.get_ns()]))
        self.assertEqual(lit_arg.get_lit_pointer().get(), set([LiteralPointer.STR_LIT]))

    def test_update_def_args(self):
        dm = DefinitionManager()
        parent_ns = "root"
        fn_name = "function"
        var_name = "variable"
        arg_name = "arg_name"
        args = ["arg1", "arg2"]
        defaults = {}

        fn_ns = "{}.{}".format(parent_ns, fn_name)
        var_ns = "{}.{}".format(parent_ns, var_name)
        arg_ns = "{}.{}".format(parent_ns, arg_name)

        dm.handle_function_def(parent_ns, fn_name, args, defaults)
        fn_def = dm.get(fn_ns)
        var_def = dm.create(var_ns, Definition.NAME_DEF)
        arg_def = dm.create(arg_ns, Definition.NAME_DEF)

        values = {
            0: {"type": DefinitionManager.NAME_TYPE, "value": arg_def},
            1: {"type": DefinitionManager.LIT_TYPE, "value": "10"}
        }


        # update def args for name
        dm.update_def_args(var_def, values)
        self.assertEqual(var_def.get_name_pointer().get_arg(0), set([arg_def.get_ns()]))
        self.assertEqual(var_def.get_name_pointer().get_arg(1), set([LiteralPointer.STR_LIT]))

        # update def args for function
        dm.update_def_args(fn_def, values)
        arg1_def = dm.get("{}.{}".format(fn_ns, args[0]))
        arg2_def = dm.get("{}.{}".format(fn_ns, args[1]))
        self.assertEqual(arg1_def.get_name_pointer().get(), set([arg_def.get_ns()]))
        self.assertEqual(arg2_def.get_lit_pointer().get(), set([LiteralPointer.STR_LIT]))

    def test_handle_assign(self):
        dm = DefinitionManager()
        to_assign = dm.create("to_assign", Definition.NAME_DEF)

        name_info = {"type": DefinitionManager.NAME_TYPE, "value": to_assign}
        lit_info = {"type": DefinitionManager.LIT_TYPE, "value": "10"}

        dm.handle_assign("var1", name_info)
        dm.handle_assign("var2", lit_info)

        var1_def = dm.get("var1")
        var2_def = dm.get("var2")

        self.assertEqual(var1_def.get_name_pointer().get(), set([to_assign.get_ns()]))
        self.assertEqual(var1_def.get_lit_pointer().get(), set())

        self.assertEqual(var2_def.get_lit_pointer().get(), set([LiteralPointer.STR_LIT]))
        self.assertEqual(var2_def.get_name_pointer().get(), set())

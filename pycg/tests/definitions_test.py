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

        dm = DefinitionManager()
        dm.create("root", Definition.NAME_DEF)

        dm.handle_function_def(parent_ns, fn_name)

        # a definition for the function should be created
        fn_def = dm.get(fn_ns)
        self.assertIsNotNone(fn_def)


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

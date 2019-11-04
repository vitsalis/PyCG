from base import TestBase

from pycg.machinery.pointers import Pointer, NamePointer,\
    LiteralPointer, PointerError

class PointerTest(TestBase):
    def test_merge(self):
        pointer = Pointer()
        pointer2 = Pointer()
        pointer.add("smth")
        pointer.add("smth2")
        pointer2.add("smth3")
        pointer2.add("smth2")

        pointer.merge(pointer2)

        self.assertEqual(pointer.get(), set(["smth", "smth2", "smth3"]))
        self.assertEqual(pointer2.get(), set(["smth2", "smth3"]))

        pointer3 = Pointer()
        pointer.merge(pointer3)
        self.assertEqual(pointer.get(), set(["smth", "smth2", "smth3"]))
        self.assertEqual(pointer3.get(), set())

    def test_literal_pointer(self):
        pointer = LiteralPointer()
        # assert that for string values, we just include
        # that the literal points to a str or int
        clone = set([LiteralPointer.STR_LIT])
        pointer.add("something")
        self.assertEqual(pointer.get(), clone)
        pointer.add("else")
        self.assertEqual(pointer.get(), clone)

        clone.add(LiteralPointer.INT_LIT)
        pointer.add(1)
        self.assertEqual(pointer.get(), clone)
        pointer.add(100)
        self.assertEqual(pointer.get(), clone)

        clone.add(LiteralPointer.UNK_LIT)
        pointer.add({})
        self.assertEqual(pointer.get(), clone)

    def test_name_pointer(self):
        pointer = NamePointer()
        clone = {}

        self.assertEqual(pointer.get_args(), clone)

        clone[0] = set(["something", "set", "addition"])
        clone[1] = set(["somethingelse"])

        pointer.add_arg(0, "something")
        pointer.add_arg(1, "somethingelse")
        pointer.add_arg(0, set(["set", "addition"]))

        with self.assertRaises(PointerError):
            pointer.add_arg("NaN", "fail")

        self.assertEqual(pointer.get_args(), clone)

        clone[2] = set([LiteralPointer.INT_LIT])
        pointer.add_lit_arg(2, 2)
        pointer.add_lit_arg(2, 3)
        self.assertEqual(pointer.get_args(), clone)

        clone[1].add(LiteralPointer.STR_LIT)
        pointer.add_lit_arg(1, "str")
        self.assertEqual(pointer.get_args(), clone)

        with self.assertRaises(PointerError):
            pointer.add_lit_arg("NaN", "fail")

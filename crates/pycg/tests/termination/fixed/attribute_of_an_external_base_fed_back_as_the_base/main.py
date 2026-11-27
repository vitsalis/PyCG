import unittest
bases = [unittest.TestCase]
class C(bases[0]): pass
bases[0] = C.failureException

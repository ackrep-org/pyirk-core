import unittest
import sys
import os
from os.path import join as pjoin
# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception
import pykerl as pk

activate_ips_on_exception()

current_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
TEST_DATA_PATH = pjoin(current_dir, "test_data")


# noinspection PyPep8Naming
class TestCore(unittest.TestCase):
    def setUp(self):
        pass

    # mark tests which only work for the "old core"
    def test_core1(self):
        m = pk.Manager(pjoin(TEST_DATA_PATH, "test1.yml"))
        self.assertTrue(len(m.raw_stmts_dict) > 3)
        self.assertIn("R1", pk.ds.builtin_entities)
        self.assertIn("R2", pk.ds.builtin_entities)

        # TODO: decide whether in versioned_entities the object should be the same or a copy.
        self.assertEqual(pk.ds.versioned_entities["I1001"].get(0), pk.ds.items.I1001)
        q = m.raw_stmts_dict[0]
        # IPS()

    def test_patchy_dict1(self):
        d = pk.PatchyPseudoDict()

        self.assertRaises(TypeError, d.set, ("a", "b"))
        d.set(10, "A")
        d.set(20, "wrong value")
        d.set(20, "B")
        d.set(30, "C")
        self.assertRaises(ValueError, d.set, 10, "A2")
        self.assertEqual(d.get(10), "A")
        self.assertEqual(d.get(11), "A")
        self.assertEqual(d.get(19), "A")
        self.assertEqual(d.get(21), "B")
        self.assertEqual(d.get(31), "C")
        self.assertEqual(d.get(800), "C")
        self.assertRaises(KeyError, d.get, 9)

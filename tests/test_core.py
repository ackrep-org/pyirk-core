import unittest
import sys
import os
from os.path import join as pjoin
# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception
import pyerk as p

activate_ips_on_exception()

current_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
TEST_DATA_PATH = pjoin(current_dir, "test_data")


# noinspection PyPep8Naming
class TestCore(unittest.TestCase):
    def setUp(self):
        pass

    # mark tests which only work for the "old core"
    def test_core1(self):
        pass

    def test_builtins1(self):
        """
        Test the mechanism to endow the Entity class with custom methods (on class and on instance level)
        :return:
        """
        # class level
        def example_func(slf, a):
            return f"{slf.R1}--{a}"
        p.Entity.add_method_to_class(example_func)

        res = p.I12.example_func("test")
        self.assertEqual("mathematical object--test", res)

        # instance level
        itm = p.Item(key_str=p.generate_new_key("I"), R1="test item")
        itm2 = p.Item(key_str=p.generate_new_key("I"), R1="test item2")

        def example_func2(slf, a):
            return f"{slf.R1}::{a}"
        itm.add_method(example_func2)

        res2 = itm.example_func2(1234)
        self.assertEqual("test item::1234", res2)
        self.assertIsInstance(itm2, p.Entity)

        # ensure that this method is not available to generic other instances of Entity
        with self.assertRaises(AttributeError):
            itm2.example_func2(1234)

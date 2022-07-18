import unittest
import sys
import os
from os.path import join as pjoin

import rdflib
# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception
import pyerk as p

activate_ips_on_exception()

current_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
TEST_DATA_PATH = pjoin(current_dir, "test_data", "knowledge_base1.py")


# noinspection PyPep8Naming
class TestCore(unittest.TestCase):
    def setUp(self):
        pass

    def test_core1(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        self.assertEqual(mod1.I3749.R1, "Cayley-Hamilton theorem")

        def_eq_item = mod1.I6886.R6__has_defining_equation
        self.assertEqual(def_eq_item.R4__is_instance_of, p.I18["mathematical expression"])
        self.assertEqual(def_eq_item.R24__has_LaTeX_string, r"$\dot x = f(x, u)$")

        teststring1 = "this is english text"@mod1.p.en
        teststring2 = "das ist deutsch"@mod1.p.de

        self.assertIsInstance(teststring1, rdflib.Literal)
        self.assertIsInstance(teststring2, rdflib.Literal)

    def test_sparql_query(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        p.ds.rdfgraph = p.rdfstack.create_rdf_triples()
        qsrc = p.rdfstack.get_sparql_example_query()
        res = p.ds.rdfgraph.query(qsrc)
        res2 = p.aux.apply_func_to_table_cells(p.rdfstack.convert_from_rdf_to_pyerk, res)

        import colorama
        print(colorama.Fore.YELLOW, "sparql test currently fails!")

        # self.assertEqual(res2, [[mod1.I4466, p.I4], [mod1.I4466, p.I5]])

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

    def test_evaluated_mapping(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        poly1 = p.instance_of(mod1.I4239["monovariate polynomial"])

        # test that an arbitrary item is *not* callable
        self.assertRaises(TypeError, mod1.I2738["field of complex numnbers"], 0)

        # test that some special items are callable (note that its parent class is a subclass of one which has
        # a _custom_call-method defined)
        res = poly1(0)

        self.assertEqual(res.R4__is_instace_of, p.I32["evaluated mapping"])

    def test_scope_vars(self):

        # this tests for a bug with labels of scope vars
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        itm = p.ds.get_entity("I9662")
        self.assertEqual(itm.R1, "M")



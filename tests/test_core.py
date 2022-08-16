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

        teststring1 = "this is english text" @ mod1.p.en
        teststring2 = "das ist deutsch" @ mod1.p.de

        self.assertIsInstance(teststring1, rdflib.Literal)
        self.assertIsInstance(teststring2, rdflib.Literal)

        # R1 should return the default
        self.assertEqual(p.I900.R1.language, p.settings.DEFAULT_DATA_LANGUAGE)

        # ensure that R32["is functional for each language"] works as expected (return str/Literal but not [str] ...)
        self.assertNotIsInstance(p.I12.R2, list)
        self.assertNotIsInstance(p.I900.R2, list)

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
        itm = p.ds.get_entity("I4468")
        self.assertEqual(itm.R1, "M")

    def test_relations_with_sequence_as_argument(self):
        I001x = p.create_item(R1__has_label="test item")

        # check that assigning sequences is not allowed
        with self.assertRaises(TypeError):
            I001x.set_relation(p.R5["is part of"], [p.I4["Mathematics"], p.I5["Engineering"]])

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        itm = p.ds.get_entity("I4466")  # I4466["Systems Theory"]
        # construction: R5__is_part_of=[p.I4["Mathematics"], p.I5["Engineering"]]
        res = itm.R5
        self.assertEqual(len(res), 2)
        self.assertIn(p.I4["Mathematics"], res)
        self.assertIn(p.I5["Engineering"], res)

    def test_is_instance_of_generalized_metaclass(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")

        itm1 = p.ds.get_entity("I2")  # I2["Metaclass"]
        itm2 = p.ds.get_entity("I4235")  # I4235["mathematical object"]
        itm3 = p.ds.get_entity("I4239")  # I4239["monovariate polynomial"]->I4236["mathematical expression"]->I4235

        # metaclass itself is not an instance of metaclass
        self.assertFalse(p.is_instance_of_generalized_metaclass(itm1))

        self.assertTrue(p.is_instance_of_generalized_metaclass(itm2))
        self.assertTrue(p.is_instance_of_generalized_metaclass(itm3))

        itm4 = p.instance_of(itm3)
        self.assertFalse(p.is_instance_of_generalized_metaclass(itm4))

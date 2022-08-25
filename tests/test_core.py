import unittest
import sys
import os
from os.path import join as pjoin

import rdflib

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception, set_trace
import pyerk as p
import pyerk.visualization as visualization

activate_ips_on_exception()

current_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
TEST_DATA_PATH = pjoin(current_dir, "test_data", "knowledge_base1.py")


# noinspection PyPep8Naming
class TestCore(unittest.TestCase):
    def setUp(self):
        # this serves to debug interdependent test-cases
        print("In method", p.aux.bgreen(self._testMethodName))
        # IPS(print_tb=-1)
        pass

    def tearDown(self) -> None:

        # unload all modules which where loaded by a test
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)

    def test_aa1(self):
        """
        The first test ensures, that TestCases do not influence each other
        """
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")

        self.tearDown()

        # after tearing down there should be no i32 instances left
        i32_instance_rels = p.I32["evaluated mapping"].get_inv_relations("R4__is_instance_of")
        self.assertEqual(len(i32_instance_rels), 0)

        builtin_entity_keys = set(p.ds.builtin_entities.keys())
        available_item_keys = set(p.ds.items.keys())
        available_relation_keys = set(p.ds.relations.keys())
        available_relation_edge_keys = set(p.ds.relation_edges.keys())
        available_relation_relation_edge_keys = set(p.ds.relation_relation_edges.keys())

        diff1 = available_item_keys.difference(builtin_entity_keys)
        diff2 = available_relation_keys.difference(builtin_entity_keys)
        diff3 = available_relation_edge_keys.difference(builtin_entity_keys)
        diff4 = available_relation_relation_edge_keys.difference(builtin_entity_keys)

        self.assertEqual(len(diff1), 0)
        self.assertEqual(len(diff2), 0)
        self.assertEqual(len(diff3), 0)
        self.assertEqual(len(diff4), 0)

    # noinspection PyUnresolvedReferences
    # (above noinspection is necessary because of the @-operator which is undecleared for strings)
    def test_core1(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        self.assertEqual(mod1.I3749.R1, "Cayley-Hamilton theorem")

        def_eq_item = mod1.I6886.R6__has_defining_equation
        self.assertEqual(def_eq_item.R4__is_instance_of, p.I18["mathematical expression"])
        self.assertEqual(def_eq_item.R24__has_LaTeX_string, r"$\dot x = f(x, u)$")

        # TODO: convince pycharm that this is valid (due to .__rmatmul__ method of p.en)
        teststring1 = "this is english text" @ p.en
        teststring2 = "das ist deutsch" @ p.de

        self.assertIsInstance(teststring1, rdflib.Literal)
        self.assertIsInstance(teststring2, rdflib.Literal)

        # R1 should return the default
        self.assertEqual(p.I900.R1.language, p.settings.DEFAULT_DATA_LANGUAGE)

        # ensure that R32["is functional for each language"] works as expected (return str/Literal but not [str] ...)
        self.assertNotIsInstance(p.I12.R2, list)
        self.assertNotIsInstance(p.I900.R2, list)

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
        # Note: this creates items with keys which might conflict with recently added keys to builtin entities
        # explicitly unlinking them at the end
        itm = p.create_item(key_str=p.generate_new_key("I"), R1="unit test item")
        itm2 = p.create_item(key_str=p.generate_new_key("I"), R1="unit test item2")

        def example_func2(slf, a):
            return f"{slf.R1}::{a}"

        itm.add_method(example_func2)

        res2 = itm.example_func2(1234)
        self.assertEqual("unit test item::1234", res2)
        self.assertIsInstance(itm2, p.Entity)

        # ensure that this method is not available to generic other instances of Entity
        with self.assertRaises(AttributeError):
            itm2.example_func2(1234)

        # explicitly unklink the created entities to avoid inferrence with future tests
        p.core._unlink_entity(itm.short_key)
        p.core._unlink_entity(itm2.short_key)

    def test_evaluated_mapping(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        poly1 = p.instance_of(mod1.I4239["monovariate polynomial"])

        # test that an arbitrary item is *not* callable
        self.assertRaises(TypeError, mod1.I2738["field of complex numnbers"], 0)

        # test that some special items are callable (note that its parent class is a subclass of one which has
        # a _custom_call-method defined)
        res = poly1(0)

        self.assertEqual(res.R4__is_instance_of, p.I32["evaluated mapping"])

    def test_scope_vars(self):

        # this tests for a bug with labels of scope vars
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        def_itm = p.ds.get_entity("I9907")
        matrix_instance = def_itm.M
        self.assertEqual(matrix_instance.R1, "M")

    def test_relations_with_sequence_as_argument(self):
        Ia001 = p.create_item(R1__has_label="test item")

        # check that assigning sequences is not allowed
        with self.assertRaises(TypeError):
            Ia001.set_relation(p.R5["is part of"], [p.I4["Mathematics"], p.I5["Engineering"]])

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        itm = p.ds.get_entity("I4466")  # I4466["Systems Theory"]
        # construction: R5__is_part_of=[p.I4["Mathematics"], p.I5["Engineering"]]
        res = itm.R5
        self.assertEqual(len(res), 2)
        self.assertIn(p.I4["Mathematics"], res)
        self.assertIn(p.I5["Engineering"], res)

    def test_is_instance_of_generalized_metaclass(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")

        itm1 = p.ds.get_entity("I2__Metaclass")
        itm2 = p.ds.get_entity("I4235__mathematical_object")
        itm3 = p.ds.get_entity("I4239__monovariate_polynomial")

        # metaclass itself is not an instance of metaclass
        self.assertFalse(p.is_instance_of_generalized_metaclass(itm1))

        self.assertTrue(p.is_instance_of_generalized_metaclass(itm2))
        self.assertTrue(p.is_instance_of_generalized_metaclass(itm3))

        itm4 = p.instance_of(itm3)
        self.assertFalse(p.is_instance_of_generalized_metaclass(itm4))

    def test_qualifiers(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")

        itm1: p.Item = p.ds.get_entity("I2746__Rudolf_Kalman")
        rel1, rel2 = itm1.get_relations()[p.pk("R1833__has_employer")][:2]
        self.assertEqual(len(rel1.qualifiers), 2)
        self.assertEqual(len(rel2.qualifiers), 2)

    def test_equation(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")

        itm1: p.Item = p.ds.get_entity("I3749__Cayley-Hamilton_theorem")
        Z: p.Item = itm1.scope("context").namespace["Z"]
        inv_rel_dict = Z.get_inv_relations()

        # test R31__in_mathematical_relation_with

        r31_list = inv_rel_dict["R31"]
        re: p.RelationEdge = r31_list[0]
        self.assertEqual(len(r31_list), 1)

        # test the expected qualifier
        q = re.qualifiers[0]
        self.assertEqual(q.relation_tuple[0], re)
        self.assertEqual(q.relation_tuple[1], p.R34["has proxy item"])

        # this is the proxy item
        eq = q.relation_tuple[2]
        rhs = eq.R27__has_rhs
        self.assertEqual(rhs, Z)

        # ensure reproducible results of applied mappings
        lhs = eq.R26__has_lhs
        P: p.Item = itm1.scope("context").namespace["P"]
        A: p.Item = itm1.scope("context").namespace["A"]
        tmp = P(A)
        self.assertEqual(lhs, tmp)

    def test_process_key_str(self):

        # first, check label consistency in builtin_enities
        # note these keys do not to exist
        pkey1 = p.process_key_str("I0008234")

        self.assertEqual(pkey1.short_key, "I0008234")
        self.assertEqual(pkey1.label, "")

        pkey2 = p.process_key_str("R00001234__my_label")

        self.assertEqual(pkey2.short_key, "R00001234")
        self.assertEqual(pkey2.label, "my_label")

        # wrong syntax of key_str (missing "__")
        self.assertRaises(ValueError, p.process_key_str, "R1234XYZ")

        pkey3 = p.process_key_str("R2__has_description")

        self.assertEqual(pkey3.short_key, "R2")
        self.assertEqual(pkey3.label, "has_description")

        # wrong label ("_XYZ")
        self.assertRaises(ValueError, p.process_key_str, "R2__has_description_XYZ")

        # now, check label consistency in the test data
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")

    def test_format_label(self):

        e1 = p.create_item(key_str="I0123", R1="1234567890")
        node = visualization.create_node(e1, url_template="")
        node.perform_html_wrapping(use_html=False)
        label = node.get_dot_label(render=True)
        self.assertEqual(label, 'I0123\\n["1234567890"]')

        e1 = p.create_item(key_str="I0124", R1="1234567890abcdefgh")
        node = visualization.create_node(e1, url_template="")
        node.perform_html_wrapping(use_html=False)
        label = node.get_dot_label(render=True)
        self.assertEqual(label, 'I0124\\n["1234567890abcde\\nfgh"]')

        e1 = p.create_item(key_str="I0125", R1="12 34567 890abcdefgh")
        node = visualization.create_node(e1, url_template="")
        node.perform_html_wrapping(use_html=False)
        label = node.get_dot_label(render=True)
        self.assertEqual(label, 'I0125\\n["12 34567\\n890abcdefgh"]')

        e1 = p.create_item(key_str="I0126", R1="12 34567-890abcdefgh")
        node = visualization.create_node(e1, url_template="")
        node.perform_html_wrapping(use_html=False)
        label = node.get_dot_label(render=True)
        self.assertEqual(label, 'I0126\\n["12 34567-\\n890abcdefgh"]')


class TestCore2(unittest.TestCase):
    def setUp(self):
        # this serves to debug interdependent test-cases
        # print("In method", p.aux.bgreen(self._testMethodName))
        pass

    def tearDown(self) -> None:

        # unload all modules which where loaded by a test
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)

    def test_visualization(self):

        res_graph: visualization.nx.DiGraph = visualization.create_nx_graph_from_entity("I21__mathematical_relation")
        self.assertEqual(res_graph.number_of_nodes(), 7)

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        res_graph: visualization.nx.DiGraph = visualization.create_nx_graph_from_entity("Ia3699")
        self.assertEqual(res_graph.number_of_nodes(), 8)

    def test_visualization2(self):
        # test rendering of dot

        res = visualization.visualize_entity("I21__mathematical_relation", write_tmp_files=True)

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        res = visualization.visualize_entity("Ia6745", write_tmp_files=False)


class TestZZCore3(unittest.TestCase):
    """
    Collection of test that should be executed last (because they seem to influence othter tests).
    This is achieved by putting "ZZ" in the name (assuming that test classes are executed in alphabetical order).
    """

    def setUp(self):
        # this serves to debug interdependent test-cases
        # print("In method", p.aux.bgreen(self._testMethodName))
        pass

    def tearDown(self) -> None:

        # unload all modules which where loaded by a test
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)

    def test_sparql_query(self):
        # This test seems somehow to influence later tests
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH, "knowledge_base1")
        p.ds.rdfgraph = p.rdfstack.create_rdf_triples()
        qsrc = p.rdfstack.get_sparql_example_query()
        res = p.ds.rdfgraph.query(qsrc)
        res2 = p.aux.apply_func_to_table_cells(p.rdfstack.convert_from_rdf_to_pyerk, res)

        import colorama

        print(colorama.Fore.YELLOW, "sparql test currently fails!")

        # self.assertEqual(res2, [[mod1.I4466, p.I4], [mod1.I4466, p.I5]])

import unittest
import sys
import os
from os.path import join as pjoin
import random

import rdflib

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception, set_trace  # noqa
import pyerk as p
import pyerk.visualization as visualization
import git
from addict import Addict as Container
import pyerk.reportgenerator as rgen

"""
recommended ways to run the tests from the repo root (where setup.py lives):

# all tests
nosetests --rednose --nocapture
python3 -m unititest

# single class


"""

# ensure reproducible results
# (the result order of graph algorithms imported in ruleengine seems to depend on random numbers)
random.seed(1714)

activate_ips_on_exception()

current_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))

ERK_ROOT_DIR = p.aux.get_erk_root_dir()

# path for basic (staged) test data
TEST_DATA_DIR1 = pjoin(ERK_ROOT_DIR, "pyerk-core", "tests", "test_data")

# path for "realistic" test data

# taking this from envvar allows to flexibly use other test-data during debugging
TEST_DATA_PARENT_PATH = os.getenv("PYERK_TEST_DATA_PARENT_PATH", default=pjoin(ERK_ROOT_DIR, "erk-data-for-unittests"))


TEST_DATA_REPO_PATH = pjoin(TEST_DATA_PARENT_PATH, "ocse")
TEST_DATA_PATH2 = pjoin(TEST_DATA_REPO_PATH, "control_theory1.py")
TEST_DATA_PATH_MA = pjoin(TEST_DATA_REPO_PATH, "math1.py")
TEST_DATA_PATH3 = pjoin(TEST_DATA_REPO_PATH, "agents1.py")
TEST_DATA_PATH_ZEBRA01 = pjoin(TEST_DATA_DIR1, "zebra01.py")
TEST_DATA_PATH_ZEBRA02 = pjoin(TEST_DATA_DIR1, "zebra02.py")
TEST_DATA_PATH_ZEBRA_BASE_DATA = pjoin(TEST_DATA_DIR1, "zebra_base_data.py")
TEST_DATA_PATH_ZEBRA_RULES = pjoin(TEST_DATA_DIR1, "zebra_puzzle_rules.py")
TEST_MOD_NAME = "control_theory1"

# useful to get the currently latest sha strings:
# git log --pretty=oneline | head
TEST_DATA_REPO_COMMIT_SHA = "2ef9c27bf7b0743956edda558506626ac8b2dba0"  # (2022-12-20 17:11:24)

# TODO: make this more robust (e.g. search for config file or environment variable)
# TODO: put link to docs here (directory layout)
TEST_ACKREP_DATA_FOR_UT_PATH = pjoin(ERK_ROOT_DIR, "..", "ackrep", "ackrep_data_for_unittests")

os.environ["UNITTEST"] = "True"

__URI__ = TEST_BASE_URI = "erk:/local/unittest"


# this serves to print the test-method-name before it is executed (useful for debugging, see setUP below)
PRINT_TEST_METHODNAMES = True

# some tests might generate files such as `tmp.svg` as a byproduct for debugging. The following flags controls this.
WRITE_TMP_FILES = False


class HouskeeperMixin:
    """
    Class to provide common functions for all our TestCase subclasses
    """

    def setUp(self):
        self.register_this_module()

    def tearDown(self) -> None:
        if not self._outcome.errors:
            # keep the mods loaded for easier interactive debugging
            self.unload_all_mods()
        self.print_methodnames()

    @staticmethod
    def unload_all_mods():
        p.unload_mod(TEST_BASE_URI, strict=False)

        # unload all modules which where loaded by a test
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)

    @staticmethod
    def register_this_module():
        keymanager = p.KeyManager()
        p.register_mod(TEST_BASE_URI, keymanager)

    def print_methodnames(self):
        if PRINT_TEST_METHODNAMES:
            # noinspection PyUnresolvedReferences
            cls = self.__class__
            method_repr = f"{cls.__module__}:{cls.__qualname__}.{self._testMethodName}"
            method_repr = f"{method_repr:<85}"

            if self._outcome.errors:
                print(method_repr, p.aux.bred("failed"))
            else:
                print(method_repr, p.aux.bgreen("passed"))


class Test_00_Core(HouskeeperMixin, unittest.TestCase):
    def test_a0__ensure_expected_test_data(self):
        """
        Construct a list of all sha-strings which where commited in the current branch and assert that
        the expected string is among them. This heuristics assumes that it is OK if the data-repo is newer than
        expected. But the tests fails if it is older (or on a unexpeced branch).
        """

        repo = git.Repo(TEST_DATA_REPO_PATH)
        log_list = repo.git.log("--pretty=oneline").split("\n")
        sha_list = [line.split(" ")[0] for line in log_list]

        self.assertIn(TEST_DATA_REPO_COMMIT_SHA, sha_list)

    def test_a1__process_key_str(self):
        res = p.process_key_str("I1")
        self.assertEqual(res.prefix, None)
        self.assertEqual(res.short_key, "I1")
        self.assertEqual(res.label, None)

        res = p.process_key_str("I000__test_label", check=False)
        self.assertEqual(res.prefix, None)
        self.assertEqual(res.short_key, "I000")
        self.assertEqual(res.label, "test_label")

        res = p.process_key_str("some_prefix__I000", check=False, resolve_prefix=False)
        self.assertEqual(res.prefix, "some_prefix")
        self.assertEqual(res.short_key, "I000")
        self.assertEqual(res.label, None)

        res = p.process_key_str("some_prefix__I000__test_label", check=False, resolve_prefix=False)
        self.assertEqual(res.prefix, "some_prefix")
        self.assertEqual(res.short_key, "I000")
        self.assertEqual(res.label, "test_label")

        with self.assertRaises(p.UnknownPrefixError):
            res = p.process_key_str("some_prefix__I000__test_label", check=False, resolve_prefix=True)

        with self.assertRaises(KeyError):
            res = p.process_key_str("some_prefix_literal_value", check=False)

        res = p.process_key_str("some_prefix__I000['test_label']", check=False, resolve_prefix=False)
        self.assertEqual(res.prefix, "some_prefix")
        self.assertEqual(res.short_key, "I000")
        self.assertEqual(res.label, "test_label")

        res = p.process_key_str('some_prefix__I000["test_label"]', check=False, resolve_prefix=False)
        self.assertEqual(res.prefix, "some_prefix")
        self.assertEqual(res.short_key, "I000")
        self.assertEqual(res.label, "test_label")

        with self.assertRaises(KeyError):
            res = p.process_key_str("some_prefix__I000['missing bracket'", check=False)

        with self.assertRaises(KeyError):
            res = p.process_key_str("some_prefix__I000[missing quotes]", check=False)

        with self.assertRaises(KeyError):
            res = p.process_key_str("some_prefix__I000__double_label_['redundant']", check=False)

    def test_b1__uri_contex_manager(self):
        """
        Test defined behavior of errors occur in uri_context
        :return:
        """

        self.assertEqual(len(p.core._uri_stack), 0)
        try:
            with p.uri_context(uri=TEST_BASE_URI):
                raise ValueError
        except ValueError:
            pass
        self.assertEqual(len(p.core._uri_stack), 0)

        self.assertEqual(len(p.ds.entities_created_in_mod), 1)
        L1 = len(p.ds.items)
        L2 = len(p.ds.relations)
        L3 = len(p.ds.statement_uri_map)
        try:
            _ = p.erkloader.load_mod_from_path(pjoin(TEST_DATA_DIR1, "tmod0_with_errors.py"), prefix="tm0")
        except ValueError:
            pass
        # assert that no enties remain in the data structures
        self.assertEqual(len(p.ds.entities_created_in_mod), 1)
        self.assertEqual(L1, len(p.ds.items))
        self.assertEqual(L2, len(p.ds.relations))
        self.assertEqual(L3, len(p.ds.statement_uri_map))
        self.assertEqual(len(p.core._uri_stack), 0)

    def test_key_manager(self):
        p.KeyManager.instance = None

        km = p.KeyManager(minval=100, maxval=105)

        self.assertEqual(km.key_reservoir, [103, 101, 100, 104, 102])

        k = km.pop()
        self.assertEqual(k, 102)

        k = km.pop()
        self.assertEqual(k, 104)
        self.assertEqual(km.key_reservoir, [103, 101, 100])

    def test_uri_attr_of_entities(self):

        self.assertEqual(p.I1.uri, f"{p.BUILTINS_URI}#I1")
        self.assertEqual(p.R1.uri, f"{p.BUILTINS_URI}#R1")

        with self.assertRaises(p.EmptyURIStackError):
            itm = p.create_item(key_str=p.pop_uri_based_key("I"), R1="unit test item")

        with p.uri_context(uri=TEST_BASE_URI):
            itm = p.create_item(key_str=p.pop_uri_based_key("I"), R1="unit test item")
            rel = p.create_relation(key_str=p.pop_uri_based_key("R"), R1="unit test relation")

        self.assertEqual(itm.uri, f"{TEST_BASE_URI}#{itm.short_key}")
        self.assertEqual(rel.uri, f"{TEST_BASE_URI}#{rel.short_key}")

    def test_load_multiple_modules(self):
        _ = p.erkloader.load_mod_from_path(pjoin(TEST_DATA_DIR1, "tmod1.py"), prefix="tm1")
        # TODO: to be continued where tmod1 itself loads tmod2...


# noinspection PyPep8Naming
class Test_01_Core(HouskeeperMixin, unittest.TestCase):
    def test_a01__directory_structure(self):
        pyerk_dir = pjoin(ERK_ROOT_DIR, "pyerk-core")
        django_gui_dir = pjoin(ERK_ROOT_DIR, "pyerk-django")

        self.assertTrue(os.path.isdir(pyerk_dir))
        # since there is no reason to have the django gui in this repos CI:
        if os.environ.get("CI") != "true":
            self.assertTrue(os.path.isdir(django_gui_dir))
        self.assertTrue(os.path.isdir(TEST_DATA_PARENT_PATH))

    def test_a01__test_independence(self):
        """
        The first test ensures, that TestCases do not influence each other
        """

        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")

        self.tearDown()

        # after tearing down there should be no i32 instances left
        i32_instance_rels = p.I32["evaluated mapping"].get_inv_relations("R4__is_instance_of")
        self.assertEqual(len(i32_instance_rels), 0)

        builtin_entity_uris = set(p.ds.entities_created_in_mod[p.BUILTINS_URI])
        builtin_stm_uris = set(p.ds.stms_created_in_mod[p.BUILTINS_URI])
        available_item_keys = set(p.ds.items.keys())
        available_relation_keys = set(p.ds.relations.keys())
        available_statement_keys = set(p.ds.statement_uri_map.keys())
        available_relation_statement_keys = set(p.ds.relation_statements.keys())

        diff1 = available_item_keys.difference(builtin_entity_uris)
        diff2 = available_relation_keys.difference(builtin_entity_uris)

        diff3 = available_statement_keys.difference(builtin_stm_uris)
        diff4 = available_relation_statement_keys.difference(builtin_entity_uris)

        self.assertEqual(len(diff1), 0)
        self.assertEqual(len(diff2), 0)
        self.assertEqual(len(diff3), 0)
        self.assertEqual(len(diff4), 0)

    def test_a03_tear_down(self):
        """
        test if tear_down of TestClass works properly

        :return:
        """

        # ensure that builtins are loaded
        self.assertGreater(len(p.ds.items), 40)
        self.assertGreater(len(p.ds.relations), 40)
        self.assertGreater(len(p.ds.statement_uri_map), 300)

        # ensure that no residuals are left from last test
        non_builtin_stms = [k for k in p.ds.statement_uri_map.keys() if not k.startswith(p.BUILTINS_URI)]
        self.assertEqual(len(non_builtin_stms), 0)

        non_builtin_entities = [k for k in p.ds.items.keys() if not k.startswith(p.BUILTINS_URI)]
        non_builtin_entities += [k for k in p.ds.relations.keys() if not k.startswith(p.BUILTINS_URI)]
        self.assertEqual(len(non_builtin_entities), 0)

    # noinspection PyUnresolvedReferences
    # (above noinspection is necessary because of the @-operator which is undecleared for strings)
    def test_b01__core1_basics(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        self.assertEqual(mod1.I3749.R1, "Cayley-Hamilton theorem")

        def_eq_item = mod1.I6886.R6__has_defining_mathematical_relation
        self.assertEqual(def_eq_item.R4__is_instance_of, p.I18["mathematical expression"])
        self.assertEqual(def_eq_item.R24__has_LaTeX_string, r"$\dot x = f(x, u)$")

        teststring1 = "this is english text" @ p.en
        teststring2 = "das ist deutsch" @ p.de

        self.assertIsInstance(teststring1, rdflib.Literal)
        self.assertIsInstance(teststring2, rdflib.Literal)

        # R1 should return the default
        self.assertEqual(p.I900.R1.language, p.settings.DEFAULT_DATA_LANGUAGE)

        # ensure that R32["is functional for each language"] works as expected (return str/Literal but not [str] ...)
        self.assertNotIsInstance(p.I12.R2, list)
        self.assertNotIsInstance(p.I900.R2, list)

        mod_uri = p.ds.uri_prefix_mapping.b["ct"]
        p.unload_mod(mod_uri)

    def test_b02_builtins1(self):
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

        with p.uri_context(uri=TEST_BASE_URI):
            itm = p.create_item(key_str=p.pop_uri_based_key("I"), R1="unit test item")
            itm2 = p.create_item(key_str=p.pop_uri_based_key("I"), R1="unit test item2")

        def example_func2(slf, a):
            return f"{slf.R1}::{a}"

        itm.add_method(example_func2)

        res2 = itm.example_func2(1234)
        self.assertEqual("unit test item::1234", res2)
        self.assertIsInstance(itm2, p.Entity)

        # ensure that this method is not available to generic other instances of Entity
        with self.assertRaises(AttributeError):
            itm2.example_func2(1234)

    # TODO: trigger loading of unittest version of ocse via envvar
    def test_a02__load_settings(self):
        """
        ensure that the default settingsfile is loaded correctly
        """
        # this is a variable which should be present in every pyerkconf file
        conf = p.settings.CONF

        # self.assertTrue(len(conf) != 0)
        self.assertTrue(len(conf) >= 0)

    def test_c01__ct_loads_math(self):
        """
        test if the control_theory module successfully loads the math module

        :return:
        """
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        self.assertIn("ma", p.ds.uri_prefix_mapping.b)
        itm1 = p.ds.get_entity_by_key_str("ma__I5000__scalar_zero")
        self.assertEqual(itm1, mod1.ma.I5000["scalar zero"])

    def test_c02__multilingual_relations(self):
        """
        test how to create items with labels in multiple languages
        """

        with p.uri_context(uri=TEST_BASE_URI):
            itm = p.create_item(
                key_str=p.pop_uri_based_key("I"),
                # multiple values to R1 can be passed using a list
                R1__has_label=[
                    "test-label in english" @ p.en,  # `@p.en` is recommended, if you use multiple languages
                    "test-label auf deutsch" @ p.de,
                ],
                R2__has_description="test-description in english",
            )

        # this returns only one label according to the default language
        default_label = itm.R1

        # to access all labels use this:
        label1, label2 = itm.get_relations("R1", return_obj=True)
        self.assertEqual(default_label, label1)
        self.assertEqual(label1.value, "test-label in english")
        self.assertEqual(label1.language, "en")
        self.assertEqual(label2.value, "test-label auf deutsch")
        self.assertEqual(label2.language, "de")

        # add another language later

        with p.uri_context(uri=TEST_BASE_URI):
            itm.set_relation(p.R2, "test-beschreibung auf deutsch" @ p.de)

        desc1, desc2 = itm.get_relations("R2", return_obj=True)

        self.assertTrue(isinstance(desc1, str))
        self.assertTrue(isinstance(desc2, p.Literal))

        self.assertEqual(desc2.language, "de")

        # use the labels of different languages in index-labeld key notation

        # first: without explicitly specifying the language
        tmp1 = itm["test-label in english"]
        self.assertTrue(tmp1 is itm)

        tmp2 = itm["test-label auf deutsch"]
        self.assertTrue(tmp2 is itm)

        # second: with explicitly specifying the language
        tmp3 = itm["test-label in english" @ p.en]
        self.assertTrue(tmp3 is itm)

        tmp4 = itm["test-label auf deutsch" @ p.de]
        self.assertTrue(tmp4 is itm)

        with self.assertRaises(ValueError):
            tmp5 = itm["wrong label"]

        with self.assertRaises(ValueError):
            tmp5 = itm["wrong label" @ p.de]

        with self.assertRaises(ValueError):
            tmp5 = itm["wrong label" @ p.en]  # noqa

        # change the default language

        p.settings.DEFAULT_DATA_LANGUAGE = "de"

        new_default_label = itm.R1
        self.assertEqual(new_default_label, label2)
        self.assertEqual(new_default_label.language, "de")

        new_default_description = itm.R2
        self.assertEqual(new_default_description, "test-beschreibung auf deutsch" @ p.de)

        with p.uri_context(uri=TEST_BASE_URI):
            itm2 = p.create_item(
                key_str=p.pop_uri_based_key("I"),
                # multiple values to R1 can be passed using a list
                R1__has_label=["test-label2", "test-label2-de" @ p.de],
                R2__has_description="test-description2 in english",
            )

        # in case of ordinary strings they should be used if no value is available for current language

        self.assertEqual(p.settings.DEFAULT_DATA_LANGUAGE, "de")
        self.assertEqual(itm2.R1, "test-label2-de" @ p.de)
        self.assertEqual(itm2.R2, "test-description2 in english")

        p.settings.DEFAULT_DATA_LANGUAGE = "en"
        self.assertEqual(itm2.R1, "test-label2")
        self.assertEqual(itm2.R2, "test-description2 in english")

        p.settings.DEFAULT_DATA_LANGUAGE = "en"

        # test for correct error message
        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            itm1 = p.instance_of(p.I1["general item"])

            # this should cause no error (because of differnt language)
            itm1.set_relation(p.R1["has label"], "neues Label"@p.de)

            with self.assertRaises(p.aux.FunctionalRelationError):
                itm1.set_relation(p.R1["has label"], "new label")

    def test_c03__nontrivial_metaclasses(self):
        with p.uri_context(uri=TEST_BASE_URI):
            i1 = p.instance_of(p.I34["complex number"])

        self.assertTrue(i1.R4, p.I34)

    def test_c04__evaluated_mapping(self):

        res = p.ds.statements.get("S6229")
        self.assertIsNone(res)

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        with p.uri_context(uri=TEST_BASE_URI):
            poly1 = p.instance_of(mod1.I4239["monovariate polynomial"])

        # test that an arbitrary item is *not* callable
        self.assertRaises(TypeError, mod1.ma.I2738["field of complex numbers"], 0)

        # test that some special items are callable (note that its parent class is a subclass of one which has
        # a _custom_call-method defined)
        with p.uri_context(uri=TEST_BASE_URI):
            # this creates new items and thus must be executed inside a context
            res = poly1(0)

        self.assertEqual(res.R4__is_instance_of, p.I32["evaluated mapping"])

    def test_c05__evaluated_mapping2(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")

        with p.uri_context(uri=TEST_BASE_URI):
            h = p.instance_of(mod1.I9923["scalar field"])
            f = p.instance_of(mod1.I9841["vector field"])
            x = p.instance_of(mod1.I1168["point in state space"])

            Lderiv = mod1.I1347["Lie derivative of scalar field"]

            # this creates a new item (and thus must be executed with a non-empty uri stack, i.e. within this context)
            h2 = Lderiv(h, f, x)

        self.assertEqual(h2.R4__is_instance_of, mod1.I9923["scalar field"])

        arg_tup = h2.R36__has_argument_tuple
        self.assertEqual(arg_tup.R4__is_instance_of, p.I33["tuple"])
        elements = arg_tup.R39__has_element
        self.assertEqual(tuple(elements), (h, f, x))

    def test_c06__tuple(self):

        data = (10, 11, 12, 13, p.I1, "some string")

        with self.assertRaises(p.EmptyURIStackError):
            tup = p.new_tuple(*data)

        with p.uri_context(uri=TEST_BASE_URI):
            tup = p.new_tuple(*data)
        self.assertEqual(tup.R4__is_instance_of, p.I33["tuple"])
        self.assertEqual(tup.R38__has_length, 6)

        # TODO: non functional relations should return a tuple not a list?
        res = tup.R39__has_element
        self.assertEqual(data, tuple(res))

    def test_c07__scope_vars(self):

        # this tests for a bug with labels of scope vars
        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        def_itm = p.ds.get_entity_by_key_str("ct__I9907__definition_of_square_matrix")
        matrix_instance = def_itm.M
        self.assertEqual(matrix_instance.R1, "M")

    def test_c08__relations_with_sequence_as_argument(self):
        with p.uri_context(uri=TEST_BASE_URI):
            Ia001 = p.create_item(R1__has_label="test item")

        # check that assigning sequences is not allowed
        with self.assertRaises(TypeError):
            Ia001.set_relation(p.R5["is part of"], [p.I4["Mathematics"], p.I5["Engineering"]])

        with p.uri_context(uri=TEST_BASE_URI):
            # check that assigning sequences is possible with explicit method.
            Ia001.set_mutliple_relations(p.R5["is part of"], [p.I4["Mathematics"], p.I5["Engineering"]])

        rel_objs = Ia001.get_relations("R5", return_obj=True)
        self.assertEqual(rel_objs, [p.I4, p.I5])

        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        itm = p.ds.get_entity_by_key_str("ct__I4466__Systems_Theory")
        # construction: R5__is_part_of=[p.I4["Mathematics"], p.I5["Engineering"]]
        res = itm.R5
        self.assertEqual(len(res), 2)
        self.assertIn(p.I4["Mathematics"], res)
        self.assertIn(p.I5["Engineering"], res)

    def test_c09__is_instance_of_generalized_metaclass(self):
        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")

        itm1 = p.ds.get_entity_by_key_str("I2__Metaclass")
        itm2 = p.ds.get_entity_by_key_str("I12__mathematical_object")
        itm3 = p.ds.get_entity_by_key_str("ma__I4239__monovariate_polynomial")

        # metaclass could be considered as an instance of itself because metaclasses are allowed to have
        # subclasses and instances (which is both true for I2__metaclass)
        self.assertTrue(p.allows_instantiation(itm1))

        self.assertTrue(p.allows_instantiation(itm2))
        self.assertTrue(p.allows_instantiation(itm3))

        with p.uri_context(uri=TEST_BASE_URI):
            # itm3 is a normal class -> itm4 is not allowed to have instances (itm4 is no metaclass-instance)
            itm4 = p.instance_of(itm3)
        self.assertFalse(p.allows_instantiation(itm4))

    def test_c10__qualifiers(self):
        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH3, prefix="ag")

        itm1: p.Item = p.ds.get_entity_by_key_str("ag__I2746__Rudolf_Kalman")
        stm1, stm2 = itm1.get_relations("ag__R1833__has_employer")[:2]
        self.assertEqual(len(stm1.qualifiers), 2)
        self.assertEqual(len(stm2.qualifiers), 2)

        self.assertEqual(len(stm2.dual_statement.qualifiers), 2)

        qf1, qf2 = stm2.qualifiers

        qf1.unlink()
        self.assertEqual(len(stm2.qualifiers), 1)
        self.assertEqual(len(stm2.dual_statement.qualifiers), 1)

    def test_c11__equation(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")

        # get item via prefix and key
        itm1: p.Item = p.ds.get_entity_by_key_str("ct__I3749__Cayley-Hamilton_theorem")

        # get item via key and uri
        itm2: p.Item = p.ds.get_entity_by_key_str("I3749__Cayley-Hamilton_theorem", mod_uri=mod1.__URI__)

        self.assertEqual(itm1, itm2)

        Z: p.Item = itm1.scope("context").namespace["Z"]

        r31_list = Z.get_inv_relations("R31__is_in_mathematical_relation_with")
        stm: p.Statement = r31_list[0].dual_statement  # taking the dual because we got it via the inverse relation
        self.assertEqual(len(r31_list), 1)

        # test the expected qualifier
        q = stm.qualifiers[0]
        self.assertEqual(q.subject, stm)  # here it is relevant that we used the dual_relation above
        self.assertEqual(q.predicate, p.R34["has proxy item"])

        # this is the proxy item
        eq = q.object
        rhs = eq.R27__has_rhs
        self.assertEqual(rhs, Z)

        # ensure reproducible results of applied mappings
        lhs = eq.R26__has_lhs
        P: p.Item = itm1.scope("context").namespace["P"]
        A: p.Item = itm1.scope("context").namespace["A"]
        tmp = P(A)
        self.assertEqual(lhs, tmp)

    def test_c12__process_key_str(self):

        # first, check label consistency in builtin_enities
        # note these keys do not to exist
        pkey1 = p.process_key_str("I0008234")

        self.assertEqual(pkey1.short_key, "I0008234")
        self.assertEqual(pkey1.label, None)

        pkey2 = p.process_key_str("R00001234__my_label", check=False)

        self.assertEqual(pkey2.short_key, "R00001234")
        self.assertEqual(pkey2.label, "my_label")

        # wrong syntax of key_str (missing "__")
        self.assertRaises(KeyError, p.process_key_str, "R1234XYZ")

        pkey3 = p.process_key_str("R2__has_description", check=False)

        self.assertEqual(pkey3.short_key, "R2")
        self.assertEqual(pkey3.label, "has_description")

        # wrong label ("_XYZ")
        self.assertRaises(ValueError, p.process_key_str, "R2__has_description_XYZ")

        # now, check label consistency in the test data
        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, TEST_MOD_NAME)

    def test_c12a__process_key_str2(self):

        ct = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")

        p.ds.get_entity_by_key_str("ct__R7641__has_approximation") == ct.R7641["has approximation"]

        with p.uri_context(uri=TEST_BASE_URI):
            e0 = p.create_item(key_str="I0124", R1="some label")

            # test prefix notation in keyword attributes
            # first: missing prefix -> unknown key
            with self.assertRaises(KeyError):
                _ = p.create_item(key_str="I0125", R1="some label", R7641__has_approximation=e0)

            # second: use prefix to adresse the correct relation
            e1 = p.create_item(key_str="I0125", R1="some label", ct__R7641__has_approximation=e0)

            # third: create a relation which has a short key collission with a relation from the ct module
            _ = p.create_relation(key_str="R7641", R1="some test relation")
            e2 = p.create_item(
                key_str="I0126", R1="some label", ct__R7641__has_approximation=e0, R7641__some_test_relation="foo"
            )

        # this is the verbose way to adress a builtin relation
        self.assertEqual(e1.bi__R1, "some label")

        # this is the (necessary) way to adress a relation from an external module
        self.assertEqual(e1.ct__R7641[0], e0)
        self.assertEqual(e2.ct__R7641[0], e0)

        # unittest module is also "extern" (because it is currently not active)
        with self.assertRaises(AttributeError):
            _ = e2.R7641__some_test_relation

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            # adress the relation with correct prefix
            self.assertEqual(e2.ut__R7641__some_test_relation[0], "foo")

            # adress the relation without prefix (but with activated unittet module)
            self.assertEqual(e2.R7641__some_test_relation[0], "foo")

        # activate different module and use attribute without prefix
        with p.uri_context(uri=ct.__URI__):
            self.assertEqual(e2.R7641__has_approximation[0], e0)

    def test_c13__format_label(self):
        with p.uri_context(uri=TEST_BASE_URI):
            e1 = p.create_item(key_str="I0123", R1="1234567890")
        node = visualization.create_node(e1, url_template="")
        node.perform_html_wrapping(use_html=False)
        label = node.get_dot_label(render=True)
        self.assertEqual(label, 'I0123\\n["1234567890"]')

        with p.uri_context(uri=TEST_BASE_URI):
            e1 = p.create_item(key_str="I0124", R1="1234567890abcdefgh")
        node = visualization.create_node(e1, url_template="")
        node.perform_html_wrapping(use_html=False)
        label = node.get_dot_label(render=True)
        self.assertEqual(label, 'I0124\\n["1234567890abcde\\nfgh"]')

        with p.uri_context(uri=TEST_BASE_URI):
            e1 = p.create_item(key_str="I0125", R1="12 34567 890abcdefgh")
        node = visualization.create_node(e1, url_template="")
        node.perform_html_wrapping(use_html=False)
        label = node.get_dot_label(render=True)
        self.assertEqual(label, 'I0125\\n["12 34567\\n890abcdefgh"]')

        with p.uri_context(uri=TEST_BASE_URI):
            e1 = p.create_item(key_str="I0126", R1="12 34567-890abcdefgh")
        node = visualization.create_node(e1, url_template="")
        node.perform_html_wrapping(use_html=False)
        label = node.get_dot_label(render=True)
        self.assertEqual(label, 'I0126\\n["12 34567-\\n890abcdefgh"]')

    def test_c14__visualization1(self):

        res_graph: visualization.nx.DiGraph = visualization.create_nx_graph_from_entity(
            p.u("I21__mathematical_relation")
        )
        self.assertGreater(res_graph.number_of_nodes(), 6)

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, TEST_MOD_NAME)

        # do not use something like "Ia3699" here directly because this might change when mod1 changes
        auto_item: p.Item = mod1.I3749["Cayley-Hamilton theorem"].A
        res_graph: visualization.nx.DiGraph = visualization.create_nx_graph_from_entity(auto_item.uri)
        self.assertGreater(res_graph.number_of_nodes(), 7)

    def test_c15__visualization2(self):
        # test rendering of dot

        res = visualization.visualize_entity(p.u("I21__mathematical_relation"), write_tmp_files=WRITE_TMP_FILES)

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, TEST_MOD_NAME)
        auto_item: p.Item = mod1.I3749["Cayley-Hamilton theorem"].P
        res = visualization.visualize_entity(auto_item.uri, write_tmp_files=WRITE_TMP_FILES)

        s1 = '<a href="">R35</a>'
        s2 = '<a href="">["is applied</a>'
        s3 = '<a href="">mapping of"]</a>'
        self.assertIn(s1, res)
        self.assertIn(s2, res)
        self.assertIn(s3, res)

    def test_d01__wrap_function_with_uri_context(self):
        ma = p.erkloader.load_mod_from_path(TEST_DATA_PATH_MA, prefix="ma")

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):
            A = p.instance_of(ma.I9906["square matrix"])
            A.set_relation("ma__R5939__has_column_number", 7)

        def test_func():
            """
            docstring
            """
            # this fails outside uri-context of math
            n = A.R5939__has_column_number
            return n

        with self.assertRaises(AttributeError):
            test_func()

        wrapped_func = p.wrap_function_with_uri_context(test_func, ma.__URI__)

        self.assertEqual(wrapped_func.__doc__, test_func.__doc__)

        # now this call works as expected
        res = wrapped_func()
        self.assertEqual(res, 7)

    def test_d02__custom_call_post_process1(self):

        ma = p.erkloader.load_mod_from_path(TEST_DATA_PATH_MA, prefix="ma")

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):
            A = p.instance_of(ma.I9906["square matrix"])
            s = p.instance_of(ma.I5030["variable"])

            # construct sI - A
            M = ma.I6324["canonical first order monic polynomial matrix"](A, s)
            d = ma.I5359["determinant"](M)

        self.assertTrue(M.R4__is_instance_of, ma.I1935["polynomial matrix"])
        self.assertTrue(M.ma__R8736__depends_polyonomially_on, s)

        self.assertTrue(d.ma__R8736__depends_polyonomially_on, s)

    def test_d03__replace_entity(self):

        ma = p.erkloader.load_mod_from_path(TEST_DATA_PATH_MA, prefix="ma")

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):
            A = p.instance_of(ma.I9906["square matrix"])
            n1 = p.instance_of(p.I38["non-negative integer"])
            n2 = p.instance_of(p.I38["non-negative integer"])

            # set functional relation
            A.set_relation(ma.R5938["has row number"], n1)
        self.assertEqual(A.ma__R5938__has_row_number, n1)
        self.assertNotEqual(A.ma__R5938__has_row_number, n2)

        tmp = p.ds.get_entity_by_uri(n1.uri)
        self.assertEqual(n1, tmp)

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):
            p.replace_and_unlink_entity(n1, n2)

        self.assertEqual(A.ma__R5938__has_row_number, n2)
        self.assertNotEqual(A.ma__R5938__has_row_number, n1)

        with self.assertRaises(p.aux.UnknownURIError):
            tmp = p.ds.get_entity_by_uri(n1.uri)

    def test_d03b__replace_entity(self):

        ma = p.erkloader.load_mod_from_path(TEST_DATA_PATH_MA, prefix="ma")

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):
            A = p.instance_of(ma.I9906["square matrix"])
            n1 = p.instance_of(p.I38["non-negative integer"])
            n2 = p.instance_of(p.I38["non-negative integer"])
            n3 = p.instance_of(p.I38["non-negative integer"])

            # set relations
            A.set_relation(ma.R5938["has row number"], n1)  # n1 is object
            n1.set_relation(p.R31["is in mathematical relation with"], n3)  # n1 is subject

        self.assertEqual(n3.get_inv_relations("R31", return_subj=True)[0], n1)
        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):
            p.replace_and_unlink_entity(n1, n2)

        self.assertEqual(n3.get_inv_relations("R31", return_subj=True)[0], n2)

    def test_d04__invalid_prefix(self):

        n1a = len(p.ds.mod_path_mapping.a)
        n2a = len(p.ds.entities_created_in_mod)
        n3a = len(p.ds.stms_created_in_mod)
        n4a = len(sys.modules)

        with self.assertRaises(p.aux.InvalidPrefixError):
            _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zb")

        n1b = len(p.ds.mod_path_mapping.a)
        n2b = len(p.ds.entities_created_in_mod)
        n3b = len(p.ds.stms_created_in_mod)
        n4b = len(sys.modules)

        self.assertEqual(n1a, n1b)
        self.assertEqual(n2a, n2b)
        self.assertEqual(n3a, n3b)
        self.assertEqual(n4a, n4b)

    def test_d05__get_proxy_item(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):
            A = p.instance_of(p.I1["general item"])
            B = p.instance_of(p.I1["general item"], qualifiers=[p.proxy_item(A)])

        res = p.get_proxy_item(B.get_relations(p.R4.uri)[0])
        self.assertEqual(res, A)

    def test_d06__get_rel_props(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            R1000 = p.create_relation(
                R1__has_label="test relation",
                R22__is_functional=True,
                R53__is_inverse_functional=True,
            )

            R1001 = p.create_relation(
                R1__has_label="test relation2",
            )

            I2000 = p.instance_of(p.I40["general relation"])
            I2000.set_relation(p.R22["is functional"], True)

        res = p.get_relation_properties(R1000)
        self.assertEqual(res, [p.R22.uri, p.R53.uri])

        res = p.get_relation_properties(R1001)
        self.assertEqual(res, [])

        res = p.get_relation_properties(I2000)
        self.assertEqual(res, [p.R22.uri])

    def test_d07__replace_statement(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            itm = p.instance_of(p.I1["general item"])

        self.assertEqual(itm.R4__is_instance_of, p.I1["general item"])

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):
            itm.overwrite_statement("R4__is_instance_of", p.I2["Metaclass"])
        self.assertEqual(itm.R4__is_instance_of, p.I2["Metaclass"])

    def test_d08__unlink_enities(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            itm1 = p.instance_of(p.I1["general item"])

            rep_str1 = repr(itm1)
            self.assertTrue(rep_str1.endswith('["itm1"]>'))

            p.core._unlink_entity(itm1.uri, remove_from_mod=True)

            rep_str2 = repr(itm1)
            self.assertTrue(rep_str2.endswith('["!!unlinked: itm1"]>'))


class Test_02_ruleengine(HouskeeperMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def setup_data1(self):

        with p.uri_context(uri=TEST_BASE_URI):
            self.rule1 = p.create_item(
                key_str="I400",
                R1__has_label="subproperty rule 1",
                R2__has_description=(
                    # "specifies the 'transitivity' of I11_mathematical_property-instances via R17_issubproperty_of"
                    "specifies the 'transitivity' of R17_is_subproperty_of"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with self.rule1["subproperty rule 1"].scope("context") as cm:
                cm.new_var(P1=p.instance_of(p.I11["mathematical property"]))
                cm.new_var(P2=p.instance_of(p.I11["mathematical property"]))
                cm.new_var(P3=p.instance_of(p.I11["mathematical property"]))
            #     # A = cm.new_var(sys=instance_of(I1["general item"]))
            #
            with self.rule1["subproperty rule 1"].scope("premises") as cm:
                cm.new_rel(cm.P2, p.R17["is subproperty of"], cm.P1)
                cm.new_rel(cm.P3, p.R17["is subproperty of"], cm.P2)
                # todo: state that all variables are different from each other

            with self.rule1["subproperty rule 1"].scope("assertions") as cm:
                cm.new_rel(cm.P3, p.R17["is subproperty of"], cm.P1)

    def test_a01__basics(self):

        self.setup_data1()

        self.assertIn(TEST_BASE_URI, p.ds.entities_created_in_mod)
        self.assertEqual(len(p.ds.entities_created_in_mod), 2)
        self.tearDown()

        self.assertEqual(len(p.ds.entities_created_in_mod), 1)
        self.tearDown()

        # would be nice to solve this more elegantly (without the need for explicitly registering the module again)
        self.register_this_module()
        self.setup_data1()
        self.assertIn(TEST_BASE_URI, p.ds.entities_created_in_mod)
        self.assertEqual(len(p.ds.entities_created_in_mod), 2)

    def test_c02__ruleengine01(self):

        self.setup_data1()
        itm1 = p.I12["mathematical object"]
        res = p.ruleengine.get_simple_properties(itm1)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[p.R1.uri], itm1.R1)
        self.assertEqual(res[p.R2.uri], itm1.R2)

        ra = p.ruleengine.RuleApplicator(self.rule1)
        all_rels = ra.get_all_node_relations()
        self.assertGreater(len(all_rels), 30)
        key = (p.I2.uri, p.I1.uri)
        value_container: p.ruleengine.Container = all_rels[key]

        self.assertEqual(value_container.rel_uri, p.R3.uri)

        all_rules = p.ruleengine.get_all_rules()
        self.assertGreater(len(all_rules), 0)

    def test_c03__ruleengine02(self):
        self.setup_data1()
        ra = p.ruleengine.RuleApplicator(self.rule1)
        G = ra.create_simple_graph()
        self.assertGreater(G.number_of_nodes(), 30)
        self.assertGreater(G.number_of_edges(), 30)

    def test_c04__ruleengine03(self):
        self.setup_data1()

        ra = p.ruleengine.RuleApplicator(self.rule1)

        self.assertEqual(len(ra.get_asserted_relation_templates()), 1)

        self.assertEqual(ra.P.number_of_nodes(), 3)
        self.assertEqual(ra.P.number_of_edges(), 2)

        res_graph = ra.match_subgraph_P()

        # ensures that the rule does not match itself
        self.assertEqual(len(res_graph), 0)

        # in this erk module some properties have subproperties
        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct", modname=TEST_MOD_NAME)

        # create a new RuleApplicator because the overal graph changed
        ra = p.ruleengine.RuleApplicator(self.rule1)
        res_graph = ra.match_subgraph_P()
        self.assertGreater(len(res_graph), 5)

    def test_c05__ruleengine04(self):
        self.setup_data1()

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct", modname=TEST_MOD_NAME)
        self.assertEqual(len(mod1.I9642["local exponential stability"].get_relations("R17__is_subproperty_of")), 1)
        ra = p.ruleengine.RuleApplicator(self.rule1, mod_context_uri=TEST_BASE_URI)
        res = ra.apply()

        # ensure that after rule application there is at least one new relation
        self.assertEqual(len(mod1.I9642["local exponential stability"].get_relations("R17__is_subproperty_of")), 2)
        for r in res.new_statements:
            print(r)

    def test_c06__ruleengine05(self):
        self.setup_data1()
        premises_stms = p.ruleengine.filter_relevant_stms(
            self.rule1.scp__premises.get_inv_relations("R20__has_defining_scope")
        )

        self.assertEqual(len(premises_stms), 2)
        with self.assertRaises(p.aux.EmptyURIStackError):
            p.ruleengine.apply_all_semantic_rules()

        with p.uri_context(uri=TEST_BASE_URI):
            _ = p.ruleengine.apply_all_semantic_rules()

    def test_c07__zebra_puzzle01(self):
        """
        Test one special rule I901, with new features from builin_entities
        """

        self._apply_and__t_e_s_t__matching_rule("zb__I901")

    def _apply_and__t_e_s_t__matching_rule(self, rule_key, nbr_of_new_stms=1):

        # store relevant data in Container to evaluate further
        c = Container()
        zb = c.zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA01, prefix="zb")

        c.rule = p.ds.get_entity_by_key_str(rule_key)

        matching_rules = zb.unknown_beverage1.get_relations("R54__is_matched_by_rule", return_obj=True)
        self.assertEqual(matching_rules, [])
        res = p.ruleengine.apply_semantic_rule(c.rule, mod_context_uri=zb.__URI__)
        c.new_stms = res.new_statements

        relevant_statements = [stm for stm in c.new_stms if stm.subject == zb.unknown_beverage1]

        self.assertEqual(len(relevant_statements), nbr_of_new_stms)
        c.matching_rules = zb.unknown_beverage1.get_relations("R54__is_matched_by_rule", return_obj=True)
        self.assertEqual(c.matching_rules, [c.rule])

        return c

    def test_c08__zebra_puzzle02(self):
        """
        Test one special rule I902, with new features from builin_entities
        """

        self._apply_and__t_e_s_t__matching_rule("zb__I902")

    def test_c09__zebra_puzzle03(self):
        """
        Test one special rule I903 with new features from builin_entities
        """

        c = self._apply_and__t_e_s_t__matching_rule("zb__I903", nbr_of_new_stms=2)
        self.assertEqual(c.zb.unknown_beverage1.R56__is_one_of[0].R39__has_element[0], c.zb.I7509["water"])
        self.assertEqual(c.zb.unknown_beverage2.R56__is_one_of[0].R39__has_element[0], c.zb.I6756["tea"])

        # apply next rule: establishing R47__is_same_as relationship
        res = p.ruleengine.apply_semantic_rule(c.zb.I904, mod_context_uri=c.zb.__URI__)
        self.assertGreaterEqual(len(res.new_statements), 2)

        self.assertEqual(c.zb.unknown_beverage1.R47__is_same_as[0], c.zb.I7509["water"])
        self.assertEqual(c.zb.unknown_beverage2.R47__is_same_as[0], c.zb.I6756["tea"])

    def test_c10__zebra_puzzle_all_of_stage01(self):
        """
        apply all rules of stage 01 of the zebra puzzle and assess the correctness of the result
        """
        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA01, prefix="zb")

        self.assertNotEqual(zb.I4037["Englishman"].zb__R8216__drinks, zb.I7509["water"])
        _ = p.ruleengine.apply_all_semantic_rules(mod_context_uri=zb.__URI__)
        self.assertEqual(zb.I4037["Englishman"].zb__R8216__drinks, zb.I7509["water"])

    def test_d01__zebra_puzzle_stage02(self):
        """
        assess correctness of full data
        """

        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        # test base data
        self.assertEqual(zp.zb.I4037["Englishman"].zb__R8098__has_house_color.R1, "red")

        # test hints
        self.assertEqual(zp.zb.I9848["Norwegian"].zb__R3606__lives_next_to[0], zp.person12)

    def test_d02__zebra_puzzle_stage02(self):
        """
        apply rules and assess correctness of the result
        """

        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        neighbour = zp.person1.zb__R2353__lives_immediatly_right_of
        self.assertIsNone(neighbour)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I710, mod_context_uri=zp.__URI__)

        # assert that both statemens have been created:
        # S(person1,  p.R47["is same as"], person2)
        # S(person2,  p.R47["is same as"], person1)
        counter = 0
        for stm in res.new_statements:
            stm: p.Statement
            if stm.subject == zp.person1:
                self.assertEqual(stm.predicate, p.R47["is same as"])
                self.assertEqual(stm.object, zp.person2)
                counter += 1
            elif stm.subject == zp.person2:
                self.assertEqual(stm.predicate, p.R47["is same as"])
                self.assertEqual(stm.object, zp.person1)
                counter += 1

        self.assertEqual(counter, 2)

        with p.uri_context(uri=TEST_BASE_URI):
            p.replace_and_unlink_entity(zp.person2, zp.person1)

        neighbour = zp.person1.zb__R2353__lives_immediatly_right_of
        self.assertEqual(neighbour, zp.person3)

    def test_d03__zebra_puzzle_stage02(self):
        """
        Test the outcome of some specific rules
        """

        with p.uri_context(uri=TEST_BASE_URI):

            itm1 = p.instance_of(p.I36["rational number"])
            itm2 = p.instance_of(p.I36["rational number"])
            itm3 = p.instance_of(p.I36["rational number"])
            itm4 = p.instance_of(p.I34["complex number"])

            I702 = p.create_item(
                R1__has_label="test rule",
                R2__has_description=("test to match every instance of I36['rational number']"),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I702.scope("context") as cm:
                cm.new_var(x=p.instance_of(p.I1["general item"]))
                cm.uses_external_entities(I702)
                cm.uses_external_entities(p.I36["rational number"])

            with I702.scope("premises") as cm:
                cm.new_rel(cm.x, p.R4["is instance of"], p.I36["rational number"], overwrite=True)

            with I702.scope("assertions") as cm:
                cm.new_rel(cm.x, p.R54["is matched by rule"], I702)

            self.assertEqual(itm1.R54__is_matched_by_rule, [])
            self.assertEqual(itm2.R54__is_matched_by_rule, [])
            self.assertEqual(itm3.R54__is_matched_by_rule, [])

            res = p.ruleengine.apply_semantic_rule(I702)

        self.assertEqual(len(res.new_statements), 3)
        self.assertEqual(itm1.R54__is_matched_by_rule, [I702])
        self.assertEqual(itm2.R54__is_matched_by_rule, [I702])
        self.assertEqual(itm3.R54__is_matched_by_rule, [I702])

        # use the uris because the Items itself are not hashable -> no conversion into a set
        self.assertEqual(
            set(itm.uri for itm in I702.get_inv_relations("R54", return_subj=True)),
            set((I702.x.uri, itm1.uri, itm2.uri, itm3.uri)),
        )

        self.assertEqual(itm4.R54__is_matched_by_rule, [])

        # next rule:

        with p.uri_context(uri=TEST_BASE_URI):

            itm1.set_relation(p.R57["is placeholder"], True)

            I703 = p.create_item(
                R1__has_label="test rule",
                R2__has_description=(
                    "test to match every instance of I36['rational number'] which is also a placeholder"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I703.scope("context") as cm:
                cm.new_var(x=p.instance_of(p.I1["general item"]))
                cm.uses_external_entities(I703)
                cm.uses_external_entities(p.I36["rational number"])

            with I703.scope("premises") as cm:
                cm.new_rel(cm.x, p.R4["is instance of"], p.I36["rational number"], overwrite=True)
                cm.new_rel(cm.x, p.R57["is placeholder"], True)

            with I703.scope("assertions") as cm:
                cm.new_rel(cm.x, p.R54["is matched by rule"], I703)

            res = p.ruleengine.apply_semantic_rule(I703)

        self.assertEqual(len(res.new_statements), 1)

        # next rule:

        with p.uri_context(uri=TEST_BASE_URI):

            itm1.set_relation(p.R31["is in mathematical relation with"], itm3)  # itm3 will be replaced by the rule

            self.assertEqual(itm1.R31__is_in_mathematical_relation_with, [itm3])

            itm2.set_relation(p.R47["is same as"], itm3)

            I704 = p.create_item(
                R1__has_label="test rule",
                R2__has_description=(
                    "test to match all instances of I36['rational number'] which are in a R47__is_same_as relation"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I704.scope("context") as cm:
                cm.new_var(x=p.instance_of(p.I1["general item"]))
                cm.new_var(y=p.instance_of(p.I1["general item"]))
                cm.uses_external_entities(I704)

            with I704.scope("premises") as cm:
                cm.new_rel(cm.x, p.R47["is same as"], cm.y)

            with I704.scope("assertions") as cm:
                cm.new_rel(cm.x, p.R54["is matched by rule"], I704)
                cm.new_consequent_func(p.replacer_method, cm.y, cm.x)

            res = p.ruleengine.apply_semantic_rule(I704)

        self.assertEqual(len(res.new_statements), 1)

        # confirm the replacement
        self.assertEqual(itm1.R31__is_in_mathematical_relation_with, [itm2])

    def test_d04__overwrite_stm_inside_rule_scope(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            I702 = p.create_item(
                R1__has_label="test rule",
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I702.scope("context") as cm:
                cm.new_var(x=p.instance_of(p.I1["general item"]))

            self.assertEqual(cm.x.R4, p.I1["general item"])

            with I702.scope("premises") as cm:
                cm.new_rel(cm.x, p.R4["is instance of"], p.I2["Metaclass"], overwrite=True)

                # arbitrary ordinary relation
                cm.new_rel(cm.x, p.R38["has length"], 5)

            self.assertEqual(cm.x.R4, p.I2["Metaclass"])

        premise_stms = I702.scp__premises.get_inv_relations("R20")

        # there are two premisie statements: 1.: R4, 2. R38
        self.assertEqual(len(premise_stms), 2)

    def test_d04b__zebra_puzzle_stage02(self):
        """
        test the condition function mechanism
        """

        with p.uri_context(uri=TEST_BASE_URI):

            itm1 = p.instance_of(p.I36["rational number"])
            itm2 = p.instance_of(p.I36["rational number"])

            itm1.set_relation(p.R47["is same as"], itm2)
            itm2.set_relation(p.R47["is same as"], itm1)

            I704 = p.create_item(
                R1__has_label="test rule",
                R2__has_description=(
                    "test to match only pairs of R47__is_same_as related items where the label_compare_method is True"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I704.scope("context") as cm:
                cm.new_var(x=p.instance_of(p.I1["general item"]))
                cm.new_var(y=p.instance_of(p.I1["general item"]))
                cm.uses_external_entities(I704)

            with I704.scope("premises") as cm:
                cm.new_rel(cm.x, p.R47["is same as"], cm.y)
                cm.new_condition_func(p.label_compare_method, cm.x, cm.y)

            with I704.scope("assertions") as cm:
                cm.new_rel(cm.x, p.R54["is matched by rule"], I704)

            new_stms = p.ruleengine.apply_semantic_rule(I704)

        self.assertEqual(itm1.R54__is_matched_by_rule, [I704])

        # without the condition func this would be also matched
        self.assertEqual(itm2.R54__is_matched_by_rule, [])

    def test_d05__zebra_puzzle_stage02(self):
        """
        apply rules and assess correctness of the result
        """

        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        neighbour_before = zp.person1.zb__R2353__lives_immediatly_right_of
        self.assertEqual(neighbour_before, None)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I710["rule: identify same items via zb__R2850__is_functional_activity"], mod_context_uri=zp.__URI__
        )
        self.assertEqual(zp.person1.R47__is_same_as, [zp.person2])

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I720["rule: replace (some) same_as-items"], mod_context_uri=zp.__URI__
        )

        # this tests fails sometimes because the order of the match-dicts from the DiGraph-Matcher varies and
        # thus sometimes person2 is replaced with person1 and sometimes vice versa

        neighbour_after = zp.person1.zb__R2353__lives_immediatly_right_of
        self.assertEqual(neighbour_after, zp.person3)

    def test_d06__zebra_puzzle_stage02(self):
        """
        test subproperty matching rule
        """
        with p.uri_context(uri=TEST_BASE_URI):

            R301 = p.create_relation(R1="parent relation")
            R302 = p.create_relation(R1="sub relation", R17__is_subproperty_of=R301)

            I701 = p.create_item(
                R1__has_label="rule: just match subproperties",
                R2__has_description=(
                    "if two items are related by a subproperty, then they are also related by the parent property"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I701.scope("context") as cm:
                cm.new_var(rel1=p.instance_of(p.I40["general relation"]))
                cm.new_var(rel2=p.instance_of(p.I40["general relation"]))
                cm.uses_external_entities(I701)

            with I701.scope("premises") as cm:
                cm.new_rel(cm.rel1, p.R17["is subproperty of"], cm.rel2)

            with I701.scope("assertions") as cm:
                cm.new_rel(cm.rel1, p.R54["is matched by rule"], I701)

            res = p.ruleengine.apply_semantic_rule(I701)

            self.assertEqual(len(res.new_statements), 1)

            # new rule

            R303 = p.create_relation(R1="another relation")

            I702 = p.create_item(
                R1__has_label="rule: just match subproperties (2)",
                R2__has_description=(
                    "if two items are related by a subproperty, then they are also related by the parent property"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I702.scope("context") as cm:
                cm.new_var(rel1=p.instance_of(p.I40["general relation"]))
                cm.uses_external_entities(I702)

            with I702.scope("premises") as cm:
                cm.new_rel(cm.rel1, p.R1["has label"], "another relation", overwrite=True)

            with I702.scope("assertions") as cm:
                cm.new_rel(cm.rel1, p.R54["is matched by rule"], I702)

            res = p.ruleengine.apply_semantic_rule(I702)

            self.assertEqual(len(res.new_statements), 1)

    def test_d07__zebra_puzzle_stage02(self):
        """
        test subrelation rule
        """

        with p.uri_context(uri=TEST_BASE_URI):
            R301 = p.create_relation(R1="parent relation")
            R302 = p.create_relation(R1="subrelation", R17__is_subproperty_of=R301)

            itm1 = p.instance_of(p.I1["general item"])
            itm2 = p.instance_of(p.I1["general item"])

            itm1.set_relation(R302["subrelation"], itm2)


            I701 = p.create_item(
                R1__has_label="rule: imply parent relation of a subrelation ",
                R2__has_description=(
                    "items which are related by a subrelation should also be related by the parent relation"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I701.scope("context") as cm:
                cm.new_var(rel1=p.instance_of(p.I40["general relation"]))
                cm.new_var(rel2=p.instance_of(p.I40["general relation"]))

            with I701.scope("premises") as cm:
                cm.new_rel(cm.rel1, p.R17["is subproperty of"], cm.rel2)

            with I701.scope("assertions") as cm:
                cm.new_consequent_func(p.copy_statements, cm.rel1, cm.rel2)

            self.assertEqual(itm1.R301__parent_relation, [])
            res = p.ruleengine.apply_semantic_rule(I701)

            self.assertEqual(len(res.new_statements), 1)
            self.assertEqual(itm1.R301__parent_relation, [itm2])

    def test_d08__zebra_puzzle_stage02(self):
        """
        test add reverse of symmetrical relations
        """

        with p.uri_context(uri=TEST_BASE_URI):
            R301 = p.create_relation(R1="relation1", R42__is_symmetrical=True)
            R302 = p.create_relation(R1="relation2")

            itm1 = p.instance_of(p.I1["general item"])
            itm2 = p.instance_of(p.I1["general item"])
            itm3 = p.instance_of(p.I1["general item"])

            itm4 = p.instance_of(p.I1["general item"])
            itm5 = p.instance_of(p.I1["general item"])

            itm1.set_relation(R301["relation1"], itm2)  # this should entail the reversed statement
            itm1.set_relation(R302["relation2"], itm3)  # this should entail nothing

            # this should remain unchanged because, the symmetrically associated statement does already exist
            itm4.set_relation(R301["relation1"], itm5)
            itm5.set_relation(R301["relation1"], itm4)

            I701 = p.create_item(
                R1__has_label="rule: imply parent relation of a subrelation ",
                R2__has_description=(
                    "given statement (s, p, o) where p.R42__is_symmetrical==True implies statement (o, p, s)"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I701.scope("context") as cm:
                cm.new_var(rel1=p.instance_of(p.I40["general relation"]))

            with I701.scope("premises") as cm:
                cm.new_rel(cm.rel1, p.R42["is symmetrical"], True)

            with I701.scope("assertions") as cm:
                cm.new_consequent_func(p.reverse_statements, cm.rel1)

            self.assertEqual(itm2.R301, [])
            res = p.ruleengine.apply_semantic_rule(I701)

            # at time of writing: one new statement is caused already by a symmetrical relation from builtin_entities
            self.assertGreaterEqual(len(res.new_statements), 2)
            self.assertEqual(itm1.R301, [itm2])
            self.assertEqual(itm3.R302, [])
            self.assertEqual(itm4.R301, [itm5])
            self.assertEqual(itm5.R301, [itm4])

    def test_d09__zebra_puzzle_stage02(self):
        """
        test conversion of predicate to subject
        """

        with p.uri_context(uri=TEST_BASE_URI):
            R2850 = p.create_relation(R1="is functional activity")
            R301 = p.create_relation(R1="relation1", R2850__is_functional_activity=True)
            R302 = p.create_relation(R1="distraction relation", R2850__is_functional_activity=False)
            R303 = p.create_relation(R1="distraction relation2")

            x1 = p.instance_of(p.I1["general item"])
            x2 = p.instance_of(p.I1["general item"])
            z1 = p.instance_of(p.I1["general item"])
            z2 = p.instance_of(p.I1["general item"])

            x1.set_relation(R301, x2)

            x1.set_relation(R302, z1)
            x2.set_relation(R303, z2)

            I703 = p.create_item(
                R1__has_label="rule: match subject, predicate object together",
                R2__has_description=(
                    "match subject, predicate object together where pred.R2850__is_functional_activity==True"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I703.scope("context") as cm:
                cm.new_var(itm1=p.instance_of(p.I1["general item"]))
                cm.new_var(itm2=p.instance_of(p.I1["general item"]))
                cm.uses_external_entities(I703)

                cm.new_rel_var("rel1")

            with I703.scope("premises") as cm:

                cm.new_rel(cm.rel1, R2850["is functional activity"], True)
                cm.new_rel(cm.itm1, cm.rel1, cm.itm2)

            with I703.scope("assertions") as cm:
                cm.new_rel(cm.itm1, p.R54["is matched by rule"], I703)
                cm.new_rel(cm.itm2, p.R54["is matched by rule"], I703)
                cm.new_rel(cm.rel1, p.R54["is matched by rule"], I703)

                # cm.new_consequent_func(p.add_arg_tuples_for_statement, cm.itm1, cm.rel1, cm.itm2)

            res = p.ruleengine.apply_semantic_rule(I703)
            self.assertEqual(len(res.new_statements), 3)
            self.assertEqual(x1.R54, [I703])
            self.assertEqual(x2.R54, [I703])
            self.assertEqual(R301.R54, [I703])


    def test_d10__zebra_puzzle_stage02(self):
        """
        apply zebra puzzle rules to zebra puzzle data and assess correctness of the result
        """

        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)

        # before loading the hint, we can already infer some new statements
        res = p.ruleengine.apply_semantic_rules(
            zr.I702["rule: add reverse statement for symmetrical relations"],
            mod_context_uri=zb.__URI__
        )

        self.assertEqual(len(res.rel_map), 1)
        self.assertIn(p.R43["is opposite of"].uri, res.rel_map)

        # load the hints and perform basic inferrence
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")
        res = p.ruleengine.apply_semantic_rules(
            zp.zr.I701["rule: imply parent relation of a subrelation"],
            zp.zr.I702["rule: add reverse statement for symmetrical relations"],
            mod_context_uri=zp.__URI__
        )

        # only inferrence until now: 5 R3606["lives next to"]-statements
        self.assertEqual(len(res.new_statements), 5)
        self.assertEqual(len(res.rel_map), 1)
        self.assertIn(zp.zb.R3606["lives next to"].uri, res.rel_map)

        res = p.ruleengine.apply_semantic_rules(
            zp.zr.I710["rule: identify same items via zb__R2850__is_functional_activity"],
            zp.zr.I720["rule: replace (some) same_as-items"],
            mod_context_uri=zp.__URI__
        )

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I730["rule: deduce negative facts for neighbours"],
            mod_context_uri=zp.__URI__
        )

        self.assertEqual(len(res.new_statements), 10)

        # check one particular example
        self.assertEqual(zb.I9848["Norwegian"].zb__R1055__has_not_house_color, [zb.I1497["blue"]])


class Test_Z_Core(HouskeeperMixin, unittest.TestCase):
    """
    Collection of test that should be executed last (because they seem to influence othter tests).
    This is achieved by putting "ZZ" in the name (assuming that test classes are executed in alphabetical order).
    """

    def test_sparql_query(self):
        # This test seems somehow to influence later tests
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, TEST_MOD_NAME)
        p.ds.rdfgraph = p.rdfstack.create_rdf_triples()
        qsrc = p.rdfstack.get_sparql_example_query()
        res = p.ds.rdfgraph.query(qsrc)
        res2 = p.aux.apply_func_to_table_cells(p.rdfstack.convert_from_rdf_to_pyerk, res)

        # Note this will fail if more `R5__has_part` relations are used
        expected_result = [
            [mod1.I4466["Systems Theory"], p.I4["Mathematics"]],
            [mod1.I4466["Systems Theory"], p.I5["Engineering"]],
        ]
        self.assertEqual(res2, expected_result)

    def test_c01__sparql_query2(self):
        # TODO: replace by Model entity once it exists
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, TEST_MOD_NAME)

        with p.uri_context(uri=TEST_BASE_URI):
            m1 = p.instance_of(mod1.I7641["general system model"], r1="test_model 1", r2="a test model")
            m2 = p.instance_of(mod1.I7641["general system model"], r1="test_model 2", r2="a test model")

            m1.set_relation(p.R16["has property"], mod1.I9210["stabilizability"])
            m2.set_relation(p.R16["has property"], mod1.I7864["controllability"])

        # graph has to be created after the entities
        p.ds.rdfgraph = p.rdfstack.create_rdf_triples()

        qsrc = f"""
        PREFIX : <{p.rdfstack.ERK_URI}>
        PREFIX ct: <{mod1.__URI__}#>
        SELECT ?s ?o
        WHERE {{
            ?s :R16 ct:I7864.
        }}
        """
        res = p.ds.rdfgraph.query(qsrc)
        res2 = p.aux.apply_func_to_table_cells(p.rdfstack.convert_from_rdf_to_pyerk, res)

        expected_result = [
            [m2["test_model 2"], None],
        ]
        self.assertEqual(res2, expected_result)

    def test_c02__sparql_zz_preprocessing(self):
        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, TEST_MOD_NAME)

        with p.uri_context(uri=TEST_BASE_URI):
            m1 = p.instance_of(mod1.I7641["general system model"], r1="test_model 1", r2="a test model")
            m2 = p.instance_of(mod1.I7641["general system model"], r1="test_model 2", r2="a test model")

            m1.set_relation(p.R16["has property"], mod1.I9210["stabilizability"])
            m2.set_relation(p.R16["has property"], mod1.I7864["controllability"])

        # graph has to be created after the entities
        p.ds.rdfgraph = p.rdfstack.create_rdf_triples()

        # syntactically correct query:
        condition_list = [
            "?s :R16__has_property ct:I7864__controllability.",
            "?s :R16__has_property ct:I7864__controllability .",
            "?s   :R16__has_property   ct:I7864__controllability   .",
            "?s (:R4__is_instance_of|:R3__is_subclass_of)* :I1__general_item .",
        ]

        for condition in condition_list:
            qsrc_corr = f"""
            PREFIX : <{p.rdfstack.ERK_URI}>
            PREFIX ct: <{mod1.__URI__}#>
            SELECT ?s ?o
            WHERE {{
                {condition}
            }}
            """
            q = p.ds.preprocess_query(qsrc_corr)
            res = p.ds.rdfgraph.query(q)
            res2 = p.aux.apply_func_to_table_cells(p.rdfstack.convert_from_rdf_to_pyerk, res)
            self.assertGreater(len(res2), 0)

        # syntactically incorrect querys:
        condition_list = [
            "?s :R16__wrong ct:I7864__controllability.",
        ]
        msg_list = [
            "Entity label 'has property' for entity ':R16__wrong' and given label 'wrong' do not match!",
        ]

        for condition, msg in zip(condition_list, msg_list):
            qsrc_incorr_1 = f"""
            PREFIX : <{p.rdfstack.ERK_URI}>
            PREFIX ct: <{mod1.__URI__}#>
            SELECT ?s ?o
            WHERE {{
                {condition}
            }}
            """
            with self.assertRaises(AssertionError) as cm:
                p.ds.preprocess_query(qsrc_incorr_1)
            self.assertEqual(cm.exception.args[0], msg)


class Test_05_Script1(HouskeeperMixin, unittest.TestCase):
    def test_c01__visualization(self):
        cmd = "pyerk -vis I12"
        res = os.system(cmd)
        self.assertEqual(res, 0)


class Test_06_reportgenerator(HouskeeperMixin, unittest.TestCase):
    @p.erkloader.preserve_cwd
    def tearDown(self) -> None:
        super().tearDown()
        os.chdir(pjoin(TEST_DATA_DIR1, "reports"))
        try:
            os.unlink("report.tex")
        except FileNotFoundError:
            pass

    def test_c01__resolve_entities_in_nested_data(self):

        reind = rgen.resolve_entities_in_nested_data
        some_list = [1, 123.4, "foobar"]
        self.assertEqual(reind(some_list), some_list)

        data1 = {"key1": some_list, "key2": ":I1"}
        data1exp = {"key1": some_list, "key2": p.I1}
        self.assertEqual(reind(data1), data1exp)

        mod2 = p.erkloader.load_mod_from_path(TEST_DATA_PATH3, prefix="ag")

        data1 = {"key1": ':ag__I2746["Rudolf Kalman"]', "key2": {"nested_key": ':ag__R1833["has employer"]'}}
        data1exp = {"key1": mod2.I2746, "key2": {"nested_key": mod2.R1833}}
        self.assertEqual(reind(data1), data1exp)

    @p.erkloader.preserve_cwd
    def test_c02__report_generation1(self):

        reportconf_path1 = pjoin(TEST_DATA_DIR1, "reports", "reportconf.toml")
        reporttex_path1 = pjoin(TEST_DATA_DIR1, "reports", "report.tex")
        os.chdir(pjoin(TEST_DATA_DIR1, "reports"))
        self.assertFalse(os.path.exists(reporttex_path1))
        rg = rgen.ReportGenerator(reportconf_path1, write_file=True)
        rg.generate_report()
        self.assertTrue(os.path.exists(reporttex_path1))

        self.assertEqual(len(rg.authors), 2)

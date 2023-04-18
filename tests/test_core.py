import unittest
import sys
import os
from os.path import join as pjoin
from typing import Dict, List, Union

import rdflib

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception, set_trace  # noqa
import pyerk as p
import pyerk.visualization as visualization
import pyerk.io
from pyerk.auxiliary import uri_set
import git
import pyerk.reportgenerator as rgen


from .settings import (
    ERK_ROOT_DIR,
    TEST_DATA_DIR1,
    TEST_DATA_PARENT_PATH,
    TEST_DATA_REPO_PATH,
    TEST_DATA_PATH2,
    TEST_DATA_PATH_MA,
    TEST_DATA_PATH3,
    TEST_DATA_PATH_ZEBRA_BASE_DATA,
    TEST_DATA_PATH_ZEBRA02,
    TEST_MOD_NAME,
    TEST_DATA_REPO_COMMIT_SHA,
    # TEST_ACKREP_DATA_FOR_UT_PATH,
    TEST_BASE_URI,
    WRITE_TMP_FILES,
    HouskeeperMixin,
   
    
    )



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
            itm1.set_relation(p.R1["has label"], "neues Label" @ p.de)

            with self.assertRaises(p.aux.FunctionalRelationError):
                itm1.set_relation(p.R1["has label"], "new label")

    def test_c03__nontrivial_metaclasses(self):
        with p.uri_context(uri=TEST_BASE_URI):
            i1 = p.instance_of(p.I34["complex number"])

        self.assertTrue(i1.R4, p.I34)

    def test_c04__evaluated_mapping(self):

        res = p.ds.statements.get("S6229")
        self.assertIsNone(res)

        ct = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        with p.uri_context(uri=TEST_BASE_URI):
            poly1 = p.instance_of(ct.I4239["monovariate polynomial"])

        # test that an arbitrary item is *not* callable
        self.assertRaises(TypeError, ct.ma.I2738["field of complex numbers"], 0)

        # test that some special items are callable (note that its parent class is a subclass of one which has
        # a _custom_call-method defined)
        with p.uri_context(uri=TEST_BASE_URI):
            # this creates new items and thus must be executed inside a context
            res = poly1(0)

        self.assertEqual(res.R4__is_instance_of, p.I32["evaluated mapping"])

        with p.uri_context(uri=TEST_BASE_URI):
            x = p.instance_of(p.I35["real number"])
            s1 = ct.ma.I5807["sign"](x)
            s2 = ct.ma.I5807["sign"](x)
            self.assertTrue(s1 is s2)


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

    def test_c07b__nested_scopes_of_propositions(self):
        """
        Test existentially and universally quantified conditions as nested scopes in scopes of propositions/definitions
        """
        with p.uri_context(uri=TEST_BASE_URI):
            I7324 = p.create_item(
                R1__has_label = "definition of something",
                R4__is_instance_of =p.I20["mathematical definition"],
            )

            my_set = p.instance_of(p.I13["mathematical set"])
            my_prop = p.instance_of(p.I11["mathematical property"])

            with I7324["definition of something"].scope("setting") as cm:
                x = cm.new_var(x=p.instance_of(p.I39["positive integer"]))
                y = cm.new_var(y=p.instance_of(p.I39["positive integer"]))

            with I7324["definition of something"].scope("premise") as cm:
                with cm.universally_quantified() as cm2:
                    cm2.add_condition_statement(cm.x, p.R15["is element of"], my_set)
                    cm2.add_condition_statement(cm.y, p.R15["is element of"], my_set)

                    # note: the meaning of this equation is pointless, we just test the implementation of subscopes
                    cm2.new_equation(lhs=cm.x, rhs=cm.y)

            with I7324["definition of something"].scope("assertion") as cm:
                cm.new_rel(cm.x, p.R16["has property"], my_prop)
                cm.new_rel(cm.y, p.R16["has property"], my_prop)

                # also pointless direct meaning, only to test contexts
                with cm.existentially_quantified() as cm2:
                    z = cm2.new_condition_var(z=p.instance_of(p.I39["positive integer"]))
                    cm2.add_condition_statement(cm2.z, p.R15["is element of"], my_set)
                    cm2.add_condition_statement(cm.y, p.R15["is element of"], my_set)
                    cm2.add_condition_math_relation(cm2.z, "<", cm.x)

                    cm2.new_math_relation(cm2.z, ">", cm.y)

            # universally quantified scope

            scp_prem = I7324.get_subscopes()[1]
            prem_sub_scopes = scp_prem.get_subscopes()
            self.assertEqual(len(prem_sub_scopes), 1)
            uq_scp = prem_sub_scopes[0]
            self.assertEqual(uq_scp.R64__has_scope_type, "UNIV_QUANT")

            # check the condition
            cond_sc = uq_scp.get_subscopes()[0]
            cond_stms = cond_sc.get_statements_for_scope()
            stm1: p.Statement = cond_stms[0]
            self.assertEqual(stm1.subject, x)
            self.assertEqual(stm1.predicate, p.R15["is element of"])
            self.assertEqual(stm1.object, my_set)

            # check the actual statement (which is an equation)
            stm1, = uq_scp.get_statements_for_scope()
            self.assertEqual(stm1.subject, x)
            self.assertEqual(stm1.predicate, p.R31["is in mathematical relation with"])
            self.assertEqual(stm1.object, y)

            proxy_item = stm1.get_first_qualifier_obj_with_rel("R34__has_proxy_item")
            self.assertEqual(proxy_item.R4__is_instance_of, p.I23["equation"])
            self.assertEqual(proxy_item.R26__has_lhs, x)
            self.assertEqual(proxy_item.R27__has_rhs, y)

            # existentially quantified scope

            scp_asstn = I7324.get_subscopes()[2]
            self.assertEqual(len(scp_asstn.get_subscopes()), 1)
            ex_scp = scp_asstn.get_subscopes()[0]
            self.assertEqual(ex_scp.R64__has_scope_type, "EXIS_QUANT")

            # check the conditions
            cond_sc = ex_scp.get_subscopes()[0]
            cond_itms = cond_sc.get_items_for_scope()
            self.assertEqual(len(cond_itms), 2)
            self.assertIn(z, cond_itms)
            # apart from z there is also the cond_proxy_item, see below

            cond_stms = cond_sc.get_statements_for_scope()
            self.assertEqual(len(cond_stms), 3)
            stm1: p.Statement = cond_stms[0]
            self.assertEqual(stm1.subject, z)
            self.assertEqual(stm1.predicate, p.R15["is element of"])
            self.assertEqual(stm1.object, my_set)

            stm3: p.Statement = cond_stms[2]
            self.assertEqual(stm3.subject, z)
            self.assertEqual(stm3.predicate, p.R31["is in mathematical relation with"])
            self.assertEqual(stm3.object, x)

            cond_proxy_item = stm3.get_first_qualifier_obj_with_rel("R34__has_proxy_item")
            self.assertIn(cond_proxy_item, cond_itms)
            self.assertEqual(cond_proxy_item.R4__is_instance_of, p.I29["less-than-relation"])
            self.assertEqual(cond_proxy_item.R26__has_lhs, z)
            self.assertEqual(cond_proxy_item.R27__has_rhs, x)

            # check the actual statement (which is an equation)
            stm1, = ex_scp.get_statements_for_scope()
            self.assertEqual(stm1.subject, z)
            self.assertEqual(stm1.predicate, p.R31["is in mathematical relation with"])
            self.assertEqual(stm1.object, y)

            proxy_item = stm1.get_first_qualifier_obj_with_rel("R34__has_proxy_item")
            self.assertEqual(proxy_item.R4__is_instance_of, p.I28["greater-than-relation"])
            self.assertEqual(proxy_item.R26__has_lhs, z)
            self.assertEqual(proxy_item.R27__has_rhs, y)

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
        itm1: p.Item = p.ds.get_entity_by_key_str("ct__I3749__Cayley_Hamilton_theorem")

        # get item via key and uri
        itm2: p.Item = p.ds.get_entity_by_key_str("I3749__Cayley_Hamilton_theorem", mod_uri=mod1.__URI__)

        self.assertEqual(itm1, itm2)

        itm1_setting_namespace = itm1._ns_context
        # alternative way to access names (graph based but bulky): itm1.scp__context.get_inv_relations("R20"), ...

        Z: p.Item = itm1_setting_namespace["Z"]

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
        P: p.Item = itm1_setting_namespace["P"]
        A: p.Item = itm1_setting_namespace["A"]
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

        wrapped_func = p.wrap_function_with_search_uri_context(test_func, ma.__URI__)

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

    def test_d09__raise_invalid_scope_name_error(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            prop = p.instance_of(p.I15["implication proposition"])

            scp1 = prop.scope("setting")

            with self.assertRaises(p.aux.InvalidScopeNameError):
                prop.scope("setting")

            scp2 = prop.scope("premise")

        self.assertNotEqual(scp1, scp2)

    def test_d10__set_multiple_statements(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            itm1 = p.instance_of(p.I1["general item"])
            itm2 = p.instance_of(p.I1["general item"])
            itm3 = p.instance_of(p.I1["general item"])

            x = p.instance_of(p.I1["general item"])

            self.assertEquals(itm1.R57__is_placeholder, None)
            self.assertEquals(itm2.R57__is_placeholder, None)

            stms = p.set_multiple_statements((itm1, itm2), p.R57["is placeholder"], True)
            self.assertEquals(len(stms), 2)
            self.assertEquals(itm1.R57__is_placeholder, True)
            self.assertEquals(itm2.R57__is_placeholder, True)

            tup = p.new_tuple(itm1, itm2, itm3)
            stms = p.set_multiple_statements(tup.R39__has_element, p.R31["is in mathematical relation with"], x)

            self.assertEquals(len(stms), 3)

            self.assertEquals(itm1.R31__is_in_mathematical_relation_with, [x])
            self.assertEquals(itm2.R31__is_in_mathematical_relation_with, [x])
            self.assertEquals(itm3.R31__is_in_mathematical_relation_with, [x])

    def test_d11__get_subjects_for_relation(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            itm1 = p.instance_of(p.I1["general item"])
            itm2 = p.instance_of(p.I1["general item"])
            itm3 = p.instance_of(p.I1["general item"])
            itm4 = p.instance_of(p.I1["general item"])

            R301 = p.create_relation(R1="test relation")

            itm1.set_relation(R301, True)
            itm2.set_relation(R301, False)
            itm3.set_relation(R301, 15)

            subj_list = p.ds.get_subjects_for_relation(R301.uri)

            self.assertEqual(uri_set(*subj_list), uri_set(itm1, itm2, itm3))

            itm1.set_relation(R301, 15)
            itm4.set_relation(R301, 15)

            subj_list = p.ds.get_subjects_for_relation(R301.uri, filter=15)
            self.assertEqual(uri_set(*subj_list), uri_set(itm1, itm3, itm4))

    def test_d12__prevent_duplicates(self):

        with p.uri_context(uri=TEST_BASE_URI, prefix="ut"):

            itm1 = p.instance_of(p.I1["general item"])
            R301 = p.create_relation(R1="test relation")

            itm1.set_relation(R301, True)
            itm1.set_relation(R301, True)

            self.assertEqual(len(itm1.R301), 2)
            itm1.set_relation(R301, True, prevent_duplicate=True)
            self.assertEqual(len(itm1.R301), 2)

    def test_d13__check_type(self):

        import json

        # created with json.dumps and textwrap.fill(json_str, width=100)
        raw_data = """
        {"erk:/ocse/0.2/zebra_base_data#R8216": [[5, "erk:/ocse/0.2/zebra_base_data#I4037"], [5,
        "erk:/ocse/0.2/zebra_base_data#I9848"], [5, "erk:/ocse/0.2/zebra_base_data#I3132"], [5,
        "erk:/ocse/0.2/zebra_base_data#I2552"], [5, "erk:/ocse/0.2/zebra_base_data#I5931"]],
        "erk:/ocse/0.2/zebra_base_data#R9040": [[5, "erk:/ocse/0.2/zebra_base_data#I4037"], [5,
        "erk:/ocse/0.2/zebra_base_data#I9848"], [5, "erk:/ocse/0.2/zebra_base_data#I3132"], [5,
        "erk:/ocse/0.2/zebra_base_data#I2552"], [5, "erk:/ocse/0.2/zebra_base_data#I5931"]],
        "erk:/ocse/0.2/zebra_base_data#R5611": [[5, "erk:/ocse/0.2/zebra_base_data#I4037"], [5,
        "erk:/ocse/0.2/zebra_base_data#I9848"], [5, "erk:/ocse/0.2/zebra_base_data#I3132"], [5,
        "erk:/ocse/0.2/zebra_base_data#I2552"], [5, "erk:/ocse/0.2/zebra_base_data#I5931"]],
        "erk:/ocse/0.2/zebra_base_data#R8098": [[5, "erk:/ocse/0.2/zebra_base_data#I4037"], [5,
        "erk:/ocse/0.2/zebra_base_data#I9848"], [5, "erk:/ocse/0.2/zebra_base_data#I3132"], [5,
        "erk:/ocse/0.2/zebra_base_data#I2552"], [5, "erk:/ocse/0.2/zebra_base_data#I5931"]],
        "erk:/ocse/0.2/zebra_base_data#R8592": [[5, "erk:/ocse/0.2/zebra_base_data#I4037"], [5,
        "erk:/ocse/0.2/zebra_base_data#I9848"], [5, "erk:/ocse/0.2/zebra_base_data#I3132"], [5,
        "erk:/ocse/0.2/zebra_base_data#I2552"], [5, "erk:/ocse/0.2/zebra_base_data#I5931"]]}
        """.replace("\n","")
        data = json.loads(raw_data)

        self.assertFalse(p.check_type(data, Dict[str, int], strict=False))
        self.assertFalse(p.check_type(data, Dict[str, dict], strict=False))
        self.assertFalse(p.check_type(data, Dict[str, Dict], strict=False))
        self.assertFalse(p.check_type(data, Dict[str, List[int]], strict=False))
        self.assertFalse(p.check_type(data, Dict[str, List[List[int]]], strict=False))

        # pydantic has nontrivial behavior abour Unions. This requires smart_unions=True
        q = [5, 'erk:/ocse/0.2/zebra_base_data#I9848']
        p.check_type(q, List[Union[int, str]])

        # this is what we actually want to test (note that the inner list could be specified more precisely)
        self.assertTrue(p.check_type(data, Dict[str, List[List[Union[int, str]]]], strict=False))


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
        value_container_list = all_rels[key]
        value_container: p.ruleengine.Container = value_container_list[0]

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

        self.assertEqual(len(ra.ra_workers), 1)
        ra_worker = ra.ra_workers[0]

        self.assertEqual(len(ra_worker.get_asserted_relation_templates()), 1)

        self.assertEqual(ra_worker.P.number_of_nodes(), 3)
        self.assertEqual(ra_worker.P.number_of_edges(), 2)

        res_graph = ra_worker.match_subgraph_P()

        # ensures that the rule does not match itself
        self.assertEqual(len(res_graph), 0)

        # in this erk module some properties have subproperties
        _ = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct", modname=TEST_MOD_NAME)

        # create a new RuleApplicator because the overal graph changed
        ra = p.ruleengine.RuleApplicator(self.rule1)
        ra_worker = ra.ra_workers[0]
        res_graph = ra_worker.match_subgraph_P()
        self.assertGreater(len(res_graph), 5)

    def test_c05__ruleengine04(self):
        self.setup_data1()

        mod1 = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct", modname=TEST_MOD_NAME)
        self.assertEqual(len(mod1.I9642["local exponential stability"].get_relations("R17__is_subproperty_of")), 1)
        ra = p.ruleengine.RuleApplicator(self.rule1, mod_context_uri=TEST_BASE_URI)
        res = ra.apply()

        # ensure that after rule application there new relations
        self.assertEqual(len(mod1.I9642["local exponential stability"].get_relations("R17__is_subproperty_of")), 3)

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


class Test_07_import_export(HouskeeperMixin, unittest.TestCase):

    def test_b01__rdf_export(self):

        with p.uri_context(uri=TEST_BASE_URI):
            R301 = p.create_relation(R1="relation1")
            R302 = p.create_relation(R1="test qualifier")

            QF_R302 = p.QualifierFactory(R302["test qualifier"])

            x0 = p.instance_of(p.I35["real number"])
            x1 = p.instance_of(p.I35["real number"])
            x2 = p.instance_of(p.I35["real number"])

            # create two qualifiers (one with a literal object-value and one with x2 as object-value)
            stm = x0.set_relation(R301, x1, qualifiers=[QF_R302(True), QF_R302(x2)])  # noqa

        q_stms = [v for v in p.ds.stms_created_in_mod[TEST_BASE_URI].values() if v.is_qualifier()]
        self.assertEquals(len(q_stms), 2)

        fpath = pjoin(TEST_DATA_DIR1, "tmp_test.nt")
        p.io.export_rdf_triples(fpath, add_qualifiers=True,  modfilter=TEST_BASE_URI)
        g = p.io.import_raw_rdf_triples(fpath)
        os.unlink(fpath)

        self.assertGreater(len(g), 40)

    def test_b02__rdf_import(self):

        fpath = pjoin(TEST_DATA_DIR1, "test_triples1.nt")

        with p.uri_context(uri=TEST_BASE_URI):
            # the labels will be overwritten
            R301 = p.create_relation(R1="__foo__ relation1")
            R302 = p.create_relation(R1="__foo__ test qualifier")  # noqa

            c = p.io.import_stms_from_rdf_triples(fpath)

            c.new_items.sort(key=lambda itm: itm.R1__has_label)

            x0, x1, x2 = c.new_items
            # test that overwriting worked
            self.assertEqual(R301.R1__has_label, "relation1")

            # test that a statement has been created
            self.assertEqual(x0.R301__relation1, [x1])

    def test_b03__zebra_puzzle_import(self):
        """
        match persons which have four negative statements of the same kind (test statement relations)
        """
        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")

        self.assertEqual(zb.I9848["Norwegian"].zb__R8098__has_house_color, None)
        self.assertEqual(zb.I9848["Norwegian"].zb__R1055__has_not_house_color, [])

        # test to load facts

        fpath = pjoin(TEST_DATA_DIR1, "test_zebra_triples1.nt")
        with p.uri_context(uri=TEST_BASE_URI):
            c = p.io.import_stms_from_rdf_triples(fpath)  #noqa
        self.assertEqual(zb.I9848["Norwegian"].zb__R8098__has_house_color, zb.I4118["yellow"])
        self.assertEqual(len(zb.I9848["Norwegian"].zb__R1055__has_not_house_color), 4)

    def test_b04__zebra_puzzle_unlinked_items(self):
        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        # persons1 ... person12 exists -> if they are unlinked within a module this is not yet reflected in the
        # rdf-data -> TODO: introduce a "Housekeeping" item for every module

        # this tests ensures that at least the unlinked item is not present in the rdfgrap

        with p.uri_context(uri=TEST_BASE_URI):
            zp.person10.set_relation(zb.R8098["has house color"], zb.I7612["ivory"])
            zp.person11.set_relation(zb.R8098["has house color"], zb.I4118["yellow"])
            zp.person10.set_relation(zb.R3606["lives next to"], zp.person11)


        fpath = pjoin(TEST_DATA_DIR1, "tmp_test.nt")
        p.io.export_rdf_triples(fpath, add_qualifiers=True,  modfilter=TEST_BASE_URI)
        g = p.io.import_raw_rdf_triples(fpath)

        self.assertTrue(rdflib.URIRef(zp.person11.uri) in g.subjects())
        self.assertTrue(rdflib.URIRef(zp.person11.uri) in g.objects())

        p.core._unlink_entity(zp.person11.uri, remove_from_mod=True)

        p.io.export_rdf_triples(fpath, add_qualifiers=True,  modfilter=TEST_BASE_URI)
        g = p.io.import_raw_rdf_triples(fpath)

        self.assertFalse(rdflib.URIRef(zp.person11.uri) in g.subjects())
        self.assertFalse(rdflib.URIRef(zp.person11.uri) in g.objects())

        os.unlink(fpath)

import unittest
import os
from os.path import join as pjoin
from typing import Dict, List, Tuple

import rdflib

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception, set_trace  # noqa
import pyerk as p
import pyerk.io
from addict import Addict as Container
import pyerk.reportgenerator as rgen


from .settings import (
    TEST_DATA_DIR1,
    TEST_DATA_PATH2,
    TEST_DATA_PATH3,
    TEST_DATA_PATH_ZEBRA_BASE_DATA,
    TEST_DATA_PATH_ZEBRA01,
    TEST_DATA_PATH_ZEBRA02,
    TEST_DATA_PATH_ZEBRA_RULES,
    TEST_MOD_NAME,
    # TEST_ACKREP_DATA_FOR_UT_PATH,
    TEST_BASE_URI,
    HouskeeperMixin,
   
)


class Test_01_rulebased_reasoning(HouskeeperMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def setup_data1(self):
        pass

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

        neighbour = zp.person1.zb__R2353__lives_immediately_right_of
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

        neighbour = zp.person1.zb__R2353__lives_immediately_right_of
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

            itm2.set_relation(p.R47["is same as"], itm3)  # itm3 will be replaced by the rule

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
                cm.uses_external_entities(p.I36['rational number'])

            with I704.scope("premises") as cm:
                cm.new_rel(cm.x, p.R4["is instance of"], p.I36['rational number'], overwrite=True)
                cm.new_rel(cm.x, p.R47["is same as"], cm.y)

            with I704.scope("assertions") as cm:
                cm.new_consequent_func(p.replacer_method, cm.y, cm.x)

            res = p.ruleengine.apply_semantic_rule(I704)

        self.assertEqual(len(res.new_statements), 2)

        # confirm the replacement
        self.assertEqual(itm1.R31__is_in_mathematical_relation_with, [itm2])
        self.assertTrue(itm3._unlinked, True)

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

        neighbour_before = zp.person1.zb__R2353__lives_immediately_right_of
        self.assertEqual(neighbour_before, None)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I710["rule: identify same items via zb__R2850__is_functional_activity"], mod_context_uri=zp.__URI__
        )
        self.assertEqual(zp.person1.R47__is_same_as, [zp.person2])

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I720["rule: replace (some) same_as-items"], mod_context_uri=zp.__URI__
        )

        self.assertFalse(zp.person1._unlinked)

        self.assertIn((zp.person9, zp.person5), res.replacements)
        self.assertIn((zp.person2, zp.person1), res.replacements)
        neighbour_after = zp.person1.zb__R2353__lives_immediately_right_of
        self.assertEqual(neighbour_after, zp.person3)

    def test_d06__zebra_puzzle_stage02(self):
        """
        test subproperty matching rule
        """
        with p.uri_context(uri=TEST_BASE_URI):

            R301 = p.create_relation(R1="parent relation")
            R302 = p.create_relation(R1="subrelation", R17__is_subproperty_of=R301)

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

            # define another (incomplete) rule which is never applied
            # ensure that above rule is not applied to the items defined in the scope of this rule
            I763 = p.create_item(
                R1__has_label="test rule",
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I763.scope("context") as cm:
                cm.new_var(p1=p.instance_of(p.I1["general item"]))
                cm.new_var(p2=p.instance_of(p.I1["general item"]))

            with I763.scope("premises") as cm:
                cm.new_rel(cm.p1, R302["subrelation"], cm.p2)

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

            R303 = p.create_relation(R1="relation3")
            R304 = p.create_relation(R1="relation3", R68__is_inverse_of=R303)

            itm1 = p.instance_of(p.I1["general item"])
            itm2 = p.instance_of(p.I1["general item"])
            itm3 = p.instance_of(p.I1["general item"])

            itm4 = p.instance_of(p.I1["general item"])
            itm5 = p.instance_of(p.I1["general item"])
            itm6 = p.instance_of(p.I1["general item"])

            itm1.set_relation(R301["relation1"], itm2)  # this should entail the reversed statement
            itm1.set_relation(R302["relation2"], itm3)  # this should entail nothing

            # this should remain unchanged because, the symmetrically associated statement does already exist
            itm4.set_relation(R301["relation1"], itm5)
            itm5.set_relation(R301["relation1"], itm4)

            itm6.set_relation(p.R43["is opposite of"], itm4)

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

            # at time of writing: two new statement are caused already by symmetrical relations from builtin_entities
            # R43["is opposite of"] and R68["is inverse of"]
            # thus we expect 3 here (or more if builtin_entities got more symmetrical relations, which are also applied)
            self.assertGreaterEqual(len(res.new_statements), 3)
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
        test to match variable literal values (and result report)
        """

        with p.uri_context(uri=TEST_BASE_URI):
            R301 = p.create_relation(R1="semantic relation")
            R302 = p.create_relation(R1="data attribute")

            x1 = p.instance_of(p.I1["general item"])
            x2 = p.instance_of(p.I1["general item"])
            z1 = p.instance_of(p.I1["general item"])
            z2 = p.instance_of(p.I1["general item"])

            x1.set_relation(R302, 42)
            x1.set_relation(R301, x2)

            z1.set_relation(R302, 3.1415)
            z1.set_relation(R301, z2)

            I703 = p.create_item(
                R1__has_label="rule: match literal variable values",
                R2__has_description=(
                    "match literal objects as nodes, such that they can be used in consequent functions"
                ),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I703.scope("context") as cm:
                cm.new_var(var1=p.instance_of(p.I1["general item"]))
                cm.new_var(var2=p.instance_of(p.I1["general item"]))
                cm.new_variable_literal("val1")

            with I703.scope("premises") as cm:

                cm.new_rel(cm.var1, R301["semantic relation"], cm.var2)
                cm.new_rel(cm.var1, R302["data attribute"], cm.val1)

            with I703.scope("assertions") as cm:
                cm.new_rel(cm.var1, R302, "good")
                cm.new_rel(cm.var2, R302, cm.val1)

            res = p.ruleengine.apply_semantic_rule(I703)
            self.assertEqual(x1.R302[-1], "good")
            self.assertEqual(z1.R302[-1], "good")

            self.assertEqual(x2.R302[-1], 42)
            self.assertEqual(z2.R302[-1], 3.1415)

            # new rule: match on same literal value (for R303)

            y1 = p.instance_of(p.I1["general item"])
            y2 = p.instance_of(p.I1["general item"])

            R303 = p.create_relation(R1="new data attribute")

            x1.set_relation(R303, 210)
            x2.set_relation(R303, 220)

            y1.set_relation(R303, 210)  # same as x1
            y2.set_relation(R303, 220)  # same as z1

            I704 = p.create_item(
                R1__has_label="rule: match items with same literal values",
                R2__has_description=("match items with same (a priori unknown) literal values"),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I704.scope("context") as cm:
                cm.new_var(var1=p.instance_of(p.I1["general item"]))
                cm.new_var(var2=p.instance_of(p.I1["general item"]))
                cm.new_variable_literal("val1")

            with I704.scope("premises") as cm:

                cm.new_rel(cm.var1, R303["new data attribute"], cm.val1)
                cm.new_rel(cm.var2, R303["new data attribute"], cm.val1)

            with I704.scope("assertions") as cm:
                cm.new_rel(cm.var1, R301, cm.var2)

            res = p.ruleengine.apply_semantic_rule(I704)

            self.assertEqual(len(res.new_statements), 4)
            self.assertEqual(y1.R301[-1], x1)
            self.assertEqual(y2.R301[-1], x2)

            # test the presence of the reporting data structures
            self.assertEqual(len(res.partial_results[0].statement_reports), 4)


    def test_d11__zebra_puzzle_stage02(self):
        """
        test to match the nonexistence of some specific statements
        """

        with p.uri_context(uri=TEST_BASE_URI):
            R301 = p.create_relation(R1="semantic relation")
            R302 = p.create_relation(R1="data attribute")

            x1 = p.instance_of(p.I1["general item"])
            x2 = p.instance_of(p.I1["general item"])
            x3 = p.instance_of(p.I1["general item"])
            x4 = p.instance_of(p.I1["general item"])

            x1.set_relation(R302, 1)
            x2.set_relation(R302, 1)
            x3.set_relation(R302, 1)
            x4.set_relation(R302, 1)

            x1.set_relation(R301, x2)
            x2.set_relation(R301, x3)

            # try to find those items which have no R301 relation
            I703 = p.create_item(
                R1__has_label="rule: match the nonexistence of some specific statements",
                R2__has_description=("match the nonexistence of some specific statements"),
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I703.scope("context") as cm:
                cm.new_var(var1=p.instance_of(p.I1["general item"]))
                cm.uses_external_entities(R301)

            with I703.scope("premises") as cm:
                cm.new_rel(cm.var1, R302["data attribute"], 1)
                cm.new_condition_func(p.does_not_have_relation, cm.var1, R301["semantic relation"])

            with I703.scope("assertions") as cm:
                cm.new_rel(cm.var1, R302, "good")

            res = p.ruleengine.apply_semantic_rule(I703)

            self.assertEqual(len(res.new_statements), 2)
            self.assertEqual(x3.R302[-1], "good")
            self.assertEqual(x4.R302[-1], "good")

    def test_d12__zebra_puzzle_stage02(self):
        """
        test OR and AND subscopes in premises
        """

        with p.uri_context(uri=TEST_BASE_URI):
            R301 = p.create_relation(R1="semantic relation")
            R302 = p.create_relation(R1="data attribute")

            x0 = p.instance_of(p.I35["real number"])
            x1 = p.instance_of(p.I35["real number"])
            x2 = p.instance_of(p.I35["real number"])
            x3 = p.instance_of(p.I35["real number"])
            x4 = p.instance_of(p.I35["real number"])

            x0.set_relation(R302, 0)
            x1.set_relation(R302, 10)
            x2.set_relation(R302, 20)
            x3.set_relation(R302, 20)

            x4.set_relation(R302, 30)

            x1.set_relation(R301, x0)
            x2.set_relation(R301, x0)

            I703 = p.create_item(
                R1__has_label="rule with OR-subscope in premises",
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I703.scope("context") as cm:
                cm.new_var(var0=p.instance_of(p.I1["general item"]))
                cm.new_var(var1=p.instance_of(p.I1["general item"]))

                with self.assertRaises(p.aux.SemanticRuleError):
                    # try to create a logical subscope but not in premise-scope -> error
                    with cm.OR():
                        pass

            with I703.scope("premises") as cm:

                # this condition must hold in all cases:
                cm.new_rel(cm.var1, R301, cm.var0)

                with cm.OR() as cm_OR:
                    # one of these two conditions must hold
                    cm_OR.new_rel(cm.var1, R302, 10)
                    cm_OR.new_rel(cm.var1, R302, 20)

                    # test error-raising to prevent unintended mis-association of scopes
                    with self.assertRaises(p.aux.InvalidScopeNameError):
                        cm.new_rel(cm.var1, R302, 20)

            with I703.scope("assertions") as cm:
                cm.new_rel(cm.var1, R302, "good")

            res = p.ruleengine.apply_semantic_rule(I703)

            self.assertEqual(I703.scp__premises.scp__OR.R4, p.I16["scope"])

            self.assertEqual(x1.R302[-1], "good")
            self.assertEqual(x2.R302[-1], "good")
            self.assertNotEqual(x3.R302[-1], "good")
            self.assertNotEqual(x4.R302[-1], "good")

            # new rule

            c1 = p.instance_of(p.I34["complex number"])

            I704 = p.create_item(
                R1__has_label="rule with OR-and-AND-subscopes in premises",
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I704.scope("context") as cm:
                cm.new_var(var0=p.instance_of(p.I1["general item"]))
                cm.new_var(var1=p.instance_of(p.I1["general item"]))

                cm.uses_external_entities(p.I35["real number"])

            with I704.scope("premises") as cm:

                # this condition must hold in all cases:
                cm.new_rel(cm.var1, p.R4["is instance of"], p.I35["real number"], overwrite=True)

                with cm.OR() as cm_OR:
                    # either (var1 == 0) or (var1 == 10) and (var1 R301-related to some var0)
                    cm_OR.new_rel(cm.var1, R302, 30)  # met by x4
                    with cm_OR.AND() as cm_AND:
                        # met by x1
                        cm_AND.new_rel(cm.var1, R302, 10)
                        cm_AND.new_rel(cm.var1, R301, cm.var0)

            with I704.scope("assertions") as cm:
                cm.new_rel(cm.var1, R302, "good2")

            res = p.ruleengine.apply_semantic_rule(I704)

            self.assertEqual(len(res.new_statements), 2)
            self.assertEqual(x4.R302[-1], "good2")
            self.assertEqual(x1.R302[-1], "good2")

    def test_d13__zebra_puzzle_stage02(self):
        """
        match nodes with multiple edges between them
        """

        with p.uri_context(uri=TEST_BASE_URI):
            R301 = p.create_relation(R1="relation1")
            R302 = p.create_relation(R1="relation2")

            x0 = p.instance_of(p.I35["real number"])
            x1 = p.instance_of(p.I35["real number"])
            x2 = p.instance_of(p.I35["real number"])

            x0.set_relation(R301, x1)
            x0.set_relation(R302, x1)
            x1.set_relation(R302, x2)


            I601 = p.create_item(
                R1__has_label="simple rule",
                R4__is_instance_of=p.I41["semantic rule"],
            )

            with I601.scope("context") as cm:
                cm.new_var(itm1=p.instance_of(p.I1["general item"]))
                cm.new_var(itm2=p.instance_of(p.I1["general item"]))

            with I601.scope("premises") as cm:
                cm.new_rel(cm.itm1, R301, cm.itm2)

            with I601.scope("assertions") as cm:
                cm.new_rel(cm.itm1, R302, "good")

            res = p.ruleengine.apply_semantic_rule(I601)

            self.assertEqual(len(res.new_statements), 1)
            self.assertEqual(x0.R302, [x1, "good"])

    def test_d14__zebra_puzzle_stage02(self):
        """
        match persons which have four negative statements of the same kind (test statement relations)
        """
        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        with p.uri_context(uri=TEST_BASE_URI):

            res_702 = res = p.ruleengine.apply_semantic_rule(
                zr.I702["rule: add reverse statement for symmetrical relations"], mod_context_uri=zb.__URI__
            )

            zb.I9848["Norwegian"].set_relation(zb.R1055["has not house color"], zb.I5209["red"])
            zb.I9848["Norwegian"].set_relation(zb.R1055["has not house color"], zb.I1497["blue"])
            zb.I9848["Norwegian"].set_relation(zb.R1055["has not house color"], zb.I8065["green"])
            zb.I9848["Norwegian"].set_relation(zb.R1055["has not house color"], zb.I7612["ivory"])

            res_I800 = res = p.ruleengine.apply_semantic_rule(
                zp.zr.I800["rule: mark relations which are opposite of functional activities"],
                mod_context_uri=TEST_BASE_URI
            )

            self.assertGreaterEqual(len(res.new_statements), 5)

            # res_810 = res = p.ruleengine.apply_semantic_rules(
            #     zr.I810["rule: deduce positive fact from 4 negative facts"], mod_context_uri=zb.__URI__
            # )

            araw = p.ruleengine.AlgorithmicRuleApplicationWorker()
            res = araw.hardcoded_I810(zb, zr.add_stm_by_exclusion)

        self.assertEqual(len(res.new_statements), 1)
        self.assertEqual(zb.I9848["Norwegian"].zb__R8098__has_house_color, zb.I4118["yellow"])

    def test_d15__zebra_puzzle_stage02(self):

        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        # this will change soon
        self.assertNotIn(zb.I5209["red"], zp.person3.zb__R1055__has_not_house_color)

        res = p.ruleengine.apply_semantic_rules(
            zr.I803, mod_context_uri=zb.__URI__
        )
        self.assertEqual(len(res.new_statements), 88)
        self.assertIn(zb.I5209["red"], zp.person3.zb__R1055__has_not_house_color)

    def test_d16__zebra_puzzle_stage02(self):

        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        araw = p.ruleengine.AlgorithmicRuleApplicationWorker()
        func_act_list = p.ds.get_subjects_for_relation(zb.R2850["is functional activity"].uri, filter=True)
        pred_report = araw.get_predicates_report(predicate_list=func_act_list)

        # number of possibilities for each predicate
        self.assertEqual(pred_report.counters, [120]*5)
        # number of total possibilities
        self.assertEqual(pred_report.total_prod, 24883200000)
        self.assertTrue(p.check_type(pred_report.stable_candidates, Dict[str, List[Tuple[int, str]]]))

    def test_d17__zebra_puzzle_stage02(self):

        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        # get all non-placeholder etc humans
        h_list = p.get_instances_of(zb.I7435["human"], filter=p.is_relevant_item)
        # get all placeholder humans

        ph_list = p.get_instances_of(zb.I7435["human"], filter=lambda itm: itm.R57__is_placeholder)

        self.assertEqual(len(h_list), 5)

        with p.uri_context(uri=TEST_BASE_URI):

            zp.person1.set_mutliple_relations(p.R50["is different from"], ph_list)

            # this does nothing because we only have 'meaningless' R50-statements
            res = p.ruleengine.apply_semantic_rules(
                zr.I830["rule: ensure absence of contradictions (5 different-from statements) (hardcoded cheat)"]
            )
            self.assertEqual(len(res.new_statements), 0)

            zp.person1.set_mutliple_relations(p.R50["is different from"], h_list)

            with self.assertRaises(p.aux.LogicalContradiction) as err:
                res = p.ruleengine.apply_semantic_rules(
                    zr.I830["rule: ensure absence of contradictions (5 different-from statements) (hardcoded cheat)"]
                )
                if res.exception:
                    raise res.exception

            msg = '<Item Ia1158["person1"]> has too many `R50__is_differnt_from` statements'
            self.assertEqual(err.exception.args[0], msg)

    @unittest.skip("currently too slow")
    def test_d18__zebra_puzzle_stage02(self):
        """
        Test HTML report
        """
        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        fpath = pjoin(TEST_DATA_DIR1, "test_zebra_triples2.nt")
        with p.uri_context(uri=TEST_BASE_URI):
            c = p.io.import_stms_from_rdf_triples(fpath)  #noqa

            # these two entities had been replaced by rule I720["rule: replace (some) same_as-items"]
            p.core._unlink_entity(zp.person9.uri, remove_from_mod=True)
            p.core._unlink_entity(zp.person2.uri, remove_from_mod=True)

        res = p.ruleengine.apply_semantic_rules(
            zr.I800["rule: mark relations which are opposite of functional activities"],
            zr.I810["rule: deduce positive fact from 4 negative facts (hardcoded cheat)"],
            zr.I710["rule: identify same items via zb__R2850__is_functional_activity"],
            mod_context_uri=TEST_BASE_URI
        )

        fpath = "tmp_report.html"
        res.save_html_report(fpath)

        self.assertTrue(os.path.exists(fpath))

        # IPS()
        if os.environ.get("KEEP_TEST_FILES"):
            print(fpath, "written")
        else:
            os.unlink(fpath)

    @unittest.skip("currently too slow")
    def test_e01__zebra_puzzle_stage02(self):
        """
        apply zebra puzzle rules to zebra puzzle data and assess correctness of the result
        """

        reports = []
        result_history = []

        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)

        # before loading the hint, we can already infer some new statements
        res = p.ruleengine.apply_semantic_rules(
            zr.I702["rule: add reverse statement for symmetrical relations"], mod_context_uri=zb.__URI__
        )

        reports.append(zb.report(display=False, title="I702"))
        result_history.append(res)

        self.assertEqual(len(res.rel_map), 2)
        self.assertIn(p.R43["is opposite of"].uri, res.rel_map)
        self.assertIn(p.R68["is inverse of"].uri, res.rel_map)

        # load the hints and perform basic inferrence
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")
        res_I702 = res = p.ruleengine.apply_semantic_rules(
            zp.zr.I701["rule: imply parent relation of a subrelation"],
            zp.zr.I702["rule: add reverse statement for symmetrical relations"],
            mod_context_uri=TEST_BASE_URI,
        )
        result_history.append(res)

        # only inferrence until now: 5 R3606["lives next to"]-statements
        self.assertEqual(len(res.new_statements), 5)
        self.assertEqual(len(res.rel_map), 1)
        self.assertIn(zp.zb.R3606["lives next to"].uri, res.rel_map)

        res_I705 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I705["rule: deduce trivial different-from-facts"],
            mod_context_uri=TEST_BASE_URI,
        )
        reports.append(zb.report(display=False, title="I705"))
        result_history.append(res)
        self.assertEqual(len(res.new_statements), 20)

        res_I720 = res = p.ruleengine.apply_semantic_rules(
            zp.zr.I710["rule: identify same items via zb__R2850__is_functional_activity"],
            zp.zr.I720["rule: replace (some) same_as-items"],
            mod_context_uri=TEST_BASE_URI,
        )
        self.assertEqual(len(res.new_statements), 11)
        self.assertEqual(len(res.unlinked_entities), 2)

        reports.append(zb.report(display=False, title="I720"))
        result_history.append(res)

        res_I725 = res = p.ruleengine.apply_semantic_rules(
            zp.zr.I725["rule: deduce facts from inverse relations"],
            mod_context_uri=TEST_BASE_URI,
        )

        reports.append(zb.report(display=False, title="I725"))
        result_history.append(res)

        self.assertEqual(len(res.new_statements), 5)
        self.assertEqual(len(res.rel_map), 2)
        self.assertIn(zb.R8768["lives immediately left of"].uri, res.rel_map)
        self.assertIn(zb.R2693["is located immediately right of"].uri, res.rel_map)

        res_I730 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I730["rule: deduce negative facts for neighbours"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I730"))
        result_history.append(res)

        self.assertEqual(len(res.new_statements), 10)

        # check one particular example
        self.assertEqual(zb.I9848["Norwegian"].zb__R1055__has_not_house_color, [zb.I1497["blue"]])

        res_I740 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I740["rule: deduce more negative facts from negative facts"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I740"))
        result_history.append(res)

        self.assertEqual(len(res.new_statements), 0)

        # this will change soon
        self.assertEqual(zb.I4037["Englishman"].zb__R9040__lives_in_numbered_house, None)

        # apply next rule:
        res_I750 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I750["rule: every human lives in one house"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I750"))
        result_history.append(res)

        new_houses_nbr = len(res.new_entities)
        self.assertEqual(new_houses_nbr, 13)
        self.assertEqual(len(res.new_statements), new_houses_nbr * 2)  # including placeholder-statements

        # revist the  example from above
        self.assertNotEqual(zb.I4037["Englishman"].zb__R9040__lives_in_numbered_house, None)

        # apply next rule:
        res_I760 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I760["rule: deduce impossible house indices of neighbour"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I760"))
        result_history.append(res)

        self.assertEqual(len(res.new_statements), 1)
        self.assertEqual(len(res.new_entities), 1)
        self.assertEqual(res.new_entities[0].R38__has_length, 4)

        # apply next rule:
        res_I763 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I763["rule: deduce impossible house index for left-right neighbours"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I763"))
        result_history.append(res)

        # [S6612(<Item Ia1158["person1"]>, <Relation R2835["lives not in numbered house"]>, <Item I6448["house 1"]>),
        #  S6440(<Item Ia1219["person3"]>, <Relation R2835["lives not in numbered house"]>, <Item I1383["house 5"]>)]
        self.assertEqual(len(res.new_statements), 2)

        # apply next rule:
        res_I770 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I770["rule: deduce impossible house_number items from impossible indices"],
            mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I770"))
        result_history.append(res)

        #  [S6265(<Item Ia7903["house number of person12"]>, <Rel. R52["is none of"]>, <Item Ia5222["4-tuple: ..>)]
        self.assertEqual(len(res.new_statements), 1)

        # apply next rule:
        res_I780 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I780["rule: infere from 'is none of' -> 'is one of'"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I780"))
        result_history.append(res)

        # [S2144(<Item Ia7903["house number of person12"]>, <Relation R56["is one of"]>, <Item Ia8692["1-tuple: ...]>)]
        self.assertEqual(len(res.new_statements), 1)

        # apply next rule:
        res_I790 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I790["rule: infere from 'is one of' -> 'is same as'"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I790"))
        result_history.append(res)

        # [S8944(<Item Ia7903["house number of person12"]>, <Relation R47["is same as"]>, <Item I7582["house 2"]>)]
        self.assertEqual(len(res.new_statements), 1)

        # apply next rule:
        h12 = zp.person12.zb__R9040__lives_in_numbered_house
        res_I720b = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I720["rule: replace (some) same_as-items"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I720b"))
        result_history.append(res)

        self.assertEqual(res.replacements, [(h12, zp.zb.I7582["house 2"])])
        self.assertEqual(zp.person12.zb__R9040__lives_in_numbered_house, zp.zb.I7582["house 2"])

        res_I741 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I741["rule: deduce more negative facts from negative facts"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I741"))
        result_history.append(res)

        res_I792 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I792["rule: deduce different-from-facts from negative facts"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I792"))
        result_history.append(res)
        self.assertGreaterEqual(len(res.new_statements), 65)

        res_I794 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I794["rule: deduce neighbour-facts from house indices"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I794"))
        result_history.append(res)
        self.assertGreaterEqual(len(res.new_statements), 2)

        res_I796 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I796["rule: deduce different-from facts for neighbour-pairs"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I796"))
        result_history.append(res)
        self.assertGreaterEqual(len(res.new_statements), 2)

        res_I798 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I798["rule: deduce negative facts from different-from-facts"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I798"))
        result_history.append(res)

        if 0:
            # save the current knowledge state
            fpath = pjoin(TEST_DATA_DIR1, "test_zebra_triples2.nt")
            p.io.export_rdf_triples(fpath, add_qualifiers=True,  modfilter=TEST_BASE_URI)

        res_I800 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I800["rule: mark relations which are opposite of functional activities"],
            mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I800"))
        result_history.append(res)

        apply_times = [(round(r.apply_time, 3), r.rule) for r in result_history]
        apply_times.sort(key=lambda t: t[0], reverse=True)

    @unittest.skip("currently too slow")
    def test_e02__zebra_puzzle_stage02(self):

        reports = []
        result_history = []

        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        fpath = pjoin(TEST_DATA_DIR1, "test_zebra_triples2.nt")
        with p.uri_context(uri=TEST_BASE_URI):
            c = p.io.import_stms_from_rdf_triples(fpath)  #noqa

            # these two entities had been replaced by rule I720["rule: replace (some) same_as-items"]
            p.core._unlink_entity(zp.person9.uri, remove_from_mod=True)
            p.core._unlink_entity(zp.person2.uri, remove_from_mod=True)

        res_I800 = res = p.ruleengine.apply_semantic_rule(
            zp.zr.I800["rule: mark relations which are opposite of functional activities"],
            mod_context_uri=TEST_BASE_URI
        )

        reports.append(zb.report(display=False, title="I800"))
        result_history.append(res)
        self.assertGreaterEqual(len(res.new_statements), 5)

        araw = p.ruleengine.AlgorithmicRuleApplicationWorker()
        with p.uri_context(uri=TEST_BASE_URI):
            # because with traditional rules it seems to be difficult to efficiently deduce positive fact from
            # 4 negative facts, this is an algorithmic approach
            res = araw.hardcoded_I810(zb, zr.add_stm_by_exclusion)

        reports.append(zb.report(display=False, title="I810_experiment"))
        result_history.append(res)

        self.assertEqual(len(res.new_statements), 1)
        self.assertEqual(zb.I9848["Norwegian"].zb__R8098__has_house_color, zb.I4118["yellow"])

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I710["rule: identify same items via zb__R2850__is_functional_activity"],
            mod_context_uri=TEST_BASE_URI
        )

        reports.append(zb.report(display=False, title="I710_(2)"))
        result_history.append(res)
        self.assertEqual(len(res.new_statements), 2)
        self.assertEqual(zb.I9848["Norwegian"].R47__is_same_as, [zp.person5])

        # next (old) rule
        self.assertEqual(len(zb.I9848["Norwegian"].zb__R9803__drinks_not), 3)
        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I720["rule: replace (some) same_as-items"],
            mod_context_uri=TEST_BASE_URI
        )

        reports.append(zb.report(display=False, title="I720_(2)"))
        result_history.append(res)
        self.assertEqual(res.unlinked_entities, [zp.person5])
        self.assertGreaterEqual(len(res.new_statements), 10)
        self.assertEqual(len(zb.I9848["Norwegian"].zb__R9803__drinks_not), 4)

        with p.uri_context(uri=TEST_BASE_URI):
            # because with traditional rules it seems to be difficult to efficiently deduce positive fact from
            # 4 negative facts, this is an algorithmic approach
            res = araw.hardcoded_I810(zb, zr.add_stm_by_exclusion)

        reports.append(zb.report(display=False, title="I810_experiment_(2)"))
        result_history.append(res)

        self.assertEqual(len(res.new_statements), 1)
        self.assertEqual(zb.I9848["Norwegian"].zb__R8216__drinks, zb.I7509["water"])

        res = p.ruleengine.apply_semantic_rule(
            zr.I702["rule: add reverse statement for symmetrical relations"], mod_context_uri=zb.__URI__
        )

        reports.append(zb.report(display=False, title="I702_(2)"))
        result_history.append(res)

        # this contains one statement about unlinked person5 TODO: fixme
        self.assertEqual(len(res.new_statements), 9)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I798["rule: deduce negative facts from different-from-facts"], mod_context_uri=TEST_BASE_URI
        )
        self.assertEqual(len(res.new_statements), 22)

        reports.append(zb.report(display=False, title="I798_(2)"))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I760["rule: deduce impossible house indices of neighbour"], mod_context_uri=TEST_BASE_URI
        )

        # contains 2 trivial facts of non-placeholder houses, but on good fact

        reports.append(zb.report(display=False, title="I760_(2)"))
        result_history.append(res)


        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I770["rule: deduce impossible house_number items from impossible indices"],
            mod_context_uri=TEST_BASE_URI
        )

        # contains 3 trivial facts of non-placeholder houses, but on good fact
        reports.append(zb.report(display=False, title="I770_(2)"))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I780["rule: infere from 'is none of' -> 'is one of'"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I780_(2)"))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I790["rule: infere from 'is one of' -> 'is same as'"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title="I790_(2)"))
        result_history.append(res)
        self.assertEqual(len(res.new_statements), 1)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I720["rule: replace (some) same_as-items"], mod_context_uri=TEST_BASE_URI
        )
        self.assertEqual(zp.person10.zb__R9040__lives_in_numbered_house, zb.I7582["house 2"])
        reports.append(zb.report(display=False, title="I720_(3"))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I710["rule: identify same items via zb__R2850__is_functional_activity"],
            mod_context_uri=TEST_BASE_URI
        )

        reports.append(zb.report(display=False, title="I710_(3)"))
        result_history.append(res)
        self.assertEqual(len(res.new_statements), 2)

        res = p.ruleengine.apply_semantic_rule(
            zp.zr.I720["rule: replace (some) same_as-items"], mod_context_uri=TEST_BASE_URI
        )
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)
        self.assertEqual(len(res.new_statements), 21)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I701, mod_context_uri=TEST_BASE_URI)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I702, mod_context_uri=TEST_BASE_URI)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I730, mod_context_uri=TEST_BASE_URI)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I725, mod_context_uri=TEST_BASE_URI)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I741, mod_context_uri=TEST_BASE_URI)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        #
        res = p.ruleengine.apply_semantic_rule(zr.I803, mod_context_uri=zb.__URI__)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I792, mod_context_uri=TEST_BASE_URI)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I798, mod_context_uri=TEST_BASE_URI)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        self.assertEqual(len(res.new_statements), 8)

        res = p.ruleengine.apply_semantic_rule(zp.zr.I820, mod_context_uri=TEST_BASE_URI)
        reports.append(zb.report(display=False, title=res.rule.short_key))
        result_history.append(res)

        araw = p.ruleengine.AlgorithmicRuleApplicationWorker()
        func_act_list = p.ds.get_subjects_for_relation(zb.R2850["is functional activity"].uri, filter=True)
        pred_report = araw.get_predicates_report(predicate_list=func_act_list)

        with p.uri_context(uri=TEST_BASE_URI):
            res = araw.hardcoded_I810(zb, zr.add_stm_by_exclusion)

        # for performance reasons we continue with a test_e03

    @unittest.skip("currently too slow")
    def test_e03__zebra_puzzle_stage02(self):

        zb = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_BASE_DATA, prefix="zb")
        zr = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA_RULES, prefix="zr", reuse_loaded=True)
        zp = p.erkloader.load_mod_from_path(TEST_DATA_PATH_ZEBRA02, prefix="zp")

        args = (zp.person8, zb.R2835["lives not in numbered house"], zb.I7582["house 2"], zb.I4735["house 3"],
         zb.I4785["house 4"], zb.I1383["house 5"])




        fpath = pjoin(TEST_DATA_DIR1, "test_zebra_triples3.nt")
        with p.uri_context(uri=TEST_BASE_URI):
            c = p.io.import_stms_from_rdf_triples(fpath)  #noqa

            # these entities had been replaced by rule I720["rule: replace (some) same_as-items"]
            p.core._unlink_entity(zp.person9.uri, remove_from_mod=True)
            p.core._unlink_entity(zp.person2.uri, remove_from_mod=True)
            p.core._unlink_entity(zp.person5.uri, remove_from_mod=True)
            p.core._unlink_entity(zp.person12.uri, remove_from_mod=True)

            # not sure were this comes from but it has to go (disconnected artifact)
            p.core._unlink_entity("erk:/local/unittest#Ia9473", remove_from_mod=True)


        all_relevant_rules = [
            # zr.I701["rule: imply parent relation of a subrelation"],
            zr.I702["rule: add reverse statement for symmetrical relations"],
            zr.I705["rule: deduce trivial different-from-facts"],
            zr.I710["rule: identify same items via zb__R2850__is_functional_activity"],
            zr.I720["rule: replace (some) same_as-items"],
            zr.I725["rule: deduce facts from inverse relations"],
            zr.I730["rule: deduce negative facts for neighbours"],
            zr.I740["rule: deduce more negative facts from negative facts"],
            zr.I741["rule: deduce more negative facts from negative facts"],
            zr.I750["rule: every human lives in one house"],
            zr.I760["rule: deduce impossible house indices of neighbour"],
            zr.I763["rule: deduce impossible house index for left-right neighbours"],
            zr.I770["rule: deduce impossible house_number items from impossible indices"],
            # zr.I780["rule: infere from 'is none of' -> 'is one of'"],  # not useful for iterating
            zr.I790["rule: infere from 'is one of' -> 'is same as'"],
            #  zr.I792["rule: deduce different-from-facts from negative facts"],  # slow
            zr.I794["rule: deduce neighbour-facts from house indices"],
            zr.I796["rule: deduce different-from facts for neighbour-pairs"],
            zr.I798["rule: deduce negative facts from different-from-facts"],
            zr.I800["rule: mark relations which are opposite of functional activities"],
            zr.I810["rule: deduce positive fact from 4 negative facts (hardcoded cheat)"],
            zr.I820["rule: deduce personhood by exclusion"],
            zr.I825["rule: deduce lives-not-in... from lives-next-to"],
            zr.I830["rule: ensure absence of contradictions (5 different-from statements) (hardcoded cheat)"],
            zr.I840["rule: detect if puzzle is solved (hardcoded cheat)"],
        ]

        araw = p.ruleengine.AlgorithmicRuleApplicationWorker()
        p.ruleengine.VERBOSITY = True

        res = p.ruleengine.apply_semantic_rule(zr.I810, mod_context_uri=TEST_BASE_URI)

        with p.uri_context(uri=TEST_BASE_URI):
            IPS()
            return
            # res = p.ruleengine.apply_semantic_rules(*all_relevant_rules[1:])
            func_act_list = p.ds.get_subjects_for_relation(zb.R2850["is functional activity"].uri, filter=True)
            pred_report = araw.get_predicates_report(predicate_list=func_act_list)

        hyre = p.ruleengine.HypothesisReasoner(zb, base_uri=TEST_BASE_URI)
        res = hyre.hypothesis_reasoning_step(all_relevant_rules)


        # manually unload internal module:
        p.unload_mod(hyre.contex_uri, strict=False)


        # IPS() # WIP


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

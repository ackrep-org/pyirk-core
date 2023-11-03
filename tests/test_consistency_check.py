import unittest
import sys
import os
from os.path import join as pjoin
from typing import Dict, List, Union

import rdflib

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception, set_trace  # noqa
import pyerk as p


from .settings import (
    TEST_BASE_URI,
    HouskeeperMixin,
    TEST_DATA_PATH2,

    )


# noinspection PyPep8Naming
class Test_01_CC(HouskeeperMixin, unittest.TestCase):


    def create_operators(self):
        with p.uri_context(uri=TEST_BASE_URI):

            I4895 = p.create_item(
                R1__has_label="mathematical operator",
                R2__has_description="general (unspecified) mathematical operator",
                R3__is_subclass_of=p.I12["mathematical object"],
            )

            # make all instances of operators callable:
            I4895["mathematical operator"].add_method(p.create_evaluated_mapping, "_custom_call")

            I0111 = p.create_item(
                R1__has_label="test operator",
                R2__has_description="...",
                R4__is_instance_of=I4895["mathematical operator"],
                R8__has_domain_of_argument_1=p.I37["integer number"],
                R9__has_domain_of_argument_2=p.I38["non-negative integer"],
                R10__has_domain_of_argument_3=p.I39["positive integer"],
                R11__has_range_of_result=p.I34["complex number"],
            )

            return I0111

    def test_a01__cc_basics(self):

        I0111 = self.create_operators()

        with p.uri_context(uri=TEST_BASE_URI):
            real_number = p.instance_of(p.I35["real number"])
            general_int = p.instance_of(p.I37["integer number"])
            nonneg_int = p.instance_of(p.I38["non-negative integer"])
            positive_int = p.instance_of(p.I39["positive integer"])

            # these should work
            p.cc.check(I0111["test operator"](general_int, nonneg_int, positive_int))

            # now pass an instance of a subclass for arg1
            p.cc.check(I0111["test operator"](nonneg_int, nonneg_int, positive_int))

            # these should raise an error
            with self.assertRaises(p.cc.WrongArgNumber):
                p.cc.check(I0111["test operator"](general_int))
            with self.assertRaises(p.cc.WrongArgNumber):
                p.cc.check(I0111["test operator"](general_int, ))

            with self.assertRaises(p.cc.WrongArgType):
                # type error for arg2
                p.cc.check(I0111["test operator"](general_int, general_int, positive_int))

            with self.assertRaises(p.cc.WrongArgType):
                # type error for arg1 and arg3
                p.cc.check(I0111["test operator"](real_number, nonneg_int, real_number))

    def test_a02__cc_enable_checking(self):

        I0111 = self.create_operators()
        p.cc.enable_consitency_checking()

        with p.uri_context(uri=TEST_BASE_URI):
            real_number = p.instance_of(p.I35["real number"])
            with self.assertRaises(p.cc.WrongArgType):
                # type error for all args
                I0111["test operator"](real_number, real_number, real_number)

    def _define_tst_rule(self, ct) -> p.Item:
        with p.uri_context(uri=TEST_BASE_URI):
            I501 = p.create_item(
                R1__has_label="match matmul all",
                R2__has_description=("test to match every instance of ma__I5177__matmul"),
                R4__is_instance_of=p.I47["constraint rule"],
            )

            with I501.scope("setting") as cm:
                cm.new_var(x=p.instance_of(p.I1["general item"]))
                cm.new_var(arg_tuple=p.instance_of(p.I33["tuple"]))
                cm.new_var(arg1=p.instance_of(p.I1["general item"]))
                cm.new_var(arg2=p.instance_of(p.I1["general item"]))

                cm.new_var(arg1_ra=p.instance_of(p.I49["reification anchor"]))
                cm.new_var(arg2_ra=p.instance_of(p.I49["reification anchor"]))

                cm.uses_external_entities(I501)
                cm.uses_external_entities(ct.ma.I5177["matmul"])

            with I501.scope("premise") as cm:
                cm.new_rel(cm.x, p.R35["is applied mapping of"], ct.ma.I5177["matmul"])
                cm.new_rel(cm.x, p.R36["has argument tuple"], cm.arg_tuple)

                cm.new_rel(cm.arg_tuple, p.R39["has element"], cm.arg1)
                cm.new_rel(cm.arg_tuple, p.R39["has element"], cm.arg2)

                # specify the argument order
                cm.new_rel(cm.arg_tuple, p.R75["has reification anchor"], cm.arg1_ra)
                cm.new_rel(cm.arg_tuple, p.R75["has reification anchor"], cm.arg2_ra)

                cm.new_rel(cm.arg1_ra, p.R39["has element"], cm.arg1)
                cm.new_rel(cm.arg2_ra, p.R39["has element"], cm.arg2)

                cm.new_rel(cm.arg1_ra, p.R40["has index"], 0)
                cm.new_rel(cm.arg2_ra, p.R40["has index"], 1)

            with I501.scope("assertion") as cm:
                cm.new_rel(cm.x, p.R54["is matched by rule"], I501)
                cm.new_rel(cm.arg_tuple, p.R54["is matched by rule"], I501)
                cm.new_rel(cm.arg1, p.R54["is matched by rule"], I501)
                cm.new_rel(cm.arg2, p.R54["is matched by rule"], I501)

            # this rule deals with operand dimensions
            I502 = p.create_item(
                R1__has_label="match matmul all",
                R2__has_description=("test to match every instance of ma__I5177__matmul"),
                R4__is_instance_of=p.I47["constraint rule"],
            )

            with I502.scope("setting") as cm:
                cm.copy_from(I501, "setting")

                # m1 = p.instance_of(p.I39["positive integer"])
                # n2 = p.instance_of(p.I39["positive integer"])

            with I502.scope("premise") as cm:
                cm.copy_from(I501, "premise")

        return I501["match matmul all"]

    # this tests now fails because the rule got more specific -> is test obsolete or should there be a separate rule?
    @unittest.expectedFailure
    def test_b01__cc_constraint_violation_rules(self):

        ct = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        I501 = self._define_tst_rule(ct)
        with p.uri_context(uri=TEST_BASE_URI):

            A = p.instance_of(ct.ma.I9904["matrix"])
            AxA = ct.ma.I5177["matmul"](A, A)

            self.assertEqual(AxA.R54__is_matched_by_rule, [])

            res = p.ruleengine.apply_semantic_rule(I501)

        self.assertGreaterEqual(len(res.new_statements), 1)
        self.assertEqual(AxA.R54__is_matched_by_rule, [I501])

    def test_c01__cc_matrix_dimensions(self):

        ct = p.erkloader.load_mod_from_path(TEST_DATA_PATH2, prefix="ct")
        I501 = self._define_tst_rule(ct)
        with p.uri_context(uri=TEST_BASE_URI):
            n1 = p.instance_of(p.I39["positive integer"])
            m1 = p.instance_of(p.I39["positive integer"])

            n2 = p.instance_of(p.I39["positive integer"])
            m2 = p.instance_of(p.I39["positive integer"])

            A1 = p.instance_of(ct.ma.I9904["matrix"])
            A2 = p.instance_of(ct.ma.I9904["matrix"])
            B = p.instance_of(ct.ma.I9904["matrix"])

            A1.ma__R5939__has_column_number = m1
            A2.ma__R5939__has_column_number = n2
            B.ma__R5938__has_row_number = n2

            A1B = ct.ma.I5177["matmul"](A1, B)
            A2B = ct.ma.I5177["matmul"](A2, B)

            res = p.ruleengine.apply_semantic_rule(I501)

        self.assertGreaterEqual(len(res.new_statements), 2)

        self.assertEqual(A1B.R36__has_argument_tuple.R54__is_matched_by_rule, [I501])
        self.assertEqual(A2B.R36__has_argument_tuple.R54__is_matched_by_rule, [I501])
        self.assertEqual(A1.R54__is_matched_by_rule, [I501])
        self.assertEqual(A2.R54__is_matched_by_rule, [I501])

        # B is matched twice because it is used in two matrix-products
        self.assertEqual(B.R54__is_matched_by_rule, [I501, I501])

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


    )


# noinspection PyPep8Naming
class Test_01_CC(HouskeeperMixin, unittest.TestCase):
    def test_a01__cc_basics(self):

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

            real_number = p.instance_of(p.I35["real number"])
            general_int = p.instance_of(p.I37["integer number"])
            nonneg_int = p.instance_of(p.I38["non-negative integer"])
            positive_int = p.instance_of(p.I39["positive integer"])

            if 0:
                # these should work
                p.cc.check(I0111["test operator"](general_int, nonneg_int, positive_int))

                # now pass an instance of a subclass for arg1
                p.cc.check(I0111["test operator"](nonneg_int, nonneg_int, positive_int))

                # these should raise an error
                with self.assertRaises(p.cc.WrongArgNumber):
                    p.cc.check(I0111["test operator"](general_int))
                with self.assertRaises(p.cc.WrongArgNumber):
                    p.cc.check(I0111["test operator"](general_int, ))

            # now pass an instance of a subclass for arg1
            p.cc.check(I0111["test operator"](nonneg_int, nonneg_int, positive_int))

            with self.assertRaises(p.cc.WrongArgType):
                # type error for arg2
                p.cc.check(I0111["test operator"](general_int, general_int, positive_int))

            with self.assertRaises(p.cc.WrongArgType):
                # type error for arg1 and arg3
                p.cc.check(I0111["test operator"](real_number, nonneg_int, real_number))

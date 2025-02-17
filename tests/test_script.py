import unittest
import os
import shutil
from os.path import join as pjoin
from typing import Dict, List, Union

import rdflib

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception, set_trace  # noqa
import pyirk as p


from .settings import (
    TEST_BASE_URI,
    TEST_DATA_DIR1,
    HousekeeperMixin,
    TEST_DATA_DIR_OCSE,
)


# noinspection PyPep8Naming
class Test_01_Script(HousekeeperMixin, unittest.TestCase):
    def test_a01__insert_keys(self):

        srcpath = pjoin(TEST_DATA_DIR1, "tmod2_with_new_items.py")

        # make a working copy (this file will be changed)
        modpath = srcpath.replace(".py", "_workcopy.py")
        self.files_to_delete.append(modpath)
        shutil.copy(srcpath, modpath)

        N = len(os.listdir(TEST_DATA_DIR1))

        cmd = f"pyirk --insert-keys-for-placeholders {modpath}"
        os.system(cmd)

        # ensure that temporary file is deleted correctly
        self.assertEqual(N, len(os.listdir(TEST_DATA_DIR1)))

        with open(modpath) as fp:
            txt = fp.read()

        self.assertNotIn("\n_newitemkey_", txt)
        self.assertNotIn("I000", txt)

        # ensure that the module is loadable
        mod = p.irkloader.load_mod_from_path(modpath, prefix="tm1", delete_bytecode=True)

        # test I000["key insertion by label"]
        (itm3,) = mod.I1000.R72__is_generally_related_to
        itm2 = itm3.R4__is_instance_of
        itm1 = itm2.R3__is_subclass_of

        self.assertEqual(itm1.R1__has_label.value, "some new item")

    @unittest.skipIf(os.environ.get("CI"), "Skipping visualization test on CI to prevent graphviz-dependency")
    def test_c01__visualization(self):
        cmd = "pyirk -vis I12"
        res = os.system(cmd)
        self.assertEqual(res, 0)

    @unittest.skipIf(os.environ.get("CI"), "Skipping visualization test on CI to prevent graphviz-dependency")
    def test_c02__visualization_commands(self):
        os.chdir(TEST_DATA_DIR_OCSE)

        self.files_to_delete.append("tmp_dot.txt")
        self.files_to_delete.append("tmp.svg")
        cmd = "pyirk --load-mod control_theory1.py demo -vis __all__"
        res = os.system(cmd)
        self.assertEqual(res, 0)

        cmd = "pyirk --load-mod control_theory1.py demo -vis ma__I9904"
        res = os.system(cmd)
        self.assertEqual(res, 0)

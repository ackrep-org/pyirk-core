import unittest
import os
import shutil
from os.path import join as pjoin
from typing import Dict, List, Union

import rdflib

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception, set_trace  # noqa
import pyerk as p


from .settings import (
    TEST_BASE_URI,
    TEST_DATA_DIR1,
    HouskeeperMixin,
    TEST_DATA_PATH2,

    )


# noinspection PyPep8Naming
class Test_01_Script(HouskeeperMixin, unittest.TestCase):
    def test_a01__insert_keys(self):

        srcpath = pjoin(TEST_DATA_DIR1, "tmod2_with_new_items.py")

        # make a working copy (this file will be changed)
        modpath = srcpath.replace(".py", "_workcopy.py")
        # self.files_to_delete.append(modpath)
        shutil.copy(srcpath, modpath)

        N = len(os.listdir(TEST_DATA_DIR1))

        cmd = f"pyerk --insert-keys-for-placeholders {modpath}"
        os.system(cmd)

        # ensure that temporary file is deleted correctly
        self.assertEqual(N, len(os.listdir(TEST_DATA_DIR1)))

        with open(modpath) as fp:
            txt = fp.read()

        self.assertNotIn("\n_newitemkey_", txt)
        self.assertNotIn("I000", txt)

        # ensure that the module is loadable
        mod = p.erkloader.load_mod_from_path(modpath, prefix="tm1")

    @unittest.skipIf(os.environ.get("CI"), "Skipping visualization test on CI to prevent graphviz-dependency")
    def test_c01__visualization(self):
        cmd = "pyerk -vis I12"
        res = os.system(cmd)
        self.assertEqual(res, 0)

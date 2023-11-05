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
    @unittest.skipIf(os.environ.get("CI"), "Skipping visualization test on CI to prevent graphviz-dependency")
    def test_c01__visualization(self):
        cmd = "pyerk -vis I12"
        res = os.system(cmd)
        self.assertEqual(res, 0)

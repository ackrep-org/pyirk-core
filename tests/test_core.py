import unittest
import sys
import os
from os.path import join as pjoin
# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception
import pykerl as pk

activate_ips_on_exception()

current_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
TEST_DATA_PATH = pjoin(current_dir, "test_data")


# noinspection PyPep8Naming
class TestCore(unittest.TestCase):
    def setUp(self):
        pass

    # mark tests which only work for the "old core"
    def test_core1(self):
        m = pk.Manager(pjoin(TEST_DATA_PATH, "test1.yml"))

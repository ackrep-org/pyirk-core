import sys
import os
from os.path import join as pjoin
import random


# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception, set_trace  # noqa
import pyirk as p
import pyirk.io


# ensure reproducible results
# (the result order of graph algorithms imported in ruleengine seems to depend on random numbers)
random.seed(1714)

activate_ips_on_exception()

current_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))

IRK_ROOT_DIR = p.aux.get_irk_root_dir()

# path for basic (staged) test data
TEST_DATA_DIR1 = pjoin(IRK_ROOT_DIR, "pyirk-core", "tests", "test_data")
TEST_DATA_DIR_OCSE = pjoin(TEST_DATA_DIR1, "ocse_subset")


TEST_DATA_PATH2 = pjoin(TEST_DATA_DIR1, "ocse_subset", "control_theory1.py")
TEST_DATA_PATH_MA = pjoin(TEST_DATA_DIR1, "ocse_subset", "math1.py")
TEST_DATA_PATH3 = pjoin(TEST_DATA_DIR1, "ocse_subset", "agents1.py")
TEST_DATA_PATH_ZEBRA01 = pjoin(TEST_DATA_DIR1, "zebra01.py")
TEST_DATA_PATH_ZEBRA02 = pjoin(TEST_DATA_DIR1, "zebra02.py")
TEST_DATA_PATH_ZEBRA_BASE_DATA = pjoin(TEST_DATA_DIR1, "zebra_base_data.py")
TEST_DATA_PATH_ZEBRA_RULES = pjoin(TEST_DATA_DIR1, "zebra_puzzle_rules.py")
TEST_MOD_NAME = "control_theory1"

# useful to get the currently latest sha strings:
# git log --pretty=oneline | head
TEST_DATA_REPO_COMMIT_SHA = "11b9f9fe14cef7248fd0d9f31c7412516aa92aa9"  # (2023-11-07 16:20:00)

# TODO: make this more robust (e.g. search for config file or environment variable)
# TODO: put link to docs here (directory layout)
TEST_ACKREP_DATA_FOR_UT_PATH = pjoin(IRK_ROOT_DIR, "..", "ackrep", "ackrep_data_for_unittests")

os.environ["UNITTEST"] = "True"

# UNLOAD_MODS is True by default but could be set to False via env var.
# This is sometimes useful to prevent the deletion of entities by tear_down()
UNLOAD_MODS = not (os.getenv("PYIRK_NOT_UNLOAD_MODS") == "True")

__URI__ = TEST_BASE_URI = "irk:/local/unittest"


# this serves to print the test-method-name before it is executed (useful for debugging, see setUP below)
PRINT_TEST_METHODNAMES = True

# some tests might generate files such as `tmp.svg` as a byproduct for debugging. The following flags controls this.
WRITE_TMP_FILES = False


class HousekeeperMixin:
    """
    Class to provide common functions for all our TestCase subclasses
    """

    def setUp(self):
        cls = self.__class__
        method_repr = f"{cls.__module__}:{cls.__qualname__}.{self._testMethodName}"
        os.environ["UNITTEST_METHOD_NAME"] = method_repr
        self.register_this_module()
        p.ds.initialize_hooks()
        self.files_to_delete = []

    def tearDown(self) -> None:
        # possibility to keep the mods loaded on error for easier interactive debugging
        # UNLOAD_MODS is True by default
        if UNLOAD_MODS:
            self.unload_all_mods()
        self.print_methodnames()
        os.environ.pop("UNITTEST_METHOD_NAME", None)
        for path in self.files_to_delete:
            os.unlink(path)

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

            if self.had_error():
                print(method_repr, p.aux.bred("failed"))
            else:
                print(method_repr, p.aux.bgreen("passed"))

    def had_error(self):
        return False

        # TODO fix this for python 3.11 by using
        # https://stackoverflow.com/questions/4414234/getting-pythons-unittest-results-in-a-teardown-method

        error_list = [b for (a, b) in self._outcome.errors if b is not None]
        return bool(error_list)

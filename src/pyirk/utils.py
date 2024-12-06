import os
import pyirk as p

from ipydex import IPS


class GeneralHousekeeperMixin:
    """
    Class to provide common functions for all our TestCase subclasses.

    It is expected that this class is subclassed in the tests (with updated class variables)
    """

    # these class variables might be overwritten by unittests
    UNLOAD_MODS = True
    TEST_BASE_URI = "irk:/local/unittest"
    PRINT_TEST_METHODNAMES = True

    def setUp(self):
        # use this import here to prevent circular imports
        cls = self.__class__
        method_repr = f"{cls.__module__}:{cls.__qualname__}.{self._testMethodName}"
        os.environ["UNITTEST_METHOD_NAME"] = method_repr
        self.register_this_module()
        p.ds.initialize_hooks()
        self.files_to_delete = []

    def tearDown(self) -> None:
        # possibility to keep the mods loaded on error for easier interactive debugging
        # UNLOAD_MODS is True by default
        if self.UNLOAD_MODS:
            self.unload_all_mods()
        self.print_methodnames()
        os.environ.pop("UNITTEST_METHOD_NAME", None)
        for path in self.files_to_delete:
            os.unlink(path)

    def unload_all_mods(self):
        p.unload_mod(self.TEST_BASE_URI, strict=False)

        # unload all modules which where loaded by a test
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)

    def register_this_module(self):
        keymanager = p.KeyManager()
        p.register_mod(self.TEST_BASE_URI, keymanager, check_uri=False)

    def print_methodnames(self):
        if self.PRINT_TEST_METHODNAMES:
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

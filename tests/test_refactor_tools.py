import unittest

import pyirk.refactor_tools as rt



from .settings import (
    TEST_BASE_URI,
    TEST_DATA_DIR1,
    HousekeeperMixin,
    TEST_DATA_DIR_OCSE,
    TEST_DATA_PATH3 as ocse_subset_agents_path,
)


# noinspection PyPep8Naming
class Test_01_Script(HousekeeperMixin, unittest.TestCase):
    def test_rt_a01__(self):
        rt.change_entity_label("foo", "bar", ocse_subset_agents_path)
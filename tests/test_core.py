import unittest
from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()

# noinspection PyPep8Naming
class TestCore(unittest.TestCase):
    def setUp(self):
        pass

    # mark tests which only work for the "old core"
    def test_core1(self):
        pass

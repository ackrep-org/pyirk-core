# Note: this is not the real module for this URI it is an autogenerated subset for testing
import pyerk as p


# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception  # noqa

ma = p.erkloader.load_mod_from_path("./math1.py", prefix="ma")
ag = ma.ag


__URI__ = "erk:/ocse/0.2/control_theory"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


insert_entities = [
I4239["abstract monovariate polynomial"],
I1347["Lie derivative of scalar field"]
]



p.end_mod()

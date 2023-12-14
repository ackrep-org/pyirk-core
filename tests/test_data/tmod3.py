import pyirk as p
import os

__URI__ = "irk:/pyirk/testmodule3"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


I1000 = p.create_item(
    R1__has_label="test item in tmod3",
)


R2000 = p.create_relation(
    R1__has_label="some relation",
)


if os.getenv("PYIRK_TRIGGER_TEST_EXCEPTION", "False").lower() == "true":
    raise p.aux.ExplicitlyTriggeredTestException("this exception is intended")

p.end_mod()

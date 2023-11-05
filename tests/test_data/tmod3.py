import pyerk as p

__URI__ = "erk:/pyerk/testmodule3"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


I1000 = p.create_item(
    R1__has_label="test item in tmod3",
)


R2000 = p.create_relation(
    R1__has_label="some relation",
)


p.end_mod()

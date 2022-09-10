import pyerk as p

__URI__ = "erk:/pyerk/testmodule1"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


I1000 = p.create_item(
    R1__has_label="test item in tmod1",
)


p.end_mod()

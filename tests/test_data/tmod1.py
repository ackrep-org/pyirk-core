import pyerk as p

__URI__ = "pyerk/testmodule1"
p.register_mod(__URI__)


I1000 = p.create_item(
    R1__has_label="test item in tmod1",
)

import pyerk as p

__URI__ = "erk:/pyerk/testmodule2"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


I1000 = p.create_item(
    R1__has_label="test item in tmod2",
)

# <new_entities>


_newitemkey_ = p.create_item(
    R1__has_label="some new item",
    R2__has_description="",
    R4__is_instance_of=p.I50["stub"]
)

_newitemkey_ = p.create_item(
    R1__has_label="special new item",
    R2__has_description="",
    R3__is_subclass_of=p.I000["some new item"]
)

_newitemkey_ = p.create_item(
    R1__has_label="some other item",
    R2__has_description="",
    R4__is_instance_of=p.I000["special new item"]
)

# this section in the source file is helpful for bulk-insertion of new items

# _newitemkey_ = p.create_item(
#     R1__has_label="",
#     R2__has_description="",
#     R4__is_instance_of=p.I50["stub"]
# )


#</new_entities>

I1000.R72__is_generally_related_to = p.I000["some other item"]


p.end_mod()

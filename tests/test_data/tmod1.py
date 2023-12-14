import pyirk as p


# using "foo" and "bar" here to indicate that these strings are abitrary
foo_mod = p.irkloader.load_mod_from_path("./tmod3.py", prefix="bar")

__URI__ = "irk:/pyirk/testmodule1"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


I1000 = p.create_item(
    R1__has_label="test item in tmod1",

    # demonstrate usage of prefixed name-labled key
    bar__R2000__some_relation=42,
)

# demonstrate usage of index-labled key (explicit object reference)
I1000.set_relation(foo_mod.R2000["some relation"], 23)

# note that both R2000-statements are created in the uri_context of *this* module


p.end_mod()

# Note: this is not the real module for this URI it is an autogenerated subset for testing

from typing import Union
import pyerk as p

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception  # noqa

ag = p.erkloader.load_mod_from_path("./agents1.py", prefix="ag")

__URI__ = "erk:/ocse/0.2/math"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)

I4895 = p.create_item(
    R1__has_label="mathematical operator",
    R2__has_description="general (unspecified) mathematical operator",
    R3__is_subclass_of=p.I12["mathematical object"],
)

I4895["mathematical operator"].add_method(p.create_evaluated_mapping, "_custom_call")


I9923 = p.create_item(
    R1__has_label="scalar field",
    R2__has_description="...",
    R3__is_subclass_of=I4895["mathematical operator"],
)

I9841 = p.create_item(
    R1__has_label="vector field",
    R2__has_description="...",
    R3__is_subclass_of=I4895["mathematical operator"],
)

I4236 = p.create_item(
    R1__has_label="mathematical expression",
    R2__has_description="common base class for mathematical expressions",
    R3__is_subclass_of=p.I12["mathematical object"],
)

I1060 = p.create_item(
    R1__has_label="general function",
    R2__has_description="function that maps from some set (domain) into another (range);",
    R3__is_subclass_of=I4236["mathematical expression"],
    R18__has_usage_hint="this is the base class for more specifc types of functions",
)

I1063 = p.create_item(
    R1__has_label="scalar function",
    R2__has_description="function that has one (in general complex) number as result",
    R3__is_subclass_of=I1060["general function"],
)

I4237 = p.create_item(
    R1__has_label="monovariate rational function",
    R2__has_description="...",
    R3__is_subclass_of=I1063["scalar function"],
)

I4237["monovariate rational function"].add_method(p.create_evaluated_mapping, "_custom_call")


I4239 = p.create_item(
    R1__has_label="abstract monovariate polynomial",
    R2__has_description=(
        "abstract monovariate polynomial (argument might be a complex-valued scalar, a matrix, an operator, etc.)"
    ),
    R3__is_subclass_of=I4237["monovariate rational function"],
)

R3326 = p.create_relation(
    R1__has_label="has dimension",
    R2__has_description="specifies the dimension of a (dimensional) mathematical object",
    R8__has_domain_of_argument_1=p.I12["mathematical object"],
    R11__has_range_of_result=p.I38["non-negative integer"],
    R22__is_functional=True,
)

I5166 = p.create_item(
    R1__has_label="vector space",
    R2__has_description="type for a vector space",
    R3__is_subclass_of=p.I13["mathematical set"],
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/wiki/Q125977",
    R41__has_required_instance_relation=R3326["has dimension"],
)

I5167 = p.create_item(
    R1__has_label="state space",
    R2__has_description="type for a state space of a dynamical system (I6886)",
    R3__is_subclass_of=I5166["vector space"],

    # this should be defined via inheritance from vector space
    # TODO: test that this is the case
    # R41__has_required_instance_relation=R3326["has dimension"],
)

R5405 = p.create_relation(
    R1__has_label="has associated state space",
    R2__has_description="specifies the associated state space of the subject (e.g. a I9273__explicit...ode_system)",
    R8__has_domain_of_argument_1=p.I12["mathematical object"],
    R11__has_range_of_result=I5167["state space"],
    R22__is_functional=True,
)

I1168 = p.create_item(
    R1__has_label="point in state space",
    R2__has_description="type for a point in a given state space",
    R3__is_subclass_of=p.I12["mathematical object"],
    R41__has_required_instance_relation=R5405["has associated state space"],
)

I9904 = p.create_item(
    R1__has_label="matrix",
    R2__has_description="matrix of (in general) complex numbers, i.e. matrix over the field of complex numbers",
    R3__is_subclass_of=p.I12["mathematical object"],
)

R5939 = p.create_relation(
    R1__has_label="has column number",
    R2__has_description="specifies the number of columns of a matrix",
    R8__has_domain_of_argument_1=I9904["matrix"],
    R11__has_range_of_result=p.I38["non-negative integer"],
    R22__is_functional=True,
)

R5938 = p.create_relation(
    R1__has_label="has row number",
    R2__has_description="specifies the number of rows of a matrix",
    R8__has_domain_of_argument_1=I9904["matrix"],
    R11__has_range_of_result=p.I38["non-negative integer"],
    R22__is_functional=True,
)

I5177 = p.create_item(
    R1__has_label="matmul",
    R2__has_description=("matrix multplication operator"),
    R4__is_instance_of=I4895["mathematical operator"],
    R8__has_domain_of_argument_1=I9904["matrix"],
    R9__has_domain_of_argument_2=I9904["matrix"],
    R11__has_range_of_result=I9904["matrix"],
)

I3749 = p.create_item(
    R1__has_label="Cayley-Hamilton theorem",
    R2__has_description="establishes that every square matrix is a root of its own characteristic polynomial",
    R4__is_instance_of=p.I15["implication proposition"],
)

I5000 = p.create_item(
    R1__has_label="scalar zero",
    R2__has_description="entity representing the zero-element in the set of complex numbers and its subsets",
    R4__is_instance_of=p.I34["complex number"],
    R24__has_LaTeX_string="$0$",
)

R3033 = p.create_relation(
    R1__has_label="has type of elements",
    R2__has_description=(
        "specifies the item-type of the elements of a mathematical set; "
        "should be a subclass of I12['mathematical object']"
    ),
    R8__has_domain_of_argument_1=p.I13["mathematical set"],
    R11__has_range_of_result=p.I42["mathematical type (metaclass)"],
)

I8133 = p.create_item(
    R1__has_label="field of numbers",
    R1__has_label__de="Zahlenkörper",
    R2__has_description="general field of numbers; baseclass for the fields of real and complex numbers",
    R3__is_subclass_of=p.I13["mathematical set"],
)

I2738 = p.create_item(
    R1__has_label="field of complex numbers",
    R2__has_description="field of complex numnbers",
    R4__is_instance_of=I8133["field of numbers"],
    R13__has_canonical_symbol=r"$\mathbb{C}$",
    R3033__has_type_of_elements=p.I34["complex number"],
)

I5807 = p.create_item(
    R1__has_label="sign",
    R2__has_description="returns the sign of a real number, i.e. on element of {-1, 0, 1}",
    R4__is_instance_of=I4895["mathematical operator"],
    R8__has_domain_of_argument_1=p.I35["real number"],
    R11__has_range_of_result=p.I37["integer number"],
)

I9906 = p.create_item(
    R1__has_label="square matrix",
    R2__has_description="a matrix for which the number of rows and columns are equal",
    R3__is_subclass_of=I9904["matrix"],
    # TODO: formalize the condition inspired by OWL
)

I9907 = p.create_item(
    R1__has_label="definition of square matrix",
    R2__has_description="the defining statement of what a square matrix is",
    R4__is_instance_of=p.I20["mathematical definition"],
)

with I9907.scope("setting") as cm:
    cm.new_var(M=p.uq_instance_of(I9904["matrix"]))
    cm.new_var(nr=p.uq_instance_of(p.I39["positive integer"]))

    cm.new_var(nc=p.instance_of(p.I39["positive integer"]))

    cm.new_rel(cm.M, R5938["has row number"], cm.nr)
    cm.new_rel(cm.M, R5939["has column number"], cm.nc)

with I9907.scope("premise") as cm:
    # number of rows == number of columns
    cm.new_equation(lhs=cm.nr, rhs=cm.nc)

with I9907.scope("assertion") as cm:
    cm.new_rel(cm.M, p.R30["is secondary instance of"], I9906["square matrix"])


p.end_mod()

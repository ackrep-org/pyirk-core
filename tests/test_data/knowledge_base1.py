"""
This file is the attempt to represten knowledge directly as code.

Motivation: this allows to explore formal knowledge representation without having to develop a domain specific
language first.

"""

import pyerk as p

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception

__MOD_ID__ = "M2085"
# __DEPENDENCIES__ = c.register()


p.register_mod(__MOD_ID__)

I5948 = p.create_item(
    R1__has_label="dynamical system",
    R2__has_description="system with the capability to change over time, optionally with explicit input and/or output",
    R4__instance_of=p.I2["Metaclass"],  # this means: this Item is an ordinary class
)


I4466 = p.create_item(
    R1__has_label="Systems Theory",
    R2__has_description="academic field; might be regarded as part of applied mathematics",
    R4__instance_of=p.I3["Field of science"],
    R5__is_part_of=[p.I4["Mathematics"], p.I5["Engineering"]],
)

R1001 = p.create_relation(R1__has_label="studies", R2__has_description="object or class wich an academic field studies")

I4466["Systems Theory"].set_relation(R1001["studies"], I5948["dynamical system"])


R4347 = p.create_relation(
    R1__has_label="has context",
    R2__has_description="establishes the context of a statement",
    # R8__has_domain_of_argument_1=I7723("general mathematical proposition"),
    # R10__has_range_of_result=<!! container of definition-items>
)

R4348 = p.create_relation(
    R1__has_label="has premise",
    R2__has_description="establishes the premise (if-part) of an implication",
    R8__has_domain_of_argument_1=p.I15["implication proposition"],
    # R10__has_range_of_result=<!! container of statements>
)

R4349 = p.create_relation(
    R1__has_label="has assertion",
    R2__has_description="establishes the assertion (then-part) of an implication",
    R8__has_domain_of_argument_1=p.I15["implication proposition"],
    # R10__has_range_of_result=<!! container of statements>
)


R9125 = p.create_relation(
    R1__has_label="has input dimension",
    # R8__has_domain_of_argument_1= generic dynamical system
    # R10__has_range_of_result= nonnegative integer
)

I6886 = p.create_item(
    R1__has_label="general ode state space representation",
    R2__has_description="explicit first order ODE system description of a dynamical system",
    R4__instance_of=p.I2["Metaclass"],
    # TODO: this has to use create_equation (to be implemented)
    R6__has_defining_equation=p.create_expression(r"$\dot x = f(x, u)$"),
)

I5356 = p.create_item(
    R1__has_label="general system property",
    R2__has_description="general property of dynamical system (not of its representation)",
    R4__instance_of=p.I2["Metaclass"],
)

I5357 = p.create_item(
    R1__has_label="differential flatness",
    R3__subclass_of=I5356["general system property"],
    R2__has_description="differential flatness",
)

I5358 = p.create_item(
    R1__has_label="exact input-to-state linearizability",
    R3__subclass_of=I5356["general system property"],
    # TODO: it might be necessary to restrict this to ode-state-space-systems
    R2__has_description="exact input-to-state linearizability (via static state feedback)",
)

"""
def create_I5847():
    R1__has_label = "Equivalence of flat systems and exact input-to-state linearizable systems"
    R4__instance_of = c.I15["implication proposition"]
    R2__has_description = (
                             "Establishes that differentially flat systems and exact input-to-state linearizable systems "
                             "are equivalent in the SISO case"
                         )

    def R4347__has_context():
        ctx = c.Context()
        ctx.sys = c.generic_instance(I6886["general_ode_state_space_representation"])
        c.set_restriction(ctx.sys, R9125["has input dimension"], 1)
        return ctx

    def R4348__has_premise(ctx: c.Context):
        ctx.sys.R

    def R4349__has_assertion():
        pass

    return c.create_item_from_namespace()


I5847 = create_I5847()

"""


# attempt without writing code

I2640 = p.create_item(
    R1__has_label="transfer function representation",
    R2__has_description="...",
    R4__instance_of=p.I2["Metaclass"],
)

I4235 = p.create_item(
    R1__has_label="mathematical object",
    R2__has_description="...",
    R4__instance_of=p.I2["Metaclass"],
)

p.R37["has definition"].set_relation(p.R8["has domain of argument 1"], I4235["mathematical object"])

# todo: what is the difference between an object and an expression?
I4236 = p.create_item(
    R1__has_label="mathematical expression",
    R2__has_description="...",
    R3__subclass_of=I4235["mathematical object"],
)

I4237 = p.create_item(
    R1__has_label="monovariate rational function",
    R2__has_description="...",
    R3__subclass_of=I4236["mathematical expression"],
)

I4237["monovariate rational function"].add_method(p.custom_call__create_evaluated_mapping, "_custom_call")

I4239 = p.create_item(
    R1__has_label="monovariate polynomial",
    R2__has_description=(
        "abstract monovariate polynomial (argument might be a complex-valued scalar, a matrix, an operator, etc.)"
    ),
    R3__subclass_of=I4237["monovariate rational function"],
)

I4240 = p.create_item(
    R1__has_label="matrix polynomial",
    R2__has_description="monovariate polynomial of quadratic matrices",
    R3__subclass_of=I4239["monovariate polynomial"],
)

I5484 = p.create_item(
    R1__has_label="finite set of complex numbers",
    R2__has_description="...",
    R3__subclass_of=p.I13["mathematical set"],
)

I2738 = p.create_item(
    R1__has_label="field of complex numnbers",
    R2__has_description="field of complex numnbers",
    # TODO: use p.I12 here
    R4__instance_of=I4235["mathematical object"],
    R13__has_canonical_symbol=r"$\mathbb{C}$",
    # todo: introduce algebraic structures and relation to set
)

I2739 = p.create_item(
    R1__has_label="open left half plane",
    R2__has_description="set of all complex numbers with negative real part",
    R4__instance_of=I4235["mathematical object"],
    R14__is_subset_of=I2738["field of complex numnbers"],
)

R5323 = p.create_relation(
    R1__has_label="has denominator",
    R2__has_description="...",
    R8__has_domain_of_argument_1=I4237["monovariate rational function"],
    R10__has_range_of_result=I4239["monovariate polynomial"],
)


R5334 = p.create_relation(
    R1__has_label="has representation",
    R2__has_description="relates an entity with an abstract mathematical representation",
    # R8__has_domain_of_argument_1= ...
    R10__has_range_of_result=I4235["mathematical object"],
)

R1757 = p.create_relation(
    R1__has_label="has set of roots",
    R2__has_description="set of roots for a monovariate function",
    R8__has_domain_of_argument_1=I4236["mathematical expression"],  # todo: this is too broad
    R10__has_range_of_result=I5484["finite set of complex numbers"],
)

I8181 = p.create_item(
    R1__has_label="properness",
    R2__has_description=(
        "applicable to monovariate rational functions; "
        "satisfied if degree of denominator is not smaller than degree of numerator"
    ),
    R4__instance_of=p.I11["mathematical property"],
)

I8182 = p.create_item(
    R1__has_label="strict properness",
    R2__has_description="satisfied if degree of denominator is greater than degree of numerator",
    R17__is_subproperty_of=I8181["properness"],
)

I7206 = p.create_item(
    R1__has_label="system-dynamical property",
    R2__has_description="base class for all systemdynamical properties",
    R3__subclass_of=p.I11["mathematical property"],
)

I7207 = p.create_item(
    R1__has_label="stability",
    R2__has_description="tendency to stay close to some distinguished trajectory (e.g. equilibrium)",
    R4__instance_of=I7206["system-dynamical property"],
)

# todo: this entity should be made more precise whether it is global or local
I7208 = p.create_item(
    R1__has_label="BIBO stability",
    R2__has_description=(
        "'bounded-input bounded-output stability'; "
        "satisfied if the system responds to every bounded input signal with a bounded output signal"
    ),
    R17__is_subproperty_of=I7207["stability"],
)


R1145 = p.create_relation(
    R1__has_label="is universally quantified",
    R2__has_description=(
        "specifies that the subject represents an universally quantified variable (usually denoted by '∀')"
    ),
    R8__has_domain_of_argument_1=I4235["mathematical object"],
    R11__has_range_of_result=bool,
    R18__has_usage_hints="used to specify the free variables in theorems and similar statements",
)


def uq_instance_of(type_entity: p.Item, r1: str = None, r2: str = None) -> p.Item:
    """
    Shortcut to create an instance and set the relation R1145["is universally quantified"] to True in one step
    to allow compact notation.

    :param type_entity:     the type of which an instance is created
    :param r1:              the label (tried to extract from calling context)
    :param r2:              optional description

    :return:                new item
    """

    if r1 is None:
        try:
            r1 = p.core.get_key_str_by_inspection(upcount=1)
        # TODO: make this except clause more specific
        except:
            # note this fallback naming can be avoided by explicitly passing r1=...  as kwarg
            r1 = f"{type_entity.R1} – instance"

    instance = p.instance_of(type_entity, r1, r2)
    instance.set_relation(R1145["is universally quantified"], True)
    return instance


I5325 = p.create_item(
    R1__has_label="Hurwitz polynomial",
    R2__has_description="monovariate polynomial of quadratic matrices",
    R3__subclass_of=I4239["monovariate polynomial"],
)

# <definition>
I4455 = p.create_item(
    R1__has_label="definition of Hurwitz polynomial",
    R2__has_description="the defining statement of what a hurwitz polynomial is",
    R4__is_instance_of=p.I20["mathematical definition"],
)

with I4455.scope("context") as cm:
    cm.new_var(P=uq_instance_of(I4239["monovariate polynomial"]))
    cm.new_var(set_of_roots=p.instance_of(I5484["finite set of complex numbers"]))
    cm.new_rel(I4455.P, R1757["has set of roots"], I4455.set_of_roots)


with I4455.scope("premises") as cm:
    cm.new_rel(I4455.set_of_roots, p.R14["is subset of"], I2739["open left half plane"])

with I4455.scope("assertions") as cm:
    cm.new_rel(I4455.P, p.R30["is secondary instance of"], I5325["Hurwitz polynomial"])

I5325["Hurwitz polynomial"].set_relation(p.R37["has definition"], I4455["definition of Hurwitz polynomial"])
# </definition>


# TODO: open question should  I3007["stability theorem for a rational transfer function"] be constructed by using I5325["Hurwitz polynomial"]
# con: BIBO-stability might be meaningfull also for Transferfunctions with nonpolynomial denominators


# <theorem>
# todo this should be an equivalence instead of an implication
I3007 = p.create_item(
    R1__has_label="stability theorem for a rational transfer function",
    R2__has_description="establishes the relation between BIBO-Stability and the poles of the transfer function",
    R4__instance_of=p.I15["implication proposition"],
)

with I3007.scope("context") as cm:
    cm.new_var(sys=uq_instance_of(I5948["dynamical system"]))

    cm.new_var(tf_rep=p.instance_of(I2640["transfer function representation"]))
    cm.new_var(denom=p.instance_of(I4239["monovariate polynomial"]))
    cm.new_var(set_of_poles=p.instance_of(I5484["finite set of complex numbers"]))

    cm.new_rel(I3007.sys, R5334["has representation"], I3007.tf_rep)
    cm.new_rel(I3007.tf_rep, R5323["has denominator"], I3007.denom)
    cm.new_rel(I3007.denom, R1757["has set of roots"], I3007.set_of_poles)

with I3007.scope("premises") as cm:
    cm.new_rel(I3007.set_of_poles, p.R14["is subset of"], I2739["open left half plane"])
    cm.new_rel(I3007.tf_rep, p.R16["has property"], I8181["properness"])

with I3007.scope("assertions") as cm:
    cm.new_rel(I3007.sys, p.R16["has property"], I7208["BIBO stability"])
# </theorem>


# preparation for next theorem

# Note, it might be worthwile to introduce the set of all (non-negative/positive) integer numbers as a separate item
I4463 = p.create_item(
    R1__has_label="non-negative integer",
    R2__has_description="mathematical type equivalent to Nat (from type theory): non-negative integer number",
    R4__is_instance_of=p.I12["mathematical object"],
)

I4464 = p.create_item(
    R1__has_label="positive integer",
    R2__has_description="mathematical type equivalent to Nat+ (from type theory): positive integer number",
    R3__is_subclass_of=I4463["non-negative integer"],
)

# todo: this needs more generalization
I9904 = p.create_item(
    R1__has_label="matrix",
    R2__has_description="matrix of (in general) complex numbers, i.e. matrix over the field of complex numbers",
    R3__is_subclass_of=I4235["mathematical object"],
)

I9905 = p.create_item(
    R1__has_label="zero matrix",
    R2__has_description="like its superclass but with all entries equal to zero",
    R3__is_subclass_of=I9904["matrix"],
)

I9906 = p.create_item(
    R1__has_label="square matrix",
    R2__has_description="a matrix for which the number of rows and columns are equal",
    R3__is_subclass_of=I9904["matrix"],
    # TODO: formalize the condition inspired by OWL
)

R5938 = p.create_relation(
    R1__has_label="has row number",
    R2__has_description="specifies the number of rows of a matrix",
    R8__has_domain_of_argument_1=I9904["matrix"],
    R10__has_range_of_result=I4463["non-negative integer"],
)

R5939 = p.create_relation(
    R1__has_label="has column number",
    R2__has_description="specifies the number of columns of a matrix",
    R8__has_domain_of_argument_1=I9904["matrix"],
    R10__has_range_of_result=I4463["non-negative integer"],
)

R5940 = p.create_relation(
    R1__has_label="has characteristic polynomial",
    R2__has_description="specifies the characteristic polynomial of a square matrix A, i.e. det(s·I-A)",
    R8__has_domain_of_argument_1=I9906["square matrix"],
    R10__has_range_of_result=I4239["monovariate polynomial"],
)

# <definition>
I9907 = p.create_item(
    R1__has_label="definition of square matrix",
    R2__has_description="the defining statement of what a square matrix is",
    R4__is_instance_of=p.I20["mathematical definition"],
)

with I9907.scope("context") as cm:
    cm.new_var(M=uq_instance_of(I9904["matrix"]))
    cm.new_var(nr=uq_instance_of(I4464["positive integer"]))

    cm.new_var(nc=p.instance_of(I4464["positive integer"]))

    cm.new_rel(I9907.M, R5938["has row number"], I9907.nr)
    cm.new_rel(I9907.M, R5939["has column number"], I9907.nc)

with I9907.scope("premises") as cm:
    # number of rows == number of columns
    cm.new_equation(lhs=I9907.nr, rhs=I9907.nc)

with I9907.scope("assertions") as cm:
    cm.new_rel(I9907.M, p.R30["is secondary instance of"], I9906["square matrix"])

# </definition>

I9906["square matrix"].set_relation(p.R37["has definition"], I9907["definition of square matrix"])

# <theorem>

I3749 = p.create_item(
    R1__has_label="Cayley-Hamilton theorem",
    R2__has_description="establishes that every square matrix is a root of its own characteristic polynomial",
    R4__instance_of=p.I15["implication proposition"],
)

# TODO: specify universal quantification for A and n

with I3749["Cayley-Hamilton theorem"].scope("context") as cm:
    cm.new_var(A=uq_instance_of(I9906["square matrix"]))
    cm.new_var(n=uq_instance_of(I4464["positive integer"]))

    cm.new_var(P=p.instance_of(I4240["matrix polynomial"]))
    cm.new_var(Z=p.instance_of(I9905["zero matrix"]))

    cm.new_rel(I3749.A, R5938["has row number"], I3749.n)
    cm.new_rel(I3749.A, R5940["has characteristic polynomial"], I3749.P)
    cm.new_rel(I3749.Z, R5938["has row number"], I3749.n)
    cm.new_rel(I3749.Z, R5939["has column number"], I3749.n)
    cm.new_rel(I3749.Z, p.R24["has LaTeX string"], r"\mathbf{0}")

with I3749["Cayley-Hamilton theorem"].scope("assertions") as cm:
    cm.new_equation(lhs=I3749.P(I3749.A), rhs=I3749.Z)

# </theorem>

# the following is for testing qualifiers:

I7435 = p.create_item(
    R1__has_label="human",
    R2__has_description="human being",
    R4__instance_of=p.I2["Metaclass"],
    R33__has_corresponding_wikidata_entity="Q5",
)


I2746 = p.create_item(
    R1__has_label="Rudolf Kalman",
    R2__has_description="electrical engineer and mathematician",
    R4__instance_of=I7435["human"],
)


I1342 = p.create_item(
    R1__has_label="academic institution",
    R2__has_description="educational institution dedicated to education and research",
    R4__instance_of=p.I2["Metaclass"],
    R33__has_corresponding_wikidata_entity="Q4671277",
)

I9942 = p.create_item(
    R1__has_label="Stanford University",
    R2__has_description="private research university in California, USA",
    R4__instance_of=I1342["academic institution"],
    R33__has_corresponding_wikidata_entity="Q41506",
)

I7301 = p.create_item(
    R1__has_label="ETH Zürich",
    R2__has_description="Swiss Federal Institute of Technology in Zürich",
    R4__instance_of=I1342["academic institution"],
    R33__has_corresponding_wikidata_entity="Q11942",
)

R1833 = p.create_relation(
    R1__has_label="has employer",
    R2__has_description="specifies for which entity (organisation/person) the subject works",
    R33__has_corresponding_wikidata_entity="P108",
)

R4156 = p.create_relation(
    R1__has_label="has start time",
    R2__has_description="specifies when a statement becomes true",
    R33__has_corresponding_wikidata_entity="P580",
)

R4698 = p.create_relation(
    R1__has_label="has end time",
    R2__has_description="specifies when a statement ends to be true",
    R33__has_corresponding_wikidata_entity="P582",
)

start_time = p.QualifierFactory(R4156["has start time"])
end_time = p.QualifierFactory(R4698["has end time"])

I2746["Rudolf Kalman"].set_relation(
    R1833["has employer"], I9942["Stanford University"], qualifiers=[start_time("1964"), end_time("1971")]
)
I2746["Rudolf Kalman"].set_relation(
    R1833["has employer"], I7301["ETH Zürich"], qualifiers=[start_time("1973"), end_time("1997")]
)

# End of qualifier-testing code


p.Sequence("y", p.I000["time derivative of order i"], link_op=p.I000["listing"], start=0, stop="k")

# → it would be nice if one could interactively execute/write out such a sequence for given variable values


I4349 = p.create_item(
    R1__has_label="equivalence of flatness and input-state-linearizability for SISO systems",
    R2__has_description="establishes the equivalence of flatness and input-state-linearizability for SISO systems",
    R4__instance_of=p.I15["implication proposition"],
)

# </theorem>
# <statement preparation>
I2277 = p.create_item(
    R1__has_label="statement",
    R2__has_description=(
        "models an 'ordinary statement' e.g. of a publication which is not distinguished as a formal theorem",
    ),
    R3__subclass_of=p.I15["implication proposition"],
)

# </statement preparation>

# <statement>
# source: A software framework for embedded nonlinear model predictive control using a gradient‐based augmented Lagrangian approach (GRAMPC)
# source doi: https://doi.org/10.1007/s11081-018-9417-2

# this is still unfinished work in progress:
I4216 = p.create_item(
    R1__has_label="statement about MPC for linear systems and the reducibility to quadratic problems",
    R2__has_description=(
        "for linear systems, the MPC problem can be reduced to a quadratic problem, for which the optimal control"
        "over the admissible polyhedral set can be precomputed."
    ),
    R4__instance_of=I2277["statement"],
)


with I4216.scope("context") as cm:
    cm.new_var(sys=p.instance_of(I5948["dynamical system"]))
    cm.new_var(state_space_sys=p.instance_of(I6886["general ode state space representation"]))
    cm.new_var(mpc_problem=p.instance_of(I5948["dynamical system"]))
    cm.new_var(quadratic_problem=p.instance_of(I5948["dynamical system"]))
    cm.new_var(mathematical_solution=p.instance_of(I5948["dynamical system"]))
    cm.new_var(optimal_control_law=p.instance_of(I5948["dynamical system"]))

    cm.new_rel(I4216.mpc_problem, p.R000["refers to"], I4216.sys)

with I4216.scope("premises") as cm:
    cm.new_rel(I4216.sys, p.R000["refers to"], I4216.sys)

with I4216.scope("assertions") as cm:
    cm.new_rel(I4216.mpc_problem, p.R000["can be reduced to"], I4216.quadratic_problem)


"""
Particularly for linear systems, the MPC problem can be reduced to a quadratic
problem, for which the optimal control over the admissible polyhedral set can be
precomputed.
"""

# </statement>

r"""

# experimental formulation of a theorem

- I3421__theorem_on_flat_and_system_output:
    R1__has_label="theorem on flat and system output"
    R2__has_description="Establishes that the (arbitrary) system output can be parameterized by the flat output, using derivatives up to order n-r."
    R4347__has_context:
        - sys R4__instance_of I6886__general_ode_state_space_representation
        - sys R!!__input_dimension 1
        - sys R!!__has_flat_output zeta
        - sys R!!__has_general_scalar_output y  # ggf. schon in systemdefinition
        - x R!!__is_generic_element_of_set sys.state_manifold
        # ggf. an Sumo (Government-Function) orientieren=zeta = Flat_output_function(sys)
        # problem: das ist nicht eindeutig (es gibt unendlich viele flache Ausgänge)
        # was _ist_ zeta (Variable, Zeitfunktion, Abbildung) (Buch: zeta = λ(x), also eine spezielle Art von flachem Ausgang. Was meint dann \dot zeta? → Parametrierung noch besser verstehen...
    R4348__has_premise:
        # das muss ich nochmal anpassen (Ausgang separat festlegen), oder mit in der Systemdefinition berücksichtigen
        - sys.y I9552__relative_degree_of_dynamical_system r
    R4349__has_assertion:
        - exists rho R4__instance_of I!!__multivariable_function
        - y R!!__equals rho(rho.allargs)
        - rho R!!__number_of_arguments k
        - for i in range(1, k):
            - rho.arg[k] R4__instance_of ??
            - rho.arg[k] R!!__is_time_derivative_of (zeta, i-1)
        - k R!!__equals (sys.n - r + 1)






- I7789__mathematical_representation_of_dynamical_system:
    R1__has_label="mathematical representation of dynamical_system"
    R2__has_description="..."
    R4__instance_of=I2__Metaclass
- I6886__general_ode_state_space_representation:
    R1__has_label="general ode state space representation"
    R2__has_description="explicit first order ODE system description of a dynamical system"
    R4__instance_of=I2__Metaclass
    R6__has_defining_equation="$\dot x = f(x, u)$"
- I2608__input_affine_ode_state_space_representation:
    R1__has_label="input affine ode state space representation"
    R2__has_description="Like the super class but with the condition that the input u only occurs affine."
    R3__subclass_of=I6886__general_state_space_representation
    R6__has_defining_equation="$\dot x = f(x) + g(x) u\\ y = h(x, u)$"

"""

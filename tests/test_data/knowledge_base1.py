"""
This file is the attempt to represten knowledge directly as code.

Motivation: this allows to explore formal knowledge representation without having to develop a domain specific
language first.

"""

import pyerk.core as c

__MOD_ID__ = "M2085"
#__DEPENDENCIES__ = c.register()

c.register_mod(__MOD_ID__)

I5948 = c.create_item(
    R1__has_label="dynamical system",
    R2__has_definition="system with the capability to change over time, optionally with explicit input and/or output",
    R4__instance_of=c.I2("Metaclass")  # this means: this Item is an ordinary class
)


I4466 = c.create_item(
    R1__has_label="Systems Theory",
    R2__has_definition="academic field; might be regarded as part of applied mathematics",
    R4__instance_of=c.I3("Field_of_science"),
    R5__part_of=[c.I4("Mathematics"), c.I5("Engineering")]
)

R1001 = c.create_relation(
    R1__has_label="studies",
    R2__has_definition="object or class wich an academic field studies"
)

I4466("Systems Theory").set_relation(R1001("studies"), I5948("dynamical system"))


R4347 = c.create_relation(
    R1__has_label="has context",
    R2__has_definition="establishes the context of a statement",
    # R8__has_domain_of_argument_1=I7723("general mathematical proposition"),
    # R10__has_range_of_result=<!! container of definition-items>
)

R4348 = c.create_relation(
    R1__has_label="has premise",
    R2__has_definition="establishes the premise (if-part) of an implication",
    R8__has_domain_of_argument_1=c.I15("implication proposition"),
    # R10__has_range_of_result=<!! container of statements>
)

R4349 = c.create_relation(
    R1__has_label="has assertion",
    R2__has_definition="establishes the assertion (then-part) of an implication",
    R8__has_domain_of_argument_1=c.I15("implication proposition"),
    # R10__has_range_of_result=<!! container of statements>
)


R9125 = c.create_relation(
    R1__has_label="has input dimension",
    # R8__has_domain_of_argument_1= generic dynamical system
    # R10__has_range_of_result= nonnegative integer
)

I6886 = c.create_item(
    R1__has_label="general ode state space representation",
    R2__has_definition="explicit first order ODE system description of a dynamical system",
    R4__instance_of=c.I2("Metaclass"),
    R6__has_defining_equation=r"$\dot x = f(x, u)$",
)

I5356 = c.create_item(
    R1__has_label="general system property",
    R2__has_definition="general property of dynamical system (not of its representation)",
    R4__instance_of=c.I2("Metaclass"),
)

I5357 = c.create_item(
    R1__has_label="differential flatness",
    R3__subclass_of=I5356("general system property"),
    R2__has_definition="differential flatness",
)

I5358 = c.create_item(
    R1__has_label="exact input-to-state linearizability",
    R3__subclass_of=I5356("general system property"),
    # TODO: it might be necessary to restrict this to ode-state-space-systems
    R2__has_definition="exact input-to-state linearizability (via static state feedback)",
)

"""
def create_I5847():
    R1__has_label = "Equivalence of flat systems and exact input-to-state linearizable systems"
    R4__instance_of = c.I15("implication proposition")
    R2__has_definition = (
                             "Establishes that differentially flat systems and exact input-to-state linearizable systems "
                             "are equivalent in the SISO case"
                         )

    def R4347__has_context():
        ctx = c.Context()
        ctx.sys = c.generic_instance(I6886("general_ode_state_space_representation"))
        c.set_restriction(ctx.sys, R9125("has input dimension"), 1)
        return ctx

    def R4348__has_premise(ctx: c.Context):
        ctx.sys.R

    def R4349__has_assertion():
        pass

    return c.create_item_from_namespace()


I5847 = create_I5847()

"""


# attempt without writing code

I2640 = c.create_item(
    R1__has_label="transfer function representation",
    R2__has_definition="...",
    R4__instance_of=c.I2("Metaclass"),
)

I4235 = c.create_item(
    R1__has_label="mathematical object",
    R2__has_definition="...",
    R4__instance_of=c.I2("Metaclass"),
)

# todo: what is the difference between an object and an expression?
I4236 = c.create_item(
    R1__has_label="mathematical expression",
    R2__has_definition="...",
    R3__subclass_of=I4235("mathematical object"),
)

I4237 = c.create_item(
    R1__has_label="monovariate rational function",
    R2__has_definition="...",
    R3__subclass_of=I4236("mathematical expression"),
)

I4239 = c.create_item(
    R1__has_label="monovariate polynomial",
    R2__has_definition="...",
    R3__subclass_of=I4236("mathematical expression"),
)

I5484 = c.create_item(
    R1__has_label="finite set of complex numnbers",
    R2__has_definition="...",
    R3__subclass_of=c.I13("mathematical set"),
)

I2738 = c.create_item(
    R1__has_label="field of complex numnbers",
    R2__has_definition="field of complex numnbers",
    R4__instance_of=I4235("mathematical object"),
    R13__has_canonical_symbol=r"$\mathbb{C}$",
    # todo: introduce algebraic structures and relation to set
)

I2739 = c.create_item(
    R1__has_label="open left half plane",
    R2__has_definition="set of all complex numbers with negative real part",
    R4__instance_of=I4235("mathematical object"),
    R14__is_subset_of=I2738("field of complex numnbers"),
)

R5323 = c.create_relation(
    R1__has_label="has denominator",
    R2__has_definition="...",
    R8__has_domain_of_argument_1=I4237("monovariate rational function"),
    R10__has_range_of_result=I4239("monovariate polynomial")
)


R5334 = c.create_relation(
    R1__has_label="has representation",
    R2__has_definition="relates an entity with an abstract mathematical representation",
    # R8__has_domain_of_argument_1= ...
    R10__has_range_of_result=I4235("mathematical object"),
)

R1757 = c.create_relation(
    R1__has_label="has set of roots",
    R2__has_definition="set of roots for a monovariate function",
    R8__has_domain_of_argument_1=I4236("mathematical expression"),  # todo: this is too broad
    R10__has_range_of_result=I5484("finite set of complex numbers")
)

I8181 = c.create_item(
    R1__has_label="properness",
    R2__has_definition=(
        "applicable to monovariate rational functions; "
        "satisfied if degree of denominator is not smaller than degree of numerator",
    ),
    R4__instance_of=c.I11("mathematical property")
)

I8182 = c.create_item(
    R1__has_label="strict properness",
    R2__has_definition=(
        "satisfied if degree of denominator is greater than degree of numerator",
    ),
    R17__is_subproperty_of=I8181("properness")
)

I7206 = c.create_item(
    R1__has_label="system-dynamical property",
    R2__has_definition="base class for all systemdynamical properties",
    R3__subclass_of=c.I11("mathematical property")
)

I7207 = c.create_item(
    R1__has_label="stability",
    R2__has_definition="tendency to stay close to some distinguished trajectory (e.g. equilibrium)",
    R4__instance_of=I7206("system-dynamical property")
)

# todo: this entity should be made more precise whether it is global or local
I7208 = c.create_item(
    R1__has_label="BIBO stability",
    R2__has_definition=(
        "'bounded-input bounded-output stability'; "
        "satisfied if the system responds to every bounded input signal with a bounded output signal",
    ),
    R17__is_subproperty_of=I7207("stability")
)

# <theorem>

I3007 = c.create_item(
    R1__has_label="stability theorem for a rational transfer function",
    R2__has_definition="establishes the relation between BIBO-Stability and the poles of the transfer function",
    R4__instance_of=c.I15("implication proposition"),
)

I3007.define_context_variables(
    sys=c.instance_of(I5948("dynamical system")),
    tf_rep=c.instance_of(I2640("transfer function representation")),
    denom=c.instance_of(I4239("monovariate polynomial")),
    set_of_poles=c.instance_of(I5484("finite set of complex numbers"))
)

I3007.set_context_relations(
    (I3007.sys, R5334("has representation"), I3007.tf_rep),
    (I3007.tf_rep, R5323("has denominator"), I3007.denom),
    (I3007.denom, R1757("has set of roots"), I3007.set_of_poles),
)

I3007.set_premises(
    (I3007.set_of_poles, c.R14("is subset of"), I2739("open left half plane")),
    (I3007.tf_rep, c.R16("has property"), I8181("properness"))
)

I3007.set_assertions(
    (I3007.sys, c.R16("has property"), I7208("BIBO stability"))
)

# </theorem>

I4349 = c.create_item(
    R1__has_label="equivalence of flatness and input-state-linearizability for SISO systems",
    R2__has_definition="establishes the equivalence of flatness and input-state-linearizability for SISO systems",
    R4__instance_of=c.I15("implication proposition"),

)

# </theorem>

# <statement>

I4216 = c.create_item(
    R1__has_label="statement about MPC for linear systems and the reducibility to quadratic problems",
    R2__has_description=(
        "for linear systems, the MPC problem can be reduced to a quadratic problem, for which the optimal control"
        "over the admissible polyhedral set can be precomputed."
    ),
    R4__instance_of=c.I15("implication proposition"),

)

I4216.define_context_variables(
    sys=c.instance_of(I5948("dynamical system")),
    state_space_sys=c.instance_of(I6886("general ode state space representation")),
    mpc_problem=c.instance_of(I5948("dynamical system")),
    quadratic_problem=c.instance_of(I5948("dynamical system")),
    mathematical_solution=c.instance_of(I5948("dynamical system")),
    optimal_control_law=c.instance_of(I5948("dynamical system")),
)

R1234a = c.create_relation(R1="dummy")
R1234b = c.create_relation(R1="dummy")


I4216.set_context_relations(
    (I4216.mpc_problem, R1234a("refers_to"), I4216.sys)
)

I4216.set_premises(
    (I4216.sys, R1234a("refers_to"), I4216.sys),
)

I4216.set_assertions(
    (I4216.mpc_problem, R1234b("can_be_reduced_to"), I4216.quadratic_problem),

)
"""
Particularly for linear systems, the MPC problem can be reduced to a quadratic
problem, for which the optimal control over the admissible polyhedral set can be
precomputed.
"""

# </statement>
from ipydex import IPS, activate_ips_on_exception
activate_ips_on_exception()
if __name__ == "__main__":
    IPS()


"""

# experimental formulation of a theorem

- I3421__theorem_on_flat_and_system_output:
    R1__has_label="theorem on flat and system output"
    R2__has_definition="Establishes that the (arbitrary) system output can be parameterized by the flat output, using derivatives up to order n-r."
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
    R2__has_definition="..."
    R4__instance_of=I2__Metaclass
- I6886__general_ode_state_space_representation:
    R1__has_label="general ode state space representation"
    R2__has_definition="explicit first order ODE system description of a dynamical system"
    R4__instance_of=I2__Metaclass
    R6__has_defining_equation="$\dot x = f(x, u)$"
- I2608__input_affine_ode_state_space_representation:
    R1__has_label="input affine ode state space representation"
    R2__has_definition="Like the super class but with the condition that the input u only occurs affine."
    R3__subclass_of=I6886__general_state_space_representation
    R6__has_defining_equation="$\dot x = f(x) + g(x) u\\ y = h(x, u)$"

"""
"""
This file is the attempt to represten knowledge directly as code.

Motivation: this allows to explore formal knowledge representation without having to develop a domains specific
language first.

"""

import pykerl.core as c

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

I4466("Systems Theory").R1001__studies(I5948("dynamical system"))


I7725 = c.create_item(
    R1__has_label="implication proposition",
    R2__has_definition="proposition, where the premise (if-part) implies the assertion (then-part)",
    # R3__subclass_of=I7723("general mathematical proposition")
)

R4347 = c.create_relation(
    R1__has_label="has context",
    R2__has_definition="establishes the context of a statement",
    # R8__has_domain_of_argument_1=I7723("general mathematical proposition"),
    # R10__has_range_of_result=<!! container of definition-items>
)

R4348 = c.create_relation(
    R1__has_label="has premise",
    R2__has_definition="establishes the premise (if-part) of an implication",
    R8__has_domain_of_argument_1=I7725("implication proposition"),
    # R10__has_range_of_result=<!! container of statements>
)

R4349 = c.create_relation(
    R1__has_label="has assertion",
    R2__has_definition="establishes the assertion (then-part) of an implication",
    R8__has_domain_of_argument_1=I7725("implication proposition"),
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


def create_I5847():
    R1__has_label = "Equivalence of flat systems and exact input-to-state linearizable systems"
    R4__instance_of = I7725("implication proposition")
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


from ipydex import IPS, activate_ips_on_exception
activate_ips_on_exception()
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
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


from ipydex import IPS, activate_ips_on_exception
activate_ips_on_exception()
IPS()

"""

- I7724__implication_proposition:
    R1__has_label: "proposition of implication type "
    R2__has_definition: "proposition, where the premise (if-part) implies the assertion (then-part)"
    R3__subclass_of: I7723__general_mathematical_proposition





- I7789__mathematical_representation_of_dynamical_system:
    R1__has_label: "mathematical representation of dynamical_system"
    R2__has_definition: "..."
    R4__instance_of: I2__Metaclass
- I6886__general_ode_state_space_representation:
    R1__has_label: "general ode state space representation"
    R2__has_definition: "explicit first order ODE system description of a dynamical system"
    R4__instance_of: I2__Metaclass
    R6__has_defining_equation: "$\dot x = f(x, u)$"
- I2608__input_affine_ode_state_space_representation:
    R1__has_label: "input affine ode state space representation"
    R2__has_definition: "Like the super class but with the condition that the input u only occurs affine."
    R3__subclass_of: I6886__general_state_space_representation
    R6__has_defining_equation: "$\dot x = f(x) + g(x) u\\ y = h(x, u)$"

"""
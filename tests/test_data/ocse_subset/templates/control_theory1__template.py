# Note: this is not the real module for this URI it is an autogenerated subset for testing
import pyirk as p


# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception  # noqa

ma = p.irkloader.load_mod_from_path("./math1.py", prefix="ma")
ag = ma.ag


__URI__ = "irk:/ocse/0.2/control_theory"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


insert_entities = [
    I1347["Lie derivative of scalar field"],
    I2928["general model representation"],
    I6886["general ode state space representation"],
    I4466["Systems Theory"],
    I7641["general system model"],
    I5948["dynamical system"],
    R7641["has approximation"],
    I5356["general system property"],
    I4101["general time variance"],
    I7733["time invariance"],
    I1793["general model representation property"],
    I2827["general nonlinearity"],
    I6091["control affine"],
    I5247["polynomial"],
    I4761["linearity"],
    I1898["lti"],
    I2562["general property of pde"],
    I2557["quasilinearity"],
    I3114["semilinearity"],
    I3863["linearity"],
    I5236["general trajectory property"],
    I7207["stability"],
    I5082["local attractiveness"],
    I2931["local Lyapunov stability"],
    I4900["local asymptotical stability"],
    I9642["local exponential stability"],
    I9210["stabilizability"],
    I7864["controllability"],
]


p.end_mod()

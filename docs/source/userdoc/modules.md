(sec_modules)=
## Pyirk Modules and Packages

Pyirk entities and statements are organized in Pyirk *modules* (python files). Each module has to specify its own URI via the variable `__URI__`. The uri of an entity from that module is formed by `<module URI>#<entity short_key>`. Modules can be bundled together to form pyirk *packages*. A Pyirk package consists of a directory containing a file `irkpackage.toml` and at least one Pyirk module.

Modules can depend on other modules. A usual pattern is the following:

```python
# in module control_theory1.py

import pyirk as p
mod = p.irkloader.load_mod_from_path("./math1.py", prefix="ma")
```

Here the variable `mod` is the module object (like from ordinary python import) and allows to access to the complete namespace of that module:
```python
# ...

A = p.instance_of(mod.I9904["matrix"])
```

The prefix `"ma"` can also be used to refer to that module like here
```python
# ...

res = A.ma__R8736__depends_polynomially_on
```

Rationale: The attribute name `ma__R8736__depends_polynomially_on` is handled as a string by Python (in the method `__getattr__`). While `mod.R8736` is the relation object we cannot use this syntax as attribute name.

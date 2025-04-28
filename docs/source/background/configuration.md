(sec_configuration)=
# Pyirk Configuration


## Global Configuration

To enable all features of Pyirk it is necessary to access a global configuration file (`config.toml`).
It can be created via `pyirk --bootstrap-config`. Its location is platform dependent and determined by means of the module `platformdirs`. E.g. on Linux it is `/home/$USER/.config/pyirk/config.toml`.

After creation of `config.toml` or after adding/moving/removing Pyirk packages this file must be edited.

Example:
```toml
# Pyirk configuration file (example)

[package.ocse]
path = "/home/USER/irk-data/ocse"


[package.omt]
path = "/home/USER/projects/experimental/omt"
```

The presence of a valid config file is necessary to enable `p.irkloader.load_mod_from_uri(...)` because otherwise Pyirk would not know in which directories to look for modules.

**Note:** In earlier versions of Pyirk a certain directory structure was assumed. However, this proved to be too unflexible.



## Configuration of IRK-Packages

Every valid IRK-Package must have a `irkpackage.toml` file in its root directory.
Example (from OCSE):

```toml
# these keys are mandatory
main_module = "control_theory1.py"
main_module_prefix = "ct"
version = "0.2.2.0"

# this is optional
further_modules = ["math1.py", "agents1.py"]
```

**Note:** The URI of each module is specified within the respective module.
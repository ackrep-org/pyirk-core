(sec_cli_overview)=
# Command Line Interface

While most of the pyirk usage wil come from actual python code, pyirk also provides a rich command line interface (CLI)
which can be used for introspection purposes (visualization) or interactive usage.


(sec_visualization)=
## Visualization

Currently there is some basic visualization support via the command line. To visualize
your a module (including its relations to the builtin_entities) you can use a command
like

```
pyirk --load-mod demo-module.py demo -vis __all__
```

## Interactive Usage

To open an IPython shell with a loaded module run e.g.

```
pyirk -i -l control_theory1.py ct
```

Then, you have `ct` as variable in your namespace and can e.g. run `print(ct.I5167.R1)`.

(The above command assumes that the file `control_theory1.py` is in your current working
directory.)


## Manpage 

For an overview of available command line options, execute the command:

```
pyirk -h
```

```{argparse}
:module: pyirk.script
:func: create_parser
:prog: pyirk
```

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


# Overview: pyerk

Pyerk is the python implementation of the ***e**mergent **r**epresentation of **k**nowledge* framework.

- Designed to formally represent knowledge (including meta levels)
- Implementation-status: "early alpha"
- Inspired by OWL, but much more expressive
    - ... at the cost of guarantied computability
- Inspired by Wikidata, but much simpler
- Inspired by SUO-KIF, but with less brackets
- Represented directly in python: → imperative instaead of declarative knowledge representation


Pyerk originated and is currently (2022) mainly developed with focus on representing knowledge from the domain of *control theory* as part of the *Automatic Control Knowledge Repository ([ACKREP](https://ackrep.org))*. However, in principle, it aims to be applicable wo a wide range of domains.


# Assumed Directory Structure

```
<erk-root>/
├── pyerk/                          ← repo with the code of the core package
│  ├── .git/
│  ├── README.md                    ← the currently displayed file (README.md)
│  ├── setup.py                     ← deployment script
│  ├── src/pyerk/auxiliary.py       ← module containing function get_erk_root_dir()
│  └── ...
│
├── django-erk-gui/                 ← repo with the code for the django gui (project and! app)
│  │                                  (this package is optional)
│  ├── .git/
│  ├── manage.py
│  └── ...
│
├── erk-data/                       ← directory that contains erk-knowledge packages (for actual usage)
│  ├── ocse/                        ← a knowledge package (ontology of control systems engineering)
│  │  ├── .git/
│  │  ├── README.md
│  │  ├── ocse.py                   ← a knowledge module
│  │  │                             (this one is currently used for unit testing)
│  │  └── ...
│  ├── xyz123/                      ← another knowledge package
│  │  └── ...
│  └── ...
├── erk-data-for-unittests/         ← directory that contains erk-knowledge packages
│  └── ...                            (unittest version, probably older and different from
│                                      production data.)
└──...
```

# Documentation

There is not yet "real" documentation available. However, to get an overview of the most importent features you might want to have a look at the source code, especially at the files [builtin_entities.py](/src/pyerk/builtin_entities.py) and the [test_core.py](tests/test_core.py).


Nevertheless, some topics are explained here until there is some more comprehensive documentation.

## Visualization

Currently there is some basic visualization support via the command line. To visualize your a module (including its relations to the builtin_entities) you can use a command like

```
pyerk -rwd --load-mod demo-module.py demo -vis __all__
```

## Interactive Usage

To open an IPython shell with a loaded module run e.g.

```
pyerk -i -rwd -l control_theory1.py ct
```

Then, you have `ct` as variable in your namespace and can e.g. run `print(ct.I5167.R1`).

(The above command assumes that the file `control_theory1.py` is in your current working directory.)

## Multilinguality

Pyerk aims to support an arbitrary number of languages by so called *language specified strings*. Currently support for English and German is preconfigured in `pyerk.settings`. These language specified strings are instances of the class `rdflib.Literal` where the `.language`-attribute is set to one of the values from `pyerk.setting.SUPPORTED_LANGUAGES` and can be created like:

```python
from pyerk import de, en

# ...

lss1 = "some english words"@en
lss2 = "ein paar deutsche Wörter"@de
```

where `en, de` are instances of `pyerk.core.LangaguageCode`.

The usage inside pyerk is best demonstrated by the unittest `test_c02__multilingual_relations`, see [test_core.py](tests/test_core.py).


# Coding style

We use `black -l 120 ./` to ensure coding style consistency.

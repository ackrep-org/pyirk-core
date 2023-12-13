[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyPI version](https://badge.fury.io/py/pyirk.svg)](https://pypi.org/project/pyirk/)
[![Documentation Status](https://readthedocs.org/projects/pyirk-core/badge/?version=latest)](https://pyirk-core.readthedocs.io/en/latest)
![ci](https://github.com/ackrep-org/pyirk-core/actions/workflows/python-app.yml/badge.svg)


# Overview: pyirk

Pyirk is the python implementation of the ***e**mergent **r**epresentation of **k**nowledge* framework.

- Designed to formally represent knowledge (including meta levels)
- Implementation-status: "early alpha"
- Inspired by OWL, but much more expressive
    - ... at the cost of guarantied computability
- Inspired by Wikidata, but much simpler
- Inspired by SUO-KIF, but with less brackets
- Represented directly in python: → imperative instaead of declarative knowledge representation


Pyirk originated and is currently (2022) mainly developed with focus on representing knowledge from the domain of *control theory* as part of the *Automatic Control Knowledge Repository ([ACKREP](https://ackrep.org))*. However, in principle, it aims to be applicable wo a wide range of domains.


# Assumed Directory Structure

```
<irk-root>/
├── pyirk/                          ← repo with the code of the core package
│  ├── .git/
│  ├── README.md                    ← the currently displayed file (README.md)
│  ├── setup.py                     ← deployment script
│  ├── src/pyirk/auxiliary.py       ← module containing function get_irk_root_dir()
│  └── ...
│
├── django-irk-gui/                 ← repo with the code for the django gui (project and! app)
│  │                                  (this package is optional)
│  ├── .git/
│  ├── manage.py
│  └── ...
│
├── irk-data/                       ← directory that contains irk-knowledge packages (for actual usage)
│  ├── ocse/                        ← a knowledge package (ontology of control systems engineering)
│  │  ├── .git/
│  │  ├── README.md
│  │  ├── ocse.py                   ← a knowledge module
│  │  │                             (this one is currently used for unit testing)
│  │  └── ...
│  ├── xyz123/                      ← another knowledge package
│  │  └── ...
│  └── ...
├── irk-data-for-unittests/         ← directory that contains irk-knowledge packages
│  └── ...                            (unittest version, probably older and different from
│                                      production data.)
└──...
```

# Documentation

Rudimentary documentation is available at <https://pyirk-core.readthedocs.io> (generated from the [`/docs`](/docs) directory). To get an overview of the most importent features you might also want to have a look at the source code, especially at the files [builtin_entities.py](/src/pyirk/builtin_entities.py) and the [test_core.py](tests/test_core.py).


# Coding style

We use `black -l 120 ./` to ensure coding style consistency.

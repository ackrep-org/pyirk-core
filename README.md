[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyPI version](https://badge.fury.io/py/pyirk.svg)](https://pypi.org/project/pyirk/)
[![Documentation Status](https://readthedocs.org/projects/pyirk-core/badge/?version=latest)](https://pyirk-core.readthedocs.io/en/latest)
![ci](https://github.com/ackrep-org/pyirk-core/actions/workflows/python-app.yml/badge.svg)


# Overview: pyirk

Pyirk is a Python framework for ***i**mperative **r**epresentation of **k**nowledge*.

- Designed to formally represent knowledge (including meta levels)
- Implementation-status: "early alpha"
- Inspired by OWL, but much more expressive
    - ... at the cost of guarantied computability
- Inspired by Wikidata, but much simpler
- Inspired by SUO-KIF, but with less brackets
- Represented directly in python: → imperative instead of declarative knowledge representation



While pyirk aims to be applicable to a wide range of knowledge domains, its origin an its current (2023) main focus is the representation of knowledge from the domain of *control theory* as part of the *Automatic Control Knowledge Repository ([ACKREP](https://ackrep.org))*.
Thus, a subset of the [Ontology of Control Systems Engineering](https://github.com/ackrep-org/ocse) is used as test data for pyirk. In fact, both projects are practically co-developed.

Not that, originally pyirk (imperative representation of knowledge) was called pyerk (emergent representation of knowledge), in case you come across some old version.

# Recommended Directory Structure

```
<irk-root>/
├── pyirk-core/                     ← repo with the code of the core package
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
└──...
```

# Documentation

Rudimentary documentation is available at <https://pyirk-core.readthedocs.io> (generated from the [`/docs`](/docs) directory). To get an overview of the most important features you might also want to have a look at the source code, especially at the files [builtin_entities.py](/src/pyirk/builtin_entities.py) and the test cases, e.g., [test_core.py](tests/test_core.py).


# Coding style

We use `black -l 120 ./` to ensure coding style consistency.

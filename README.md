[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


# (Python based) Easy Representation of Knowledge (pyERK)

- Currently in alpha-phase
- Inspired by OWL, but more expressive
- Inspired by Wikidata, but much simpler
- Inspired by SUO-KIF, but with less brackets
- Represented directly in python
- Designed to formally represent knowledge (including meta levels)


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
│  ├── .git/
│  ├── manage.py
│  └── ...
│
├── erk-data/                       ← directory that contains erk-knowledge packages
│  ├── control-theory/              ← a knowledge package
│  │  ├── .git/
│  │  ├── README.md
│  │  ├── control_theory1.py        ← a knowledge module
│  │  │                             (this one is currently used for unit testing)
│  │  └── ...
│  └── ...
└...
```

# Coding style

We use `black -l 120 ./` to ensure coding style consistency.

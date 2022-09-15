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
│  ├── .git/
│  ├── manage.py
│  └── ...
│
├── erk-data/                       ← directory that contains erk-knowledge packages
│  ├── ocse0.2/                     ← a knowledge package
│  │  ├── .git/
│  │  ├── README.md
│  │  ├── ocse.py                  ← a knowledge module
│  │  │                             (this one is currently used for unit testing)
│  │  └── ...
│  └── ...
└...
```

# Coding style

We use `black -l 120 ./` to ensure coding style consistency.

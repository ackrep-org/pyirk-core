# Build the Documentation

This guide will show you how to build the documentation on your machine.

```{hint}
Automatically generated documentation is available at: <https://pyirk-core.readthedocs.io>. (Be sure to select the branch of interest from the menu in the lower right).
```

## Installing the requirements

Run `pip install -r requirements.txt` in this directory to install the dependencies to build the documentation.

## Run the build and preview locally

Run `make html` in this directory to build the docs on your system. Open `build/html/index.html` to see the result.

In `/docs/build/html` run `python -m http.server 8000`.

## Debug Readthedocs Build

In `/docs` run `sphinx-autobuild ./source ./build/`. Then visit <http://127.0.0.1:8000>


## Editing the Docs

We use markdown (Sphinx default is ReST). Useful links:

- <https://www.sphinx-doc.org/en/master/usage/markdown.html>
- <https://coderefinery.github.io/documentation/sphinx/>

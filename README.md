# Swampyer

## Purpose

Intended as yet another way of interacting with a Web Application Messaging Protocol (WAMP) service, this is intended to be a very lightweight library as an alternative to autobahn.js.

## Documentation

Examples can be found in the "examples" directory.

## Installation

Install by using:

`pip install swampyer`

## Development

The targets are `python3.6` and up. `python 2.7` support was dropped in version `3.0.20211103`. For 2.7 support use:

```
# For Python 2.7 support
pip install swampyer=2.20210513
```

Tox is used to automate the testing between the various python versions.

### Setup:

Setting up the environment can by:

```bash
git clone https://github.com/zabertech/python-swampyer.git
pipenv shell
pipenv install --dev
```

### Testing

Execute by running

```bash
tox
```

### Packaging

```
python setup.py sdist && twine upload dist/*
```


# Swampyer

## Purpose

Intended as yet another way of interacting with a Web Application Messaging Protocol (WAMP) service, this is intended to be a very lightweight library as an alternative to autobahn.js.

## Documentation

Examples can be found in the "examples" directory.

## Installation

Install by using:

`pip install swampyer`

## Development

The targets are `python2.7`, `python3.6` and up.

The development environment requires `python3.6` as the `crossbar.io` based test server is unable to run in `python2.7`.

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


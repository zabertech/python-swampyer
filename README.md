# Swampyer

## Purpose

Intended as yet another way of interacting with a Web Application Messaging Protocol (WAMP) service, this is intended to be a lighter library for imports than the official autobahn-python.

The targets are `python3.8` and up.

`python 2.7` support was dropped in version `3.0.20211103`. For 2.7 support use:

```
# For Python 2.7 support
pip install swampyer=2.20210513
```

## Documentation

Examples can be found in the "examples" directory.

## Installation

Install by using:

`pip install swampyer`

## Development

Development is mostly done from within a docker container since we need to run the code against a slew of python versions to validate the code.

### Setup:

Setting up the environment can by:

```bash
git clone https://github.com/zabertech/python-swampyer.git
cd python-swampyer
docker compose up -d
```

### Testing

Nox is used to automate the testing between the various python versions.

Once the environment is up, run from the checkout directory the following command

```bash
docker compose exec python_swampyer nox
```

Execute a specific nox environment:

```bash
docker compose exec python_swampyer nox -e <env_name>
```

Note: a list of available environments can be found with:

```bash
docker compose exec python_swampyer nox --list-sessions
```

### Packaging

```
pdm build
pdm publish
```


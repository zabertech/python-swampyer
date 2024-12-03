# Swampyer

[[_TOC_]]

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

Development is mostly done from via the Zaber developer environment.

Further, most work is done within a docker container since we need to run the code against a slew of python versions to validate the code.

### Setup:

Setting up the environment can by:

```bash
git clone https://github.com/zabertech/python-swampyer.git
cd python-swampyer
docker compose up -d
```

### Testing

Nox is used to automate the testing between the various python versions.

By default when the docker compose is started the system will initiate a nox run running the test suite against the range of python versions we support.

However, if you wish to run or develop within the environment, change the `docker-compose.yml` to have a command of `sleep infinity` and the container will remember active for ad-hoc execution of the test suite.

```bash
docker compose exec python-swampyer nox
```

Execute a specific nox environment:

```bash
docker compose exec python-swampyer nox -e <env_name>
```

Note: a list of available environments can be found with:

```bash
docker compose exec python-swampyer nox --list-sessions
```

### Packaging

```
pdm build
pdm publish
```


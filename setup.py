#!/usr/bin/python

from setuptools import setup, find_packages

setup(name='swampyer',
      version='2.20200817',
      description='Simple WAMP library with minimal external dependencies',
      url = 'https://github.com/zabertech/python-swampyer',
      download_url = 'https://github.com/zabertech/python-swampyer/archive/1.20200709.tar.gz',
      author='Aki Mimoto',
      author_email='aki+swampyer@zaber.com',
      license='MIT',
      packages=['swampyer'],
      scripts=[],
      test_suite='tests',
      extras_requires={
          'dev': ["crossbar"],
          'cbor': ["cbor"],
          'msgpack': ["msgpack"],
          'all': ["cbor","msgpack"],
      },
      install_requires=[
          'websocket-client',
          'certifi',
          'six',
          'setuptools',
      ],
      dependency_links=[],
      zip_safe=False)


#!/usr/bin/python

from setuptools import setup, find_packages

setup(name='swampyer',
      version='1.20190717',
      description='Simple WAMP library with minimal external dependencies',
      url = 'https://github.com/zabertech/python-swampyer',
      download_url = 'https://github.com/zabertech/python-swampyer/archive/1.20190716.tar.gz',
      author='Aki Mimoto',
      author_email='aki+swampyer@zaber.com',
      license='MIT',
      packages=['swampyer'],
      scripts=[],
      test_suite='tests',
      extras_requires={
          'dev': ["crossbar"],
      },
      install_requires=[
          'websocket-client',
          'six',
          'setuptools',
      ],
      dependency_links=[],
      zip_safe=False)


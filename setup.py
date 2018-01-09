#!/usr/bin/python

from setuptools import setup, find_packages

setup(name='swampyer',
      version='1.00',
      description='Simple WAMP ',
      url='',
      author='Aki Mimoto',
      author_email='aki+izaber@zaber.com',
      license='MIT',
      packages=['swampyer'],
      scripts=[],
      test_suite='tests',
      install_requires=[
          'certifi',
          'websocket-client',
          'six',
      ],
      dependency_links=[],
      zip_safe=False)


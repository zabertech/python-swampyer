#!/usr/bin/python

from setuptools import setup

setup(name='swampyer',
      version='1.00',
      description='Simple WAMP ',
      url='',
      author='Aki Mimoto',
      author_email='aki+izaber@zaber.com',
      license='MIT',
      packages=['swampyer'],
      scripts=[],
      install_requires=[
          'certifi',
          'websocket-client',
          'six',
      ],
      dependency_links=[],
      zip_safe=False)


#!/usr/bin/env python

import re
from setuptools import setup
from distutils.cmd import Command
import shutil
import os

_version = re.search(r'__version__\s+=\s+\'(.*)\'',
                     open('ingenialink/__init__.py').read()).group(1)

class BDistAppCommand(Command):
    """ Custom command to build the application. """

    description = 'Build the application'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print("Copying dlls...")
        shutil.copy('resources/Packet.dll', 'ingenialink/')
        shutil.copy('resources/wpcap.dll', 'ingenialink/')

class BCleanAppCommand(Command):
    """ Custom command to clean the application. """

    description = 'Clean the application'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print("Cleaning files...")
        if os.path.exists("ingenialink/Packet.dll"):
            os.remove("ingenialink/Packet.dll")
        if os.path.exists("ingenialink/wpcap.dll"):
            os.remove("ingenialink/wpcap.dll")

setup(name='ingenialink',
      version=_version,
      packages=['ingenialink', 'ingenialink.canopen'],
      description='IngeniaLink Communications Library',
      long_description=open('README.rst').read(),
      author='Ingenia Motion Control',
      author_email='support@ingeniamc.com',
      url='https://www.ingeniamc.com',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: POSIX :: Linux',
          'Operating System :: MacOS',
          'Operating System :: Microsoft :: Windows',
          'Programming Language :: C',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Topic :: Communications',
          'Topic :: Software Development :: Libraries'
      ],
      cmdclass={
        'bdist_app': BDistAppCommand,
        'bclean_app': BCleanAppCommand
      },
      setup_requires=['cffi==1.12.2'],
      cffi_modules=['ingenialink/ingenialink_build.py:ffibuilder'],
      install_requires=[
          'cffi==1.12.2',
          'numpy<=1.19.5',
          'canopen>=1.0.0',
          'ingenialogger>=0.1.0'
      ],
      include_package_data = True

      )

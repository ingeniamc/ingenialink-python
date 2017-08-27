#!/usr/bin/env python

from setuptools import setup


setup(name='ingenialink',
      version='0.9.9',
      packages=['ingenialink'],
      description='IngeniaLink Communications Library',
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
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Topic :: Communications',
          'Topic :: Software Development :: Libraries'
      ],
      setup_requires=["cffi>=1.0.0"],
      cffi_modules=["ingenialink/ingenialink_build.py:ffibuilder"],
      install_requires=["cffi>=1.0.0"])

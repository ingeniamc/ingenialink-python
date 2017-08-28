==================
ingenialink-python
==================

.. image:: https://travis-ci.org/ingeniamc/ingenialink-python.svg?branch=master
    :target: https://travis-ci.org/ingeniamc/ingenialink-python
    :alt: Build Status

.. image:: https://ci.appveyor.com/api/projects/status/evmgqlo3r0i6fr1d?svg=true
    :target: https://ci.appveyor.com/project/gmarull/ingenialink-python
    :alt: Build Status

.. image:: https://readthedocs.org/projects/ingenialink/badge/?version=latest
    :target: http://ingenialink.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/v/ingenialink.svg
    :target: https://pypi.python.org/pypi/ingenialink
    :alt: PyPI Version

.. image:: https://api.codacy.com/project/badge/Grade/6bccc35bdbdb474c8fefa98f6c4a425e
    :target: https://www.codacy.com/app/gmarull/ingenialink-python
    :alt: Code Quality

This is a Python binding for the ingenialink_ C library. The binding is built as
a native Python extension thanks to cffi_ and then exposed through an
object-oriented API.

Python versions 2.7, >=3.4 are supported.

.. _ingenialink: https://github.com/ingeniamc/ingenialink
.. _cffi: https://cffi.readthedocs.io/en/latest/

Installation
------------

The recommended way to install is by using ``pip``, i.e::

    pip install ingenialink

Binary wheels are provided for most popular platforms and Python versions.

Documentation
-------------

For further details you can read the documentation_ where you will find
examples, the API docs, etc.

.. _documentation: https://ingenialink.readthedocs.io

==================
ingenialink-python
==================

.. image:: https://ci.appveyor.com/api/projects/status/evmgqlo3r0i6fr1d?svg=true
    :target: https://ci.appveyor.com/project/gmarull/ingenialink-python
    :alt: Build Status

.. image:: https://readthedocs.org/projects/ingenialink/badge/?version=latest
    :target: http://ingenialink.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/v/ingenialink.svg
    :target: https://pypi.python.org/pypi/ingenialink
    :alt: PyPI Version

This is a Python binding for the ingenialink_ C library. The binding is built as
a native Python extension thanks to cffi_ and then exposed through an
object-oriented API.

Only Python 3.x is currently supported.

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

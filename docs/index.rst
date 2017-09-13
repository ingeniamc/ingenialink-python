Welcome to ingenialink's documentation!
=======================================

This site covers the ``ingenialink`` package usage & API documentation. The
``ingenialink`` Python package is a binding for the ingenialink_ C library.  The
binding is built as a native Python extension thanks to cffi_ and it offers the
same functionality as the C library, which summarizes to:

* Basic motion control support
* Read and write axis registers
* Register polling
* Scan for axes in the network
* Network devices discovery and monitor

.. _ingenialink: https://github.com/ingeniamc/ingenialink
.. _cffi: https://cffi.readthedocs.io/en/latest/

Contents
--------

.. toctree::
    :maxdepth: 2

    examples
    api
    building

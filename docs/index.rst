Welcome to ingenialink's documentation!
=======================================

This site covers the ``ingenialink`` package usage & API documentation. The
``ingenialink`` Python package is a binding for the ingenialink_ C library.  The
binding is built as a native Python extension thanks to cffi_ and it offers the
same functionality as the C library, which summarizes to:

* Basic motion control support
* Read and write servo registers
* Support for dictionaries
* Register polling and monitoring
* Scan for servos on the network
* Network devices discovery and monitor

.. _ingenialink: https://github.com/ingeniamc/ingenialink
.. _cffi: https://cffi.readthedocs.io/en/latest/

Requirements
------------

* Python 3.6
* WinPcap_ 4.1.3

.. _WinPcap: https://www.winpcap.org/install/

Contents
--------

.. toctree::
    :maxdepth: 2

    api
    building
    examples
    changelog

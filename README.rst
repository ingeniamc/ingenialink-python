==================
ingenialink-python
==================

|tests| |pypi| |python_versions|

|license|

.. |tests| image:: https://img.shields.io/github/checks-status/ingeniamc/ingenialink-python/master?label=Tests
   :alt: GitHub branch status

.. |python_versions| image:: https://img.shields.io/pypi/pyversions/ingenialink?color=%2334D058
   :alt: PyPI - Python Version

.. |pypi| image:: https://img.shields.io/pypi/v/ingenialink.svg?color=%2334D058
    :target: https://pypi.python.org/pypi/ingenialink
    :alt: PyPI Version

.. |license| image:: https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg
   :alt: CC by-nc-nd
   :target: https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode

ingenialink-python is a Python library for simple motion control tasks and communication with Ingenia drives.

.. image:: https://github.com/ingeniamc/ingenialink-python/blob/master/docs/_static/images/main_image.png?raw=true
     :target: http://www.ingeniamc.com
     :alt: Ingenia Servodrives

Requirements
------------

* Python 3.9 or higher
* WinPcap_ 4.1.3

.. _WinPcap: https://www.winpcap.org/install/

Installation
------------

Installation is done by using ``pip``, i.e::

    pip install ingenialink




Documentation
-------------

For further details you can read the documentation_ where you will find
simple usage examples, the API docs, etc.

.. _documentation: https://distext.ingeniamc.com/doc/ingenialink-python/latest/


Virtual environment management with Poetry
==========================================

Install poetry::

    pip install poetry

Use an environment with a certain Python version::

    poetry env use 3.12

This command will start the poetry environment. If no Python environment exists, it will create one.

To switch to Python 3.9 environment::

    poetry env use 3.9


Project Tasks - Poe The Poet plugin
===================================

To run the tasks use ``poe``. For example, to run the format task::

    poetry poe format

Any extra CLI arguments will be appended. For example, to indicate a certain test for pytest::

    poetry poe tests -k test_servo_fixture.py

Build the module
================

Activate poetry environment and run the following::

    poetry poe build

Run tests
=========

Create *tests/setups/tests_setup.py* file with configuration file.

This file is ignored by git and won't be uploaded to the repository.
Example of a setup:


.. code-block:: python


   from pathlib import Path

   from summit_testing_framework.setups import LocalDriveConfigSpecifier

   DEN_NET_E_SETUP = LocalDriveConfigSpecifier.from_ethercat_configuration(
      identifier="den-net-e",
      dictionary=Path("C://Users//some.user//Downloads//den-net-e_eoe_2.7.3.xdf"),
      config_file=Path("C://Users//some.user//Downloads//den_net_e.xcf"),
      firmware_file=Path("C://Users//some.user//Downloads//den-net-e_2.7.3.lfu"),
      ifname="\\Device\\NPF_{675921D7-B64A-4997-9211-D18E2A6DC96A}",
      slave=1,
      boot_in_app=False,
   )


For more information, check *summit-testing-framework* documentation.

Run tests selecting the markers that you want and are appropriate for your setup.
Beware that some tests may not be appropiate for the setup that you have and may fail.

Run the tests::

    poetry poe tests


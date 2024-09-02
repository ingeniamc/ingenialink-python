==================
ingenialink-python
==================

.. |tests| |pypi| |python_versions| #TODO INGK-969: Include test badge once master branch jobs are passing.
|pypi| |python_versions|

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

Development
^^^^^^^^^^^

In case that library will be use from source code the FoE application will be missing.
It must be added to ``ingenialink/bin/FoE/win_64x`` in order to use FOE feature.

Installation
------------

Installation is done by using ``pip``, i.e::

    pip install ingenialink




Documentation
-------------

For further details you can read the documentation_ where you will find
simple usage examples, the API docs, etc.

.. _documentation: https://distext.ingeniamc.com/doc/ingenialink-python/latest/

Building from source
====================

In case you need to run the package on a system for which no binary wheels are
provided, you will need to build the package from source. In order to do so, the
following packages need to be installed on your system:

* C compiler (the one used by your Python version)
* Git
* CMake (>= 3.0)
* Python development package (``python-dev``)
* ``udev`` development package (``libudev-dev``) on Linux

Then, simply use the ``setup.py`` as usual::

        python setup.py install

If you run into problems related with CFFI, please, read the official
`installation guide <http://cffi.readthedocs.io/en/latest/installation.html>`_.

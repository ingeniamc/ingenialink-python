Building from source
====================

In case you need to run the package on a system for which no binary wheels are
provided, you will need to build the package from source. In order to do so, the
following packages need to be installed on your system:

* C compiler (the one used by your Python version)
* Git
* CMake (>= 3.0)
* libffi development package (see `this`_)
* Python development package
* ``libxml2``
* ``udev`` development package (``libudev-dev``) on Linux

Then, simply use the ``setup.py`` to build as usual::

        python setup.py build

and to install::

        python setup.py install

.. _this: http://cffi.readthedocs.io/en/latest/installation.html

Developers
----------

The builder script will automatically clone the underlying C libraries from
their respective Git repos. However, when you are changing the C libraries you
will likely not want that behavior. For this reason, you can *tell* to the
building script the location of the libraries by setting the ``SOEM_DIR``,
``XML2_DIR`` and ``INGENIALINK_DIR`` environment variables. Furthermore, you can
also make a build by directly calling the build script::

        # use your local ingenialink C library
        export INGENIALINK_DIR=/path/to/your/local/ingenialink
        # manually trigger the build (outputs to ingenialink/)
        python ingenialink/ingenialink_build.py

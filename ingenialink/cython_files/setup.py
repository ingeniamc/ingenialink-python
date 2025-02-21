from Cython.Build import cythonize
from setuptools import Extension, setup

extensions = [
    Extension(
        "get_adapters_addresses",
        ["get_adapters_addresses.pyx"],
        language="c++",
        extra_compile_args=["/TP"],
        libraries=["Iphlpapi"],
    )
]

setup(
    name="CyGetAdaptersAddresses",
    ext_modules=cythonize(extensions, compiler_directives={"language_level": "3"}),
)

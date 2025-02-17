import platform
import re

import setuptools
from setuptools.command.build_ext import build_ext as _build_ext
from setuptools.command.sdist import sdist as _sdist

_version = re.search(r"__version__\s+=\s+\"(.*)\"", open("ingenialink/__init__.py").read()).group(1)


def get_docs_url():
    return f"https://distext.ingeniamc.com/doc/ingenialink-python/{_version}"


if platform.system() == "Windows":
    extensions = [
        setuptools.Extension(
            "ingenialink.get_adapters_addresses",
            ["ingenialink/cython_files/get_adapters_addresses.pyx"],
            language="c++",  # source code should be treated as C++
            extra_compile_args=[
                "/TP"
            ],  # treat all files as C++: https://learn.microsoft.com/en-us/cpp/build/reference/tc-tp-tc-tp-specify-source-file-type?view=msvc-170
            libraries=["Iphlpapi"],
        )
    ]
else:
    extensions = []


class BuildExtCommand(_build_ext):
    """Cythonize cython modules."""

    def initialize_options(self):
        """Set default options."""
        super().initialize_options()
        self.inplace = 1

    def run(self):
        """Cythonize the extensions."""
        # Ensure cythonize is run before building extensions
        from Cython.Build import cythonize

        # embedsignature: https://github.com/cython/cython/wiki/enhancements-compilerdirectives
        cythonize(extensions, compiler_directives={"language_level": "3", "embedsignature": True})
        super().run()


class CustomSdistCommand(_sdist):
    """Ensure that cython modules are cythonized before running sdist."""

    def run(self):
        """Cythonize the extensions before running sdist."""
        self.run_command("build_ext")
        super().run()


setuptools.setup(
    name="ingenialink",
    version=_version,
    packages=setuptools.find_packages(exclude=["tests*", "examples*"]),
    include_package_data=True,
    package_data={
        "ingenialink": ["py.typed"],
        "virtual_drive": ["py.typed", "resources/*"],
    },
    description="IngeniaLink Communications Library",
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    author="Novanta",
    author_email="support@ingeniamc.com",
    url="https://www.ingeniamc.com",
    project_urls={
        "Documentation": get_docs_url(),
        "Source": "https://github.com/ingeniamc/ingenialink-python",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Cython",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries",
    ],
    install_requires=[
        "canopen==2.2.0",
        "python-can==4.4.2",
        "ingenialogger>=0.2.1",
        "ping3==4.0.3",
        "pysoem>=1.1.10, <1.2.0",
        "numpy>=1.26.0",
        "scipy==1.12.0",
        "bitarray==2.9.2",
        "multiping==1.1.2",
    ],
    extras_require={
        "dev": ["tox==4.12.1"],
    },
    setup_requires=["cython==3.0.11"],
    python_requires=">=3.9",
    ext_modules=extensions,
    cmdclass={
        "build_ext": BuildExtCommand,
        "sdist": CustomSdistCommand,
    },
)

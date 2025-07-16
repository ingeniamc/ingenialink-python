import platform
import re
from Cython.Build import cythonize
import setuptools

_version = re.search(r"__version__\s+=\s+\"(.*)\"", open("ingenialink/__init__.py").read()).group(1)


def get_docs_url():
    return f"https://distext.ingeniamc.com/doc/ingenialink-python/{_version}"

ext_modules = []

if platform.system() == "Windows":
    ext_modules.append(
        setuptools.Extension(
            "ingenialink.get_adapters_addresses",
            ["ingenialink/cython_files/get_adapters_addresses.pyx"],
            language="c++",  # source code should be treated as C++
            extra_compile_args=[
                "/TP"
            ],  # treat all files as C++: https://learn.microsoft.com/en-us/cpp/build/reference/tc-tp-tc-tp-specify-source-file-type?view=msvc-170
            libraries=["Iphlpapi"],
        )
    )

setuptools.setup(
    url="https://www.ingeniamc.com",
    project_urls={
        "Documentation": get_docs_url(),
        "Source": "https://github.com/ingeniamc/ingenialink-python",
    },
    ext_modules=cythonize(ext_modules, compiler_directives={'language_level': "3"}),
)

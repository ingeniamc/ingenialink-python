import re

import setuptools

_version = re.search(r"__version__\s+=\s+\"(.*)\"", open("ingenialink/__init__.py").read()).group(1)


def get_docs_url():
    return f"https://distext.ingeniamc.com/doc/ingenialink-python/{_version}"


setuptools.setup(
    name="ingenialink",
    version=_version,
    packages=setuptools.find_packages(exclude=["tests*", "examples*"]),
    include_package_data=True,
    package_data={
        "ingenialink": ["bin/FoE/*/*", "py.typed"],
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
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries",
    ],
    install_requires=[
        "canopen==2.2.0",
        "python-can==4.4.2",
        "ingenialogger>=0.2.1",
        "ping3==4.0.3",
        "pysoem>=1.1.7, <1.2.0",
        "numpy>=1.26.0",
        "scipy==1.12.0",
        "bitarray==2.9.2",
    ],
    extras_require={
        "dev": ["tox==4.12.1"],
    },
    python_requires=">=3.9",
)

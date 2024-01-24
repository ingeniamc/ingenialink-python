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
    author="Ingenia Motion Control",
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
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries",
    ],
    install_requires=[
        "canopen==1.2.1",
        "python-can==3.3.4",
        "ingenialogger>=0.2.1",
        "ping3==4.0.3",
        "pysoem==1.0.7",
        "numpy==1.19.5",
        "scipy==1.5.4",
    ],
    extras_require={
        "dev": ["tox==4.12.1"],
    },
)

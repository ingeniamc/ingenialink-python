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
        "dataclasses==0.6",
    ],
    extras_require={
        "dev": [
            "sphinx==3.5.4",
            "sphinx-rtd-theme==1.0.0",
            "sphinxcontrib-bibtex==2.4.1",
            "nbsphinx==0.8.6",
            "pytest==6.2.4",
            "pytest-cov==2.12.1",
            "pytest-mock==3.6.1",
            "jinja2==3.0.3",
            "pycodestyle==2.6.0",
            "wheel==0.37.1",
            "m2r2==0.3.2",
            "mypy==0.971",
        ],
    },
)

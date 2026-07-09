import sys
from os.path import abspath, join, dirname
from datetime import datetime
import os

from ingenialink import __version__


sys.path.insert(0, os.path.abspath('..'))

# options
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest',
              'sphinx.ext.coverage', 'sphinx.ext.viewcode',
              'sphinx.ext.napoleon', 'myst_parser',
              ]

project = 'ingenialink'
version = __version__
release = version
author = 'Novanta'
year = datetime.now().year
copyright = '{}, Novanta Technologies Spain S.L.'.format(year)
source_suffix = '.rst'
master_doc = 'index'


exclude_patterns = [
    'architecture/**',
]

pygments_style = 'sphinx'

# html
html_static_path = ['_static']
html_theme = 'sphinx_rtd_theme'


def setup(app):
    app.add_css_file('css/custom.css')


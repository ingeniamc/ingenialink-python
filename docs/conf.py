import sys
from os.path import abspath, join, dirname
from datetime import datetime
import os

from ingenialink import __version__

# try:
#     from unittest.mock import MagicMock
# except ImportError:
#     from mock import Mock as MagicMock


sys.path.insert(0, os.path.abspath('..'))

# options
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest',
              'sphinx.ext.coverage', 'sphinx.ext.viewcode',
              'sphinx.ext.napoleon', 'm2r2']

project = 'ingenialink'
version = __version__
release = version
author = 'Novanta'
year = datetime.now().year
copyright = '{}, Novanta Technologies Spain S.L.'.format(year)
source_suffix = '.rst'
master_doc = 'index'

pygments_style = 'sphinx'

# html
html_static_path = ['_static']
html_theme = 'sphinx_rtd_theme'


def setup(app):
    app.add_css_file('css/custom.css')

# others
# pygments_style = 'sphinx'
# autodoc_mock_imports = ['ingenialink', 'numpy']
# exclude_patterns = ['_build', '**.ipynb_checkpoints']
#
# class Mock(MagicMock):
#     @classmethod
#     def __getattr__(cls, name):
#             return MagicMock()
#
#
# MOCK_MODULES = ['ingenialink._ingenialink']
# sys.modules.update((mod_name, Mock()) for mod_name in MOCK_MODULES)

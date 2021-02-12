import sys
import re
from os.path import abspath, join, dirname
from datetime import datetime

try:
    from unittest.mock import MagicMock
except ImportError:
    from mock import Mock as MagicMock


sys.path.append(abspath(join(dirname(__file__), '..')))


# options
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest',
              'sphinx.ext.coverage', 'sphinx.ext.viewcode']

_version = re.search(r'__version__\s+=\s+\'(.*)\'',
                     open('../ingenialink/__init__.py').read()).group(1)

project = 'ingenialink'
version = _version
author = 'Ingenia Motion Control'
year = datetime.now().year
copyright = '{}, Ingenia-CAT S.L.'.format(year)
source_suffix = '.rst'
master_doc = 'index'

pygments_style = 'sphinx'

# html
html_static_path = ['_static']
html_theme = 'sphinx_rtd_theme'
html_logo = '_static/images/logo.svg'
html_theme_options = {
    'logo_only': True,
    'display_version': False,
}


def setup(app):
    app.add_stylesheet('css/custom.css')

# others
pygments_style = 'sphinx'
autodoc_mock_imports = ['ingenialink', 'numpy']
exclude_patterns = ['_build', '**.ipynb_checkpoints']

class Mock(MagicMock):
    @classmethod
    def __getattr__(cls, name):
            return MagicMock()


MOCK_MODULES = ['ingenialink._ingenialink']
sys.modules.update((mod_name, Mock()) for mod_name in MOCK_MODULES)

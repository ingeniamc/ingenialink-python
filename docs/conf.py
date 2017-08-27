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
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon']

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


# mocks
class Mock(MagicMock):
    @classmethod
    def __getattr__(cls, name):
            return MagicMock()


MOCK_MODULES = ['ingenialink._ingenialink']
sys.modules.update((mod_name, Mock()) for mod_name in MOCK_MODULES)

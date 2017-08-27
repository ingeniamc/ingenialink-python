import sys
import re
from os.path import abspath, join, dirname
from datetime import datetime

sys.path.append(abspath(join(dirname(__file__), '..')))

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
autodoc_mock_imports = ['ingenialink._ingenialink']

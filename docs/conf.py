import sys
from os.path import abspath, join, dirname
from datetime import datetime

sys.path.append(abspath(join(dirname(__file__), '..')))

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon']

project = 'ingenialink'
version = '0.9.9'
author = 'Ingenia Motion Control'
year = datetime.now().year
copyright = '{}, Ingenia-CAT S.L.'.format(year)
source_suffix = '.rst'
master_doc = 'index'

pygments_style = 'sphinx'
autodoc_mock_imports = ['ingenialink._ingenialink']

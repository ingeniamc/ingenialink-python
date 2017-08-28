import sys
import re
from os.path import join, exists
from distutils.spawn import find_executable
from subprocess import check_call

from cffi import FFI


_SRC_DIR = '_deps'
_BUILD_DIR = '_build'
_INSTALL_DIR = '_install'

_INC_DIR = join(_INSTALL_DIR, 'include')
_LIB_DIR = join(_INSTALL_DIR, 'lib')

_SER_URL = 'https://github.com/ingeniamc/sercomm'
_SER_VER = '1.3.0'
_SER_SRC = join(_SRC_DIR, 'sercomm')
_SER_BUILD = join(_BUILD_DIR, 'sercomm')

_IL_URL = 'https://github.com/ingeniamc/ingenialink'
_IL_VER = '1.0.0'
_IL_SRC = join(_SRC_DIR, 'ingenialink')
_IL_BUILD = join(_BUILD_DIR, 'ingenialink')

if sys.platform == 'win32':
    if sys.version_info >= (3, 5):
        _CMAKE_GENERATOR = 'Visual Studio 14 2015'
    elif sys.version_info >= (3, 3):
        _CMAKE_GENERATOR = 'Visual Studio 10 2010'
    elif sys.version_info >= (2, 7):
        _CMAKE_GENERATOR = 'Visual Studio 9 2008'
    else:
        raise ImportError('Unsupported Python version')

    if sys.maxsize > 2**32:
        _CMAKE_GENERATOR += ' Win64'
else:
    _CMAKE_GENERATOR = 'Unix Makefiles'


def _build_deps():
    """ Obtain and build dependencies (sercomm and ingenialink). """

    # check for Git & CMake
    git = find_executable('git')
    if not git:
        raise FileNotFoundError('Git is not installed or in PATH')

    cmake = find_executable('cmake')
    if not cmake:
        raise FileNotFoundError('CMake is not installed or in PATH')

    # clone, build and install (locally) libsercomm
    if not exists(_SER_SRC):
        check_call([git, 'clone', '-b', _SER_VER, _SER_URL, _SER_SRC])

    check_call([cmake, '-H' + _SER_SRC, '-B' + _SER_BUILD,
                '-G', _CMAKE_GENERATOR,
                '-DCMAKE_BUILD_TYPE=Release',
                '-DCMAKE_INSTALL_PREFIX=' + _INSTALL_DIR,
                '-DBUILD_SHARED_LIBS=OFF', '-DWITH_PIC=ON'])
    check_call([cmake, '--build', _SER_BUILD, '--config', 'Release',
                '--target', 'install'])

    # clone, build and install (locally) libingenialink
    if not exists(_IL_SRC):
        check_call([git, 'clone', '-b', _IL_VER, _IL_URL, _IL_SRC])

    check_call([cmake, '-H' + _IL_SRC, '-B' + _IL_BUILD,
                '-G', _CMAKE_GENERATOR,
                '-DCMAKE_BUILD_TYPE=Release',
                '-DCMAKE_INSTALL_PREFIX=' + _INSTALL_DIR,
                '-DBUILD_SHARED_LIBS=OFF', '-DWITH_PIC=ON'])
    check_call([cmake, '--build', _IL_BUILD, '--config', 'Release',
                '--target', 'install'])


def _gen_cffi_header():
    """ Generate cffi header.

        All ingenialink headers are joined into a single one, and, all
        cffi non-compatibe portions removed.

        Returns:
            str: cffi header.
    """

    remove = ['IL_EXPORT',
              'IL_BEGIN_DECL',
              'IL_END_DECL',
              '#ifdef.*',
              '#ifndef.*',
              '#endif.*',
              '#define.+H_',
              '#include.*',
              '.+foreach.+\n.*']

    headers = [join(_INC_DIR, 'ingenialink', 'err.h'),
               join(_INC_DIR, 'ingenialink', 'net.h'),
               join(_INC_DIR, 'ingenialink', 'node.h'),
               join(_INC_DIR, 'ingenialink', 'version.h')]

    h_stripped = ''

    for header in headers:
        with open(header) as h:
            h_stripped += re.sub('|'.join(remove), '', h.read())

    return h_stripped


def _get_libs():
    """ Ontain the list of libraries to link against based on platform.

        Returns:
            list: List of libraries.
    """

    libs = ['ingenialink', 'sercomm']

    if sys.platform.startswith('linux'):
        libs.extend(['udev'])
    elif sys.platform == 'win32':
        libs.extend(['user32', 'setupapi', 'advapi32'])

    return libs


# build dependencies first
_build_deps()

# cffi builder
ffibuilder = FFI()

ffibuilder.cdef(
    _gen_cffi_header() + '''
    /* callbacks */
    extern "Python" void _on_found_cb(void *ctx, uint8_t node_id);
    extern "Python" void _on_evt_cb(void *ctx, il_net_dev_evt_t on_evt,
                                    const char *port);
''')

ffibuilder.set_source('ingenialink._ingenialink',
                      r'#include <ingenialink/ingenialink.h>',
                      include_dirs=[_INC_DIR],
                      library_dirs=[_LIB_DIR],
                      libraries=_get_libs())


if __name__ == '__main__':
    ffibuilder.compile(verbose=True)

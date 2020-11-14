import argparse
import os


def _get_version():
    '''
    Read the current version from the version file to show in
    the help section.
    '''
    about = {}
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, '__version__.py')) as f:
        exec(f.read(), about)
    return about['__version__']


def prepare_args_parser():
    '''
    Construct and return the argument parser object.
    '''
    description = 'DirectSync: An efficient and easy-to-use utility to'
    description += ' compare/synchronize/mirror folder contents.\n'
    description += 'Version ' + str(_get_version()) + '\n'
    epilog = 'Copyright (c) 2019 Anmol Singh Jaggi'
    epilog += '\nhttps://anmol-singh-jaggi.github.io'
    epilog += '\nMIT License'
    parser = argparse.ArgumentParser(
        description=description,
        prog='directsync',
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'src-path', help='The path of the source directory.')
    parser.add_argument(
        'dst-path', help='The path of the destination directory.')
    parser.add_argument(
        '-add',
        '--add-missing',
        action='store_true',
        help='Copy files from source which are absent in destination.')
    parser.add_argument(
        '-rm',
        '--remove-extra',
        action='store_true',
        help='Remove the files from destination which are absent in source.')
    parser.add_argument(
        '-ovr',
        '--overwrite-content',
        action='store_true',
        help='Overwrite the files having same name but different content.')
    parser.add_argument(
        '-mirr',
        '--mirror-contents',
        action='store_true',
        help='Make the destination directory exactly same as the source.\
            Shorthand for `-add -rm -ovr`.')
    parser.add_argument(
        '-trash',
        '--use-trash',
        action='store_true',
        help='Send to trash/recycle bin while deleting/overwriting.')
    parser.add_argument(
        '-cache',
        '--use-cache',
        action='store_true',
        help='Whether to use previously cached comparison-check result from\
            disk.')
    parser.add_argument(
        '-latest',
        '--preserve-latest',
        action='store_true',
        help='Whether to use the last modified time while comparing files\
              with different content.')
    parser.add_argument(
        '-dry',
        '--dry-run',
        action='store_true',
        help='Just simulate and report the file operations that will be\
              performed with the current configuration.')
    parser.add_argument(
        '-no-bar',
        '--hide-progress-bar',
        action='store_true',
        help='Whether to hide the progress bar or not. \
            Will result in a huge speedup iff the 2 directories \
            are structured very differently.')
    args = parser.parse_args()
    args = vars(args)
    return args

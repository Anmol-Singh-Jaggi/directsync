# fsync

[![PyPI version](https://badge.fury.io/py/fsync.svg)](https://badge.fury.io/py/fsync)
![MIT License](https://img.shields.io/badge/license-MIT-green.svg)

An efficient and easy-to-use utility to compare/synchronize/mirror folder contents.

**Usage:**

    fsync [-h] [-no-bar] [-add] [-rm] [-ovr] [-rev] [-mirr]
                left-path right-path

    positional arguments:
    left-path             The path of the left(source) directory.
    right-path            The path of the right(destination) directory.

    optional arguments:
    -h, --help            show this help message and exit
    -add, --add-missing   Copy files from source which are absent in
                        destination.
    -rm, --remove-extra   Remove the files from destination which are absent in
                        source.
    -ovr, --overwrite-content
                        Overwrite the files having same name but different
                        content.
    -rev, --reverse-sync-direction
                        Use the right folder as source and the left as
                        destination.
    -mirr, --mirror-contents
                        Make the destination directory exactly same as the
                        source. Shorthand for `-add -rm -ovr`.
    -no-bar, --hide-progress-bar
                        Whether to hide the progress bar or not. Will result
                        in a huge speedup iff the 2 directories are structured
                        very differently.

**Installation:**
 - `pip install fsync`

**ToDo:**
 - Add `preserve-latest` option: Among the 2 files, the one with the latest modification date should be preserved.
 - Add `quiet` option.
 - Add `simulate` option.
 - Add `cache` option to cache the results of the previous difference check. Will need to serialize data to file.
 - Give more fine-tuned control of file comparison algorithm to the user.
 - Add `ignore-pattern` option to let the user ignore certain files based on the regex pattern provided.
 - Add tests.
 - Add code coverage.
 - Handle nested structures with symlinks.
 - Provide direct interface with online storage services.


Copyright (c) 2019 Anmol Singh Jaggi  
https://anmol-singh-jaggi.github.io  
MIT License
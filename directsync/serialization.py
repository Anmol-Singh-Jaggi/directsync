import pickle
import tempfile
from pathlib import Path
import hashlib


def serialize_directsync(dirsync):
    filepath = get_serialization_filepath(dirsync)
    with open(filepath, 'wb') as serial_file:
        pickle.dump(dirsync, serial_file, protocol=-1)


def deserialize_directsync(dirsync):
    filepath = get_serialization_filepath(dirsync)
    with open(filepath, 'rb') as serial_file:
        return pickle.load(serial_file)


def get_serialization_filepath(dirsync):
    '''
    Make a file in `$TEMP/directsync/` with the name being
    a union of the two directory names and their hashes.
    The directory names are included to make them easier to
    identify manually, otherwise just the hash would have been
    enough.
    '''
    left_path = dirsync.dirs_data.data_left.path.resolve()
    right_path = dirsync.dirs_data.data_right.path.resolve()
    filename = str(left_path) + '&&' + str(right_path)
    filename = hashlib.sha1(filename.encode()).hexdigest() + '.pickle'
    filename = left_path.stem + '_' + right_path.stem + '_' + filename
    tmp_dir = Path(tempfile.gettempdir())
    tmp_dir = tmp_dir / 'directsync'
    tmp_dir.mkdir(exist_ok=True)
    filepath = tmp_dir / filename
    return filepath

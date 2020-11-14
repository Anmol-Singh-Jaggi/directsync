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
    src_path = dirsync.dirs_data.data_src.path.resolve()
    dst_path = dirsync.dirs_data.data_dst.path.resolve()
    filename = str(src_path) + '&&' + str(dst_path)
    filename = hashlib.sha1(filename.encode()).hexdigest() + '.pickle'
    filename = src_path.stem + '_' + dst_path.stem + '_' + filename
    tmp_dir = Path(tempfile.gettempdir())
    tmp_dir = tmp_dir / 'directsync'
    tmp_dir.mkdir(exist_ok=True)
    filepath = tmp_dir / filename
    return filepath

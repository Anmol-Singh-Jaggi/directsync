from binaryornot.check import is_binary


def _is_file_text_test1(file_path):
    '''
    Try to read the first few bytes in text mode.
    '''
    try:
        with open(file_path, "r") as f:
            f.read(1024)
        return True
    except UnicodeDecodeError:
        return False


def _is_file_text_test2(file_path):
    '''
    Try to read first few lines in text mode.
    '''
    try:
        with open(file_path, "r") as f:
            num_lines = 0
            for l in f:
                num_lines += 1
                if (num_lines == 5):
                    break
        return True
    except UnicodeDecodeError:
        return False


def _is_file_text_test3(file_path):
    return not is_binary(str(file_path.resolve()))


def is_file_text(file_path):
    return _is_file_text_test1(file_path) and\
           _is_file_text_test2(file_path) and\
           _is_file_text_test3(file_path)


def compare_file_contents_buffered(path1, path2, buffer_size=100000):
    '''
    Compare file contents byte-to-byte.
    '''
    with open(path1, 'rb') as fp1, open(path2, 'rb') as fp2:
        while True:
            path1_bytes = fp1.read(buffer_size)
            path2_bytes = fp2.read(buffer_size)
            if path1_bytes != path2_bytes:
                return False
            if not path1_bytes:
                return True


def is_src_file_bigger(path_src, path_dst):
    src_size = path_src.stat().st_size
    dst_size = path_dst.stat().st_size
    return src_size > dst_size
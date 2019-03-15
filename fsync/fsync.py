import argparse
import hashlib
import pathlib

from tqdm import tqdm


class DirData:
    def __init__(self, path):
        self.path = path
        self.diff = []


class DirsData:
    def __init__(self, path_left, path_right):
        self.data_left = DirData(path_left)
        self.data_right = DirData(path_right)
        self.hash_diff = []


class FolderSync:
    def __init__(self, dir_path_left, dir_path_right, progressBar=False):
        self.dirs_data = DirsData(dir_path_left, dir_path_right)
        self.progressbar = progressBar
        if progressBar:
            self.progressbar = 'a'

    def _is_file_text(self, file_path):
        try:
            with open(file_path, "rt") as f:
                f.read(3)
            return True
        except UnicodeDecodeError:
            return False

    def _are_files_equal(self, path_left, path_right):
        # First check the file sizes.
        left_size = path_left.stat().st_size
        right_size = path_right.stat().st_size
        if left_size != right_size:
            return False
        if not self._is_file_text(path_left):
            if left_size > 1000000:
                return True
        contents = path_left.read_bytes()
        left_hash = hashlib.md5(contents).digest()
        contents = path_right.read_bytes()
        right_hash = hashlib.md5(contents).digest()
        return left_hash == right_hash

    def _compare_subfiles(self, left_dir_contents, right_dir_contents):
        left_files = [x for x in left_dir_contents if x.is_file()]
        right_files = [x for x in right_dir_contents if x.is_file()]

        left_iterator = 0
        right_iterator = 0

        while left_iterator < len(left_files) and right_iterator < len(
                right_files):
            self.mark_file_visit()
            left_entry = left_files[left_iterator]
            right_entry = right_files[right_iterator]
            left_entry_name = left_entry.name
            right_entry_name = right_entry.name
            if left_entry_name == right_entry_name:
                are_files_same = self._are_files_equal(left_entry, right_entry)
                if not are_files_same:
                    self.dirs_data.hash_diff.append((left_entry, right_entry))
                left_iterator += 1
                right_iterator += 1
                self.mark_file_visit()
            elif left_entry_name < right_entry_name:
                self.dirs_data.data_left.diff.append(left_entry)
                left_iterator += 1
            else:
                self.dirs_data.data_right.diff.append(right_entry)
                right_iterator += 1

        while left_iterator < len(left_files):
            left_entry = left_files[left_iterator]
            self.dirs_data.data_left.diff.append(left_entry)
            left_iterator += 1
            self.mark_file_visit()

        while right_iterator < len(right_files):
            right_entry = right_files[right_iterator]
            self.dirs_data.data_right.diff.append(right_entry)
            right_iterator += 1
            self.mark_file_visit()

    def _compare_subdirs(self, left_dir_contents, right_dir_contents):
        left_subdirs = [x for x in left_dir_contents if x.is_dir()]
        right_subdirs = [x for x in right_dir_contents if x.is_dir()]
        # Directories (subdirectories) to explore next.
        next_subdirs = []

        left_iterator = 0
        right_iterator = 0

        while left_iterator < len(left_subdirs) and right_iterator < len(
                right_subdirs):
            self.mark_file_visit()
            left_entry = left_subdirs[left_iterator]
            right_entry = right_subdirs[right_iterator]
            left_entry_name = left_entry.name
            right_entry_name = right_entry.name
            if left_entry_name == right_entry_name:
                next_subdirs.append((left_entry, right_entry))
                left_iterator += 1
                right_iterator += 1
                self.mark_file_visit()
            elif left_entry_name < right_entry_name:
                self.dirs_data.data_left.diff.append(left_entry)
                left_iterator += 1
            else:
                self.dirs_data.data_right.diff.append(right_entry)
                right_iterator += 1

        while left_iterator < len(left_subdirs):
            left_entry = left_subdirs[left_iterator]
            self.dirs_data.data_left.diff.append(left_entry)
            left_iterator += 1
            self.mark_file_visit()

        while right_iterator < len(right_subdirs):
            right_entry = right_subdirs[right_iterator]
            self.dirs_data.data_right.diff.append(right_entry)
            right_iterator += 1
            self.mark_file_visit()

        for dir_entry in next_subdirs:
            self._compare_dir_contents(dir_entry[0], dir_entry[1])

    def _compare_dir_contents(self, left_dir_path, right_dir_path):
        left_dir_contents = sorted([x for x in left_dir_path.iterdir()])
        right_dir_contents = sorted([x for x in right_dir_path.iterdir()])
        self._compare_subfiles(left_dir_contents, right_dir_contents)
        self._compare_subdirs(left_dir_contents, right_dir_contents)

    def check(self):
        '''
        Checks and stores the differences between the sides
        '''
        # TODO: Handle recursive structures.
        # TODO: Handle symlinks.
        # TODO: Improve documentation of the whole file.
        # TODO: Manage memory consumption for large directories
        # TODO: Handle dir does not exists!
        left_dir_path = pathlib.Path(self.dirs_data.data_left.path)
        right_dir_path = pathlib.Path(self.dirs_data.data_right.path)
        if self.progressbar:
            left_dir_generator = left_dir_path.rglob('*')
            left_dir_file_count_recursive = sum(1 for i in left_dir_generator)
            right_dir_generator = right_dir_path.rglob('*')
            right_dir_file_count_recursive = sum(
                1 for i in right_dir_generator)
            total_files_count = left_dir_file_count_recursive + right_dir_file_count_recursive
            self.progressbar = tqdm(total=total_files_count)
            self.files_visited = 0
        self._compare_dir_contents(left_dir_path, right_dir_path)
        if self.progressbar:
            self.progressbar.close()

    def add_to_right(self, add_diff_hash=False):
        '''
        Copy all files to right not present there.
        '''
        pass

    def add_to_left(self, add_diff_hash=False):
        '''
        Copy all files to left not present there.
        '''
        pass

    def delete_from_right(self, delete_diff_hash=False):
        '''
        Delete all files from right not present in left.
        '''
        pass

    def delete_from_left(self, delete_diff_hash=False):
        '''
        Delete all files from left not present in right.
        '''
        pass

    def sync_to_right(self):
        '''
        Make right dir exactly same as left dir.
        (will delete/add from/to the right dir as required)
        '''
        self.delete_from_right(True)
        self.add_to_right(True)

    def sync_to_left(self):
        '''
        Make left dir exactly same as right dir.
        (will delete/add from/to the left dir as required)
        '''
        self.delete_from_left(True)
        self.add_to_left(True)

    def mark_file_visit(self):
        if not self.progressbar:
            return
        self.files_visited += 1
        self.progressbar.update(1)

    def get_report(self):
        report_string = 'Comparison report:\n'
        report_string += '\n' + 'x' * 15 + '\n'
        report_string += 'Hashes different: (' + str(
            len(self.dirs_data.hash_diff)) + ')\n'
        for entry in self.dirs_data.hash_diff:
            report_string += '- ' + str(entry[0].relative_to(
                self.dirs_data.data_left.path)) + '\n'
        report_string += '-' * 15
        report_string += '\n\n' + '[' * 15 + '\n'
        report_string += 'Extra in left: (' + str(
            len(self.dirs_data.data_left.diff)) + ')\n'
        for entry in self.dirs_data.data_left.diff:
            report_string += '- ' + str(
                entry.relative_to(self.dirs_data.data_left.path)) + '\n'
        report_string += '-' * 15
        report_string += '\n\n' + ']' * 15 + '\n'
        report_string += 'Extra in right: (' + str(
            len(self.dirs_data.data_right.diff)) + ')\n'
        for entry in self.dirs_data.data_right.diff:
            report_string += '- ' + str(
                entry.relative_to(self.dirs_data.data_right.path)) + '\n'
        report_string += '-' * 15
        report_string += '\n\nThank you for using!\n'
        return report_string


def prepare_args_parser():
    description = 'FolderSync: A simple utility to compare/sync the contents of folders.\n'
    epilog = 'Copyright 2019 Anmol Singh Jaggi (https://anmol-singh-jaggi.github.io)\n'
    parser = argparse.ArgumentParser(
        description=description, prog='FolderSync', epilog=epilog)
    parser.add_argument(
        'left-path', help='The path of the left/first directory.')
    parser.add_argument(
        'right-path', help='The path of the right/second directory.')
    parser.add_argument(
        '-no-pro',
        '--hide-progress-bar',
        action='store_true',
        help='Whether to hide the progress bar or not.')
    args = parser.parse_args(['D:/anmol', 'D:/anmol'])
    args = vars(args)
    return args


def main():
    args = prepare_args_parser()
    left_dir = args['left-path']
    right_dir = args['right-path']
    hide_progress_bar = args['hide_progress_bar']
    fdiff = FolderSync(left_dir, right_dir, progressBar=not hide_progress_bar)
    fdiff.check()
    print(fdiff.get_report())


if __name__ == "__main__":
    main()

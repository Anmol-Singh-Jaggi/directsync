from pathlib import Path
import shutil
import logging

from tqdm import tqdm
from send2trash import send2trash

from .file_comparison import is_file_text, compare_file_contents_buffered
from .args_parsing import prepare_args_parser
from .serialization import serialize_directsync, deserialize_directsync,\
                           get_serialization_filepath

logger = logging.getLogger(__file__)


class DirData:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.diff = []


class DirsData:
    def __init__(self, path_left, path_right):
        # The items present in left but absent in right.
        self.data_left = DirData(path_left)
        # The items present in right but absent in left.
        self.data_right = DirData(path_right)
        # The items present on either side but with different contents.
        self.content_diff = []


class DirectSync:
    def __init__(self, dir_path_left, dir_path_right, show_progress_bar=False):
        self.dirs_data = DirsData(dir_path_left, dir_path_right)
        self.show_progress_bar = show_progress_bar
        self.progress_bar = None
        if not self.dirs_data.data_left.path.is_dir():
            error_msg = 'Left path "{}" is not a valid directory!'
            error_msg = error_msg.format(self.dirs_data.data_left.path)
            raise Exception(error_msg)
        if not self.dirs_data.data_right.path.is_dir():
            error_msg = 'Right path "{}" is not a valid directory!'
            error_msg = error_msg.format(self.dirs_data.data_right.path)
            raise Exception(error_msg)

    def _are_files_equal(self, path_left, path_right):
        # First check the file sizes.
        left_size = path_left.stat().st_size
        right_size = path_right.stat().st_size
        if left_size != right_size:
            # If file sizes are different, then return straightaway!
            return False
        if not is_file_text(path_left):
            if is_file_text(path_right):
                return False
            if left_size > 1000000:
                # Assume huge binary files with the same size
                # have the same content for performance.
                return True
        # If file size is same, and the files are text/small binaries,
        # then compare their contents.
        return compare_file_contents_buffered(path_left, path_right)

    def __getstate__(self):
        '''
        Specify what attributes to serialize.
        Needed to tell pickle to ignore `self.progress_bar`
        as `tqdm()` objects cannot be serialized.
        '''
        def should_pickle(attr_key):
            return 'progress' not in attr_key

        return {k: v for k, v in self.__dict__.items() if should_pickle(k)}

    def _compare_subfiles(self, left_dir_contents, right_dir_contents):
        '''
        Compare the file items.
        '''
        left_files = [x for x in left_dir_contents if x.is_file()]
        right_files = [x for x in right_dir_contents if x.is_file()]

        # Use a merging sort of algorithm.
        # 1. Sort the 2 lists according to Path's inbuilt comparison predicate
        # 2. Have 2 pointers, one on either list.
        # 3. If the 2 pointed items have the same name, then compare contents.
        #    Else add the lower name entry to `extras` and advance its pointer.
        # 4. Repeat 3 until either of the pointers reach the end.
        # 5. Exhaust the 2 pointers and add all the pointed items to `extras`.
        left_iterator = 0
        right_iterator = 0

        while left_iterator < len(left_files) and right_iterator < len(
                right_files):
            self._mark_file_visit()
            left_entry = left_files[left_iterator]
            right_entry = right_files[right_iterator]
            left_entry_name = left_entry.name
            right_entry_name = right_entry.name
            if left_entry_name == right_entry_name:
                are_files_same = self._are_files_equal(left_entry, right_entry)
                if not are_files_same:
                    self.dirs_data.content_diff.append((left_entry,
                                                        right_entry))
                left_iterator += 1
                right_iterator += 1
                self._mark_file_visit()
            elif Path(left_entry_name) < Path(right_entry_name):
                self.dirs_data.data_left.diff.append(left_entry)
                left_iterator += 1
            else:
                self.dirs_data.data_right.diff.append(right_entry)
                right_iterator += 1

        while left_iterator < len(left_files):
            left_entry = left_files[left_iterator]
            self.dirs_data.data_left.diff.append(left_entry)
            left_iterator += 1
            self._mark_file_visit()

        while right_iterator < len(right_files):
            right_entry = right_files[right_iterator]
            self.dirs_data.data_right.diff.append(right_entry)
            right_iterator += 1
            self._mark_file_visit()

    def _compare_subdirs(self, left_dir_contents, right_dir_contents):
        '''
        Similar to `_compare_subfile()` but for directories.
        '''
        left_subdirs = [x for x in left_dir_contents if x.is_dir()]
        right_subdirs = [x for x in right_dir_contents if x.is_dir()]
        # Directories (subdirectories) to explore next.
        next_subdirs = []

        left_iterator = 0
        right_iterator = 0

        while left_iterator < len(left_subdirs) and right_iterator < len(
                right_subdirs):
            self._mark_file_visit()
            left_entry = left_subdirs[left_iterator]
            right_entry = right_subdirs[right_iterator]
            left_entry_name = left_entry.name
            right_entry_name = right_entry.name
            if left_entry_name == right_entry_name:
                next_subdirs.append((left_entry, right_entry))
                left_iterator += 1
                right_iterator += 1
                self._mark_file_visit()
            elif Path(left_entry_name) < Path(right_entry_name):
                self.dirs_data.data_left.diff.append(left_entry)
                left_iterator += 1
            else:
                self.dirs_data.data_right.diff.append(right_entry)
                right_iterator += 1

        while left_iterator < len(left_subdirs):
            left_entry = left_subdirs[left_iterator]
            self.dirs_data.data_left.diff.append(left_entry)
            left_iterator += 1
            self._mark_file_visit()

        while right_iterator < len(right_subdirs):
            right_entry = right_subdirs[right_iterator]
            self.dirs_data.data_right.diff.append(right_entry)
            right_iterator += 1
            self._mark_file_visit()

        for dir_entry in next_subdirs:
            # Recursive call
            self._compare_dir_contents(dir_entry[0], dir_entry[1])

    def _compare_dir_contents(self, left_dir_path, right_dir_path):
        # Need to sort for the merging-type algorithm later on.
        try:
            left_dir_contents = sorted([x for x in left_dir_path.iterdir()])
            right_dir_contents = sorted([x for x in right_dir_path.iterdir()])
            self._compare_subfiles(left_dir_contents, right_dir_contents)
            self._compare_subdirs(left_dir_contents, right_dir_contents)
        except Exception as err:
            log_msg = '\nError while comparing directories: {}'.format(err)
            logger.exception(log_msg)

    def check_differences(self):
        '''
        Checks and stores the differences between the 2 directories.
        '''
        left_dir_path = self.dirs_data.data_left.path
        right_dir_path = self.dirs_data.data_right.path
        if self.show_progress_bar:
            # Count the total number of files to visit for progress bar.
            # Although this is not a totally accurate measure of the actual
            # work to be done, but is a close approximate in the case of the
            # 2 directories being almost identical to each other (which is
            # hopefully the most prominent use case). In case the 2 directories
            # are huge and are totally differently structured, this step will
            # be totally unnecessary, and its better to hide progress bar
            # in that case.
            desc = 'Precomputing directory sizes for progress bar...'
            self.progress_bar = tqdm(desc=desc, unit=' items')
            left_dir_generator = left_dir_path.rglob('*')
            left_file_count_recursive = 0
            for i in left_dir_generator:
                self._mark_file_visit()
                left_file_count_recursive += 1
            right_dir_generator = right_dir_path.rglob('*')
            right_file_count_recursive = 0
            for i in right_dir_generator:
                self._mark_file_visit()
                right_file_count_recursive += 1
            total_files_count = left_file_count_recursive \
                + right_file_count_recursive
            self.progress_bar.close()
            self.progress_bar = tqdm(
                total=total_files_count,
                desc='Checking differences',
                unit=' items')
        self._compare_dir_contents(left_dir_path, right_dir_path)
        if self.progress_bar:
            self.progress_bar.close()

    def _sync_items(self, item1, item2, overwrite=False, use_trash=False):
        '''
        Synchronize two files/directories.
        `overwrite`: Whether to overwrite item1 on item2 if present.
        '''
        if item1.exists():
            if not overwrite and not item2.exists():
                if item1.is_dir():
                    shutil.copytree(item1, item2)
                else:
                    shutil.copyfile(item1, item2)
            elif overwrite:
                if item1.is_dir():
                    if item2.exists():
                        shutil.rmtree(item2) if not use_trash\
                            else send2trash(str(item2.resolve()))
                    shutil.copytree(item1, item2)
                else:
                    if item2.exists() and use_trash:
                        send2trash(str(item2.resolve()))
                    shutil.copyfile(item1, item2)

    def _remove_item(self, item, use_trash=False):
        '''
        Helper function to remove a file/directory.
        '''
        if item.exists():
            if item.is_dir():
                if use_trash:
                    send2trash(str(item.resolve()))
                else:
                    shutil.rmtree(item)
            else:
                if use_trash:
                    send2trash(str(item.resolve()))
                else:
                    item.unlink()

    def sync_dirs(self,
                  overwrite=False,
                  add_missing=False,
                  remove_extra=False,
                  reverse_direction=False,
                  dry_run=False,
                  use_trash=False):
        '''
        Synchronize the directories based on the arguments passed:
        `overwrite`: Whether to overwrite files in destination whose content
                     is different from source.
        `add_missing`: Whether to copy files from source that are absent in the
                       destination folder.
        `remove_extra`: Whether to remove files from the destination which are
                        absent from the source.
        `reverse_direction`: If true, copies from right dir to left dir.
        `dry_run`: If true, then just print the operations to be performed.
        '''
        if reverse_direction:
            # Just swap the data of the 2 directories.
            # We'll swap them again at the end to restore correctness.
            self.dirs_data.data_left, self.dirs_data.data_right = \
                self.dirs_data.data_right, self.dirs_data.data_left
        if self.show_progress_bar:
            total_files_count = 0
            # Compute how many files do we need to visit; for the progress bar.
            if add_missing:
                total_files_count += len(self.dirs_data.data_left.diff)
            if remove_extra:
                total_files_count += len(self.dirs_data.data_right.diff)
            if overwrite:
                total_files_count += len(self.dirs_data.content_diff)
            if total_files_count == 0:
                return 'Directories already in sync!'
            desc = 'Syncing contents'
            if dry_run:
                desc += ' (dry-run)'
            self.progress_bar = tqdm(
                total=total_files_count, desc=desc, unit=' items')

        dry_run_report = '\n**Dry run** report:'
        dry_run_header = '\n\n' + '>' * 25
        dry_run_footer = '<' * 25
        if remove_extra and len(self.dirs_data.data_right.diff):
            dry_run_report += dry_run_header
            dry_run_report += '\nWill be removed: ({})\n'.format(
                len(self.dirs_data.data_right.diff))
            items_extra = self.dirs_data.data_right.diff
            for item in items_extra:
                if dry_run:
                    dry_run_report += ' - "{}"\n'.format(item)
                else:
                    self._remove_item(item, use_trash)
                self._mark_file_visit()
            dry_run_report += dry_run_footer
        if add_missing and len(self.dirs_data.data_left.diff):
            dry_run_report += dry_run_header
            dry_run_report += '\nWill be copied'
            if overwrite:
                dry_run_report += ' (overwritten if present)'
            else:
                dry_run_report += ' (unchanged if already existing)'
            dry_run_report += ': ({})\n'.format(
                len(self.dirs_data.data_left.diff))
            items_extra = self.dirs_data.data_left.diff
            for item_src in items_extra:
                src_base_path = self.dirs_data.data_left.path
                dst_base_path = self.dirs_data.data_right.path
                item_relative = item_src.relative_to(src_base_path)
                item_dst = dst_base_path / item_relative
                if dry_run:
                    dry_run_report += ' - "{}" -> "{}"\n'.format(
                        item_src, item_dst)
                else:
                    self._sync_items(item_src, item_dst, overwrite, use_trash)
                self._mark_file_visit()
            dry_run_report += dry_run_footer
        if overwrite and len(self.dirs_data.content_diff):
            dry_run_report += dry_run_header
            dry_run_report += '\nWill be overwritten: ({})\n'.format(
                len(self.dirs_data.content_diff))
            items_common = self.dirs_data.content_diff
            for item in items_common:
                item_src = item[0]
                item_dst = item[1]
                if reverse_direction:
                    item_src, item_dst = item_dst, item_src
                if dry_run:
                    dry_run_report += ' - "{}" -> "{}"\n'.format(
                        item_src, item_dst)
                else:
                    self._sync_items(item_src, item_dst, True, use_trash)
                self._mark_file_visit()
            dry_run_report += dry_run_footer
        if self.progress_bar:
            self.progress_bar.close()
        if reverse_direction:
            # Swap them again to restore correctness.
            self.dirs_data.data_left, self.dirs_data.data_right = \
                self.dirs_data.data_right, self.dirs_data.data_left
        return dry_run_report

    def _mark_file_visit(self):
        '''
        Update the progress bar with 1 more iteraion.
        '''
        if self.show_progress_bar:
            self.progress_bar.update()

    def get_report(self):
        '''
        Print the difference check report in a human as well as
        machine readable format.
        '''
        num_content_diff = len(self.dirs_data.content_diff)
        num_left_extra = len(self.dirs_data.data_left.diff)
        num_right_extra = len(self.dirs_data.data_right.diff)
        if not (num_content_diff or num_left_extra or num_right_extra):
            report_string = '\nNo differences found!\n'
            return report_string
        report_string = 'Comparison report:\n'
        report_string += '\n' + 'x' * 25 + '\n'
        report_string += 'Contents different: (' + str(num_content_diff)\
                                                 + ')\n'
        for entry in self.dirs_data.content_diff:
            report_string += '- ' + str(entry[0].relative_to(
                self.dirs_data.data_left.path)) + '\n'
        report_string += '-' * 25
        report_string += '\n\n' + '[' * 25 + '\n'
        report_string += 'Extra in left: (' + str(num_left_extra) + ')\n'
        for entry in self.dirs_data.data_left.diff:
            report_string += '- ' + str(
                entry.relative_to(self.dirs_data.data_left.path)) + '\n'
        report_string += '-' * 25
        report_string += '\n\n' + ']' * 25 + '\n'
        report_string += 'Extra in right: (' + str(num_right_extra) + ')\n'
        for entry in self.dirs_data.data_right.diff:
            report_string += '- ' + str(
                entry.relative_to(self.dirs_data.data_right.path)) + '\n'
        report_string += '-' * 25 + '\n\n'
        return report_string


def main():
    args = prepare_args_parser()
    left_dir_path = args['left-path']
    right_dir_path = args['right-path']
    print('Left directory = "{}"'.format(Path(left_dir_path).resolve()))
    print('Right directory = "{}"\n'.format(Path(right_dir_path).resolve()))
    hide_progress_bar = args['hide_progress_bar']
    direct_sync = DirectSync(
        left_dir_path, right_dir_path, show_progress_bar=not hide_progress_bar)
    use_cache = args['use_cache']
    if use_cache and get_serialization_filepath(direct_sync).exists():
        print('Loading from cache!\n')
        direct_sync = deserialize_directsync(direct_sync)
        direct_sync.show_progress_bar = not hide_progress_bar
    else:
        direct_sync.check_differences()
        print('Creating cache!\n')
        serialize_directsync(direct_sync)
    print(direct_sync.get_report())
    add_missing = args['add_missing']
    remove_extra = args['remove_extra']
    overwrite_content = args['overwrite_content']
    reverse_direction = args['reverse_sync_direction']
    mirror = args['mirror_contents']
    use_trash = args['use_trash']
    dry_run = args['dry_run']
    if mirror:
        add_missing = True
        remove_extra = True
        overwrite_content = True
    if add_missing or remove_extra or overwrite_content:
        dry_run_report = direct_sync.sync_dirs(overwrite_content, add_missing,
                                               remove_extra, reverse_direction,
                                               dry_run, use_trash)
        if dry_run:
            print(dry_run_report)
        # Delete cache as it has been possibly invalidated.
        if not dry_run and get_serialization_filepath(direct_sync).exists():
            get_serialization_filepath(direct_sync).unlink()
    print('')


if __name__ == "__main__":
    main()

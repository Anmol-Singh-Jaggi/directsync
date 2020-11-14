from pathlib import Path
import shutil
import logging

from tqdm import tqdm
from send2trash import send2trash

from .file_comparison import is_file_text, compare_file_contents_buffered, is_src_file_bigger

logger = logging.getLogger(__file__)


class DirData:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.diff = []


class DirsData:
    def __init__(self, path_src, path_dst):
        # The items present in src but absent in dst.
        self.data_src = DirData(path_src)
        # The items present in dst but absent in src.
        self.data_dst = DirData(path_dst)
        # The items present on either side but with different contents.
        self.content_diff = []


class DirectSync:
    def __init__(self, dir_path_src, dir_path_dst, show_progress_bar=False):
        self.dirs_data = DirsData(dir_path_src, dir_path_dst)
        self.show_progress_bar = show_progress_bar
        self.progress_bar = None
        if not self.dirs_data.data_src.path.is_dir():
            error_msg = 'src path "{}" is not a valid directory!'
            error_msg = error_msg.format(self.dirs_data.data_src.path)
            raise Exception(error_msg)
        if not self.dirs_data.data_dst.path.is_dir():
            error_msg = 'dst path "{}" is not a valid directory!'
            error_msg = error_msg.format(self.dirs_data.data_dst.path)
            raise Exception(error_msg)

    def _are_files_equal(self, path_src, path_dst):
        # First check the file sizes.
        src_size = path_src.stat().st_size
        dst_size = path_dst.stat().st_size
        if src_size != dst_size:
            # If file sizes are different, then return straightaway!
            return False
        if not is_file_text(path_src):
            if is_file_text(path_dst):
                return False
            if src_size > 1000000:
                # Assume huge binary files with the same size
                # have the same content for performance.
                return True
        # If file size is same, and the files are text/small binaries,
        # then compare their contents.
        return compare_file_contents_buffered(path_src, path_dst)

    def __getstate__(self):
        '''
        Specify what attributes to serialize.
        Needed to tell pickle to ignore `self.progress_bar`
        as `tqdm()` objects cannot be serialized.
        '''

        def should_pickle(attr_key):
            return 'progress' not in attr_key

        return {k: v for k, v in self.__dict__.items() if should_pickle(k)}

    def _compare_subfiles(self, src_dir_contents, dst_dir_contents):
        '''
        Compare the file items.
        '''
        src_files = [x for x in src_dir_contents if x.is_file()]
        dst_files = [x for x in dst_dir_contents if x.is_file()]

        # Use a merging sort of algorithm.
        # 1. Sort the 2 lists according to Path's inbuilt comparison predicate
        # 2. Have 2 pointers, one on either list.
        # 3. If the 2 pointed items have the same name, then compare contents.
        #    Else add the lower name entry to `extras` and advance its pointer.
        # 4. Repeat 3 until either of the pointers reach the end.
        # 5. Exhaust the 2 pointers and add all the pointed items to `extras`.
        src_iterator = 0
        dst_iterator = 0

        while src_iterator < len(src_files) and dst_iterator < len(
                dst_files):
            self._mark_file_visit()
            src_entry = src_files[src_iterator]
            dst_entry = dst_files[dst_iterator]
            src_entry_name = src_entry.name
            dst_entry_name = dst_entry.name
            if src_entry_name == dst_entry_name:
                are_files_same = self._are_files_equal(src_entry, dst_entry)
                if not are_files_same:
                    self.dirs_data.content_diff.append((src_entry,
                                                        dst_entry))
                src_iterator += 1
                dst_iterator += 1
                self._mark_file_visit()
            elif Path(src_entry_name) < Path(dst_entry_name):
                self.dirs_data.data_src.diff.append(src_entry)
                src_iterator += 1
            else:
                self.dirs_data.data_dst.diff.append(dst_entry)
                dst_iterator += 1

        while src_iterator < len(src_files):
            src_entry = src_files[src_iterator]
            self.dirs_data.data_src.diff.append(src_entry)
            src_iterator += 1
            self._mark_file_visit()

        while dst_iterator < len(dst_files):
            dst_entry = dst_files[dst_iterator]
            self.dirs_data.data_dst.diff.append(dst_entry)
            dst_iterator += 1
            self._mark_file_visit()

    def _compare_subdirs(self, src_dir_contents, dst_dir_contents):
        '''
        Similar to `_compare_subfile()` but for directories.
        '''
        src_subdirs = [x for x in src_dir_contents if x.is_dir()]
        dst_subdirs = [x for x in dst_dir_contents if x.is_dir()]
        # Directories (subdirectories) to explore next.
        next_subdirs = []

        src_iterator = 0
        dst_iterator = 0

        while src_iterator < len(src_subdirs) and dst_iterator < len(
                dst_subdirs):
            self._mark_file_visit()
            src_entry = src_subdirs[src_iterator]
            dst_entry = dst_subdirs[dst_iterator]
            src_entry_name = src_entry.name
            dst_entry_name = dst_entry.name
            if src_entry_name == dst_entry_name:
                next_subdirs.append((src_entry, dst_entry))
                src_iterator += 1
                dst_iterator += 1
                self._mark_file_visit()
            elif Path(src_entry_name) < Path(dst_entry_name):
                self.dirs_data.data_src.diff.append(src_entry)
                src_iterator += 1
            else:
                self.dirs_data.data_dst.diff.append(dst_entry)
                dst_iterator += 1

        while src_iterator < len(src_subdirs):
            src_entry = src_subdirs[src_iterator]
            self.dirs_data.data_src.diff.append(src_entry)
            src_iterator += 1
            self._mark_file_visit()

        while dst_iterator < len(dst_subdirs):
            dst_entry = dst_subdirs[dst_iterator]
            self.dirs_data.data_dst.diff.append(dst_entry)
            dst_iterator += 1
            self._mark_file_visit()

        for dir_entry in next_subdirs:
            # Recursive call
            self._compare_dir_contents(dir_entry[0], dir_entry[1])

    def _compare_dir_contents(self, src_dir_path, dst_dir_path):
        # Need to sort for the merging-type algorithm later on.
        try:
            src_dir_contents = sorted([x for x in src_dir_path.iterdir()])
            dst_dir_contents = sorted([x for x in dst_dir_path.iterdir()])
            self._compare_subfiles(src_dir_contents, dst_dir_contents)
            self._compare_subdirs(src_dir_contents, dst_dir_contents)
        except Exception as err:
            log_msg = '\nError while comparing directories: {}'.format(err)
            logger.exception(log_msg)

    def check_differences(self):
        '''
        Checks and stores the differences between the 2 directories.
        '''
        src_dir_path = self.dirs_data.data_src.path
        dst_dir_path = self.dirs_data.data_dst.path
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
            src_dir_generator = src_dir_path.rglob('*')
            src_file_count_recursive = 0
            for i in src_dir_generator:
                self._mark_file_visit()
                src_file_count_recursive += 1
            dst_dir_generator = dst_dir_path.rglob('*')
            dst_file_count_recursive = 0
            for i in dst_dir_generator:
                self._mark_file_visit()
                dst_file_count_recursive += 1
            total_files_count = src_file_count_recursive \
                + dst_file_count_recursive
            self.progress_bar.close()
            self.progress_bar = tqdm(
                total=total_files_count,
                desc='Checking differences',
                unit=' items')
        self._compare_dir_contents(src_dir_path, dst_dir_path)
        if self.progress_bar:
            # In cases where the directories are very different, not all files
            # and sub-dirs are visited. So, we'll need to manually update the
            # progress bar to the finish.
            self.progress_bar.update(total_files_count-self.progress_bar.n)
            self.progress_bar.close()

    def _sync_items(self,
                    item1,
                    item2,
                    overwrite=False,
                    use_trash=False,
                    preserve_latest=False):
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
                    should_reverse = self._compare_file_mtime(item1,
                                                              item2,
                                                              preserve_latest)
                    if should_reverse:
                        item1, item2 = item2, item1
                    if item2.exists() and use_trash:
                        send2trash(str(item2.resolve()))
                    shutil.copyfile(item1, item2)
                    if should_reverse:
                        item1, item2 = item2, item1

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

    def _compare_file_mtime(self, item1, item2, preserve_latest):
        return preserve_latest and (item1.stat().st_mtime <
                                    item2.stat().st_mtime)

    def sync_dirs(self,
                  overwrite=False,
                  add_missing=False,
                  remove_extra=False,
                  dry_run=False,
                  use_trash=False,
                  preserve_latest=False):
        '''
        Synchronize the directories based on the arguments passed:
        `overwrite`: Whether to overwrite files in destination whose content
                     is different from source.
        `add_missing`: Whether to copy files from source that are absent in the
                       destination folder.
        `remove_extra`: Whether to remove files from the destination which are
                        absent from the source.
        `dry_run`: If true, then just print the operations to be performed.
        '''
        if self.show_progress_bar:
            total_files_count = 0
            # Compute how many files do we need to visit; for the progress bar.
            if add_missing:
                total_files_count += len(self.dirs_data.data_src.diff)
            if remove_extra:
                total_files_count += len(self.dirs_data.data_dst.diff)
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
        if remove_extra and len(self.dirs_data.data_dst.diff):
            dry_run_report += dry_run_header
            dry_run_report += '\nWill be removed: ({})\n'.format(
                len(self.dirs_data.data_dst.diff))
            items_extra = self.dirs_data.data_dst.diff
            for item in items_extra:
                if dry_run:
                    dry_run_report += ' - "{}"\n'.format(item)
                else:
                    self._remove_item(item, use_trash)
                self._mark_file_visit()
            dry_run_report += dry_run_footer
        if add_missing and len(self.dirs_data.data_src.diff):
            dry_run_report += dry_run_header
            dry_run_report += '\nWill be copied'
            if overwrite:
                dry_run_report += ' (overwritten if present)'
            else:
                dry_run_report += ' (unchanged if already existing)'
            dry_run_report += ': ({})\n'.format(
                len(self.dirs_data.data_src.diff))
            items_extra = self.dirs_data.data_src.diff
            for item_src in items_extra:
                src_base_path = self.dirs_data.data_src.path
                dst_base_path = self.dirs_data.data_dst.path
                item_relative = item_src.relative_to(src_base_path)
                item_dst = dst_base_path / item_relative
                if dry_run:
                    dry_run_report += ' - "{}" -> "{}"\n'.format(
                        item_src, item_dst)
                else:
                    self._sync_items(item_src, item_dst, overwrite, use_trash,
                                     preserve_latest)
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
                if dry_run:
                    should_reverse = self._compare_file_mtime(item_src,
                                                              item_dst,
                                                              preserve_latest)
                    if should_reverse:
                        item_src, item_dst = item_dst, item_src
                    dry_run_report += ' - "{}" -> "{}"\n'.format(
                        item_src, item_dst)
                    if should_reverse:
                        item_src, item_dst = item_dst, item_src
                else:
                    self._sync_items(item_src, item_dst, True, use_trash,
                                     preserve_latest)
                self._mark_file_visit()
            dry_run_report += dry_run_footer
        if self.progress_bar:
            self.progress_bar.close()
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
        num_src_extra = len(self.dirs_data.data_src.diff)
        num_dst_extra = len(self.dirs_data.data_dst.diff)
        if not (num_content_diff or num_src_extra or num_dst_extra):
            report_string = '\nNo differences found!\n'
            return report_string
        report_string = 'Comparison report:\n'
        report_string += '\n' + 'x' * 25 + '\n'
        report_string += 'Contents different: (' + str(num_content_diff)\
                                                 + ')\n'
        for entry in self.dirs_data.content_diff:
            report_string += '- ' + str(entry[0].relative_to(
                self.dirs_data.data_src.path)) + ' --- bigger size in ' + ('src' if is_src_file_bigger(entry[0], entry[1]) else 'dst') + '\n'
        report_string += '-' * 25
        report_string += '\n\n' + '[' * 25 + '\n'
        report_string += 'Extra in src: (' + str(num_src_extra) + ')\n'
        for entry in self.dirs_data.data_src.diff:
            report_string += '- ' + str(
                entry.relative_to(self.dirs_data.data_src.path)) + '\n'
        report_string += '-' * 25
        report_string += '\n\n' + ']' * 25 + '\n'
        report_string += 'Extra in dst: (' + str(num_dst_extra) + ')\n'
        for entry in self.dirs_data.data_dst.diff:
            report_string += '- ' + str(
                entry.relative_to(self.dirs_data.data_dst.path)) + '\n'
        report_string += '-' * 25 + '\n\n'
        return report_string

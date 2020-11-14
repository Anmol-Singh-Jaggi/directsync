from pathlib import Path

from .core import DirectSync
from .args_parsing import prepare_args_parser
from .serialization import serialize_directsync, deserialize_directsync,\
                           get_serialization_filepath


def main():
    args = prepare_args_parser()
    src_dir_path = args['src-path']
    dst_dir_path = args['dst-path']
    print('src directory = "{}"'.format(Path(src_dir_path).resolve()))
    print('dst directory = "{}"\n'.format(Path(dst_dir_path).resolve()))

    hide_progress_bar = args['hide_progress_bar']
    use_cache = args['use_cache']
    add_missing = args['add_missing']
    remove_extra = args['remove_extra']
    overwrite_content = args['overwrite_content']
    mirror = args['mirror_contents']
    use_trash = args['use_trash']
    dry_run = args['dry_run']
    preserve_latest = args['preserve_latest']

    direct_sync = DirectSync(
        src_dir_path, dst_dir_path, show_progress_bar=not hide_progress_bar)
    if use_cache and get_serialization_filepath(direct_sync).exists():
        print('Loading from cache!\n')
        direct_sync = deserialize_directsync(direct_sync)
        direct_sync.show_progress_bar = not hide_progress_bar
    else:
        direct_sync.check_differences()
        print('Creating cache!\n')
        serialize_directsync(direct_sync)
    print(direct_sync.get_report())
    if mirror:
        add_missing = True
        remove_extra = True
        overwrite_content = True
    if add_missing or remove_extra or overwrite_content:
        dry_run_report = direct_sync.sync_dirs(
            overwrite_content, add_missing, remove_extra,
            dry_run, use_trash, preserve_latest)
        if dry_run:
            print(dry_run_report)
        # Delete cache as it has been possibly invalidated.
        if not dry_run and get_serialization_filepath(direct_sync).exists():
            get_serialization_filepath(direct_sync).unlink()
    print('')


if __name__ == "__main__":
    main()

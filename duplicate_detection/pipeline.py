import os.path
from pathlib import Path

from folder_partition.partition import split_folder_by_size, verify_folder_sizes
from duplicate_detection.exacte_duplicata_detection import add_files2database
from duplicate_detection.database import get_total_duplicates_size, delete_duplicate_files, record_folders2database


def pipeline(path_db, predir, todir, location, threshsize=10):
    predir = Path(predir)
    todir = Path(todir)

    mode = input("添加全新location输入(a/A/add), 更新现有location输入(u/U/update), 取消操作输入(n/N): ").strip().lower()

    if mode == "a" or mode == "add":
        # 划分文件夹大小
        if not verify_folder_sizes(predir / todir, threshsize=threshsize):
            split_folder_by_size(os.path.join(predir, todir), threshsize=threshsize)

        record_folders2database(
            db_path=path_db,
            pre_target_dir=predir,
            target_dir=todir.name,
            location=location,
        )

        add_files2database(
            db_path=path_db,
            pre_target_dir=predir,
            target_dir=todir,
            location=location
        )

        get_total_duplicates_size(db_path=path_db, location=location)

        delete_duplicate_files(db_path=path_db, pre_target_dir=predir, location=location, dry_run=False)
    elif mode == "u" or mode == "update":
        if not verify_folder_sizes(predir / todir, threshsize=threshsize):
            split_folder_by_size(os.path.join(predir, todir), threshsize=threshsize)

        record_folders2database(
            db_path=path_db,
            pre_target_dir=predir,
            target_dir=todir.name,
            location=location,
        )

        ifadd = input("是否再次计算hash添加新文件? (y/yes/N): )").strip().lower()
        if ifadd == "y" or ifadd == "yes":
            add_files2database(
                db_path=path_db,
                pre_target_dir=predir,
                target_dir=todir,
                location=location
            )
        else:
            print("跳过计算hash, 跳过添加新文件! ")

        get_total_duplicates_size(db_path=path_db, location=location)

        delete_duplicate_files(db_path=path_db, pre_target_dir=predir, location=location, dry_run=False)
    else:
        print("操作取消! ")
        return
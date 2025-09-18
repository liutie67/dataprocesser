import os.path
from pathlib import Path

from folder_partition.partition import split_folder_by_size, verify_folder_sizes
from duplicate_detection.exacte_duplicata_detection import add_files2database
from duplicate_detection.database import get_total_duplicates_size, delete_duplicate_files, record_folders2database
from duplicate_detection.database import check_matches_database_disk, classer


def pipeline(path_db, predir, todir, location: int, threshsize=10):
    print(f"- 当前 location: {location}")
    print(f"- 当前 database: {path_db}")
    print(f"- 当前 predir: {predir}")
    print(f"- 当前 todir: {todir}")

    predir = Path(predir)
    todir = Path(todir)

    mode = input("- 添加输入(a/add), classer输入(c/classer), examiner & assaini输入(e/d/m), 取消操作输入(n/N): ").strip().lower()
    if mode == "a" or mode == "add":
        # 划分文件夹大小
        if not verify_folder_sizes(predir / todir, threshsize=threshsize):
            split_folder_by_size(os.path.join(predir, todir), threshsize=threshsize)

        record_folders2database(
            db_path=path_db,
            pre_target_dir=predir,
            target_dir=todir.name,
            location=location,
            askconfirm=False,
        )

        ifadd = input("是否再次计算hash添加新文件? (y/yes/N): ").strip().lower()
        if ifadd == "y" or ifadd == "yes":
            add_files2database(
                db_path=path_db,
                pre_target_dir=predir,
                target_dir=todir,
                location=location
            )
        else:
            print(f"{'s'*50}跳过计算hash, 跳过添加新文件! {'s'*50}")

        get_total_duplicates_size(db_path=path_db, location=location)

        delete_duplicate_files(db_path=path_db, pre_target_dir=predir, location=location, dry_run=False)
    elif mode == "c" or mode == "classer":
        # check_matches_database_disk(
        #     database_path=path_db,
        #     location=location,
        #     folder_path=predir,
        # )

        classer(
            database_path=path_db,
            location=location,
            folder_path=predir / todir,
        )
    elif mode == "e" or mode == "d" or mode == "m":
        check_matches_database_disk(
            database_path=path_db,
            location=location,
            folder_path=predir / todir,
            assaini_by_filename=True,
        )

    else:
        print("操作取消! ")
        return
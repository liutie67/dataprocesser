import os.path
import sqlite3
from pathlib import Path

from tqdm import tqdm

from duplicate_detection.hash import hash_file_complet, hash_file_fast
from duplicate_detection.utiles import get_human_readable_size


def initialize_db():
    # # 确保表结构存在
    # thread_local.conn.execute('''
    #     CREATE TABLE IF NOT EXISTS unique_files (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         sha256 TEXT UNIQUE NOT NULL,
    #         filename TEXT NOT NULL,
    #         path TEXT NOT NULL,
    #         file_size INTEGER NOT NULL,
    #         created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    #     )
    # ''')
    # thread_local.conn.execute('''
    #     CREATE TABLE IF NOT EXISTS duplicate_files (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         sha256 TEXT NOT NULL,
    #         original_file_id INTEGER NOT NULL,
    #         filename TEXT NOT NULL,
    #         path TEXT NOT NULL,
    #         created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    #         FOREIGN KEY (original_file_id) REFERENCES unique_files (id)
    #     )
    # ''')

    return None


def legacy_insert_file_data(db_path, file_path, mark=None):
    """
    直接插入数据
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        filename = os.path.basename(file_path)
        sha256_value = hash_file_complet(file_path)

        if mark is not None:
            cursor.execute('''
                INSERT INTO files (filename, path, sha256, mark)
                VALUES (?, ?, ?, ?)
            ''', (filename, file_path, sha256_value, mark))
        else:
            cursor.execute('''
                INSERT INTO files (filename, path, sha256)
                VALUES (?, ?, ?)
            ''', (filename, file_path, sha256_value))

        conn.commit()
        print(f"插入成功！ID: {cursor.lastrowid}")

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")

    finally:
        if conn:
            conn.close()


def delete_duplicate_files(db_path, pre_target_dir, location, dry_run=True):
    """
    删除重复文件并将删除状态更新到数据库
    :param db_path: 数据库路径
    :param pre_target_dir: 针对每个系统而不同的路径
    :param location: 储存的位置 (作为筛选)
    :param dry_run: 是否为干运行（只显示不实际删除）
    """
    pre_target_dir = os.path.normpath(pre_target_dir)
    try:
        with sqlite3.connect(db_path) as conn:
            # 获取所有需要删除的重复文件
            cursor = conn.execute(f'''
                SELECT df.id, df.filepath, uf.filepath as original_path, df.sha256
                FROM duplicates df
                JOIN files uf ON df.original_id = uf.id
                WHERE df.deleted = 0 AND df.location_id = ?
            ''', (location,))

            duplicates = cursor.fetchall()

            if not duplicates:
                print("没有找到需要删除的重复文件！")
                return

            if not dry_run:
                confirm = input(f"找到 {len(duplicates)} 个待删除的重复文件，是否要永久移除这些文件？(y/N): ")

                if not (confirm.lower() == 'y' or confirm.lower() == 'yes'):
                    print("<删除操作>取消！")
                    return

            deleted_count = 0
            error_count = 0
            skipped_count = 0

            with tqdm(total=len(duplicates), desc="处理重复文件", unit="file") as pbar:
                for dup_id, dup_path, original_path, sha256 in duplicates:
                    try:
                        # 检查文件是否存在
                        if not os.path.exists(os.path.join(pre_target_dir ,dup_path)):
                            print(f"文件不存在，跳过: {dup_path}")
                            # 更新数据库状态为已删除（文件不存在）
                            conn.execute(
                                'UPDATE duplicates SET deleted = 1 WHERE id = ?',
                                (dup_id,)
                            )
                            skipped_count += 1
                            pbar.update(1)
                            continue

                        # 检查是否为相同的路径（不应该发生，但安全起见）
                        if dup_path == original_path:
                            print(f"警告：重复文件路径与原文件相同，跳过: {dup_path}")
                            skipped_count += 1
                            pbar.update(1)
                            continue

                        # 获取文件信息用于确认
                        file_size = os.path.getsize(os.path.join(pre_target_dir ,dup_path))

                        if dry_run:
                            print(f"[干运行] 将删除: {dup_path} (大小: {file_size} bytes, SHA256: {sha256[:8]}...)")
                            deleted_count += 1
                        else:
                            # 实际删除文件
                            os.remove(os.path.join(pre_target_dir ,dup_path))
                            print(f"已删除: {dup_path}")

                            # 更新数据库，标记为已删除
                            conn.execute(
                                'UPDATE duplicates SET deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?',
                                (dup_id,)
                            )
                            deleted_count += 1

                    except PermissionError:
                        print(f"权限不足，无法删除: {dup_path}")
                        error_count += 1
                    except Exception as e:
                        print(f"删除文件时出错 {dup_path}: {e}")
                        error_count += 1

                    pbar.update(1)

            conn.commit()

            print(f"\n处理完成:")
            print(f"成功删除: {deleted_count}")
            print(f"跳过: {skipped_count}")
            print(f"错误: {error_count}")
            print(f"总计: {len(duplicates)}")

            if dry_run:
                print("\n注意：这是在干运行模式下，没有实际删除任何文件。")
                print("如果要实际删除，请设置 dry_run=False")

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    except Exception as e:
        print(f" unexpected error: {e}")


def cleanup_deleted_files(db_path):
    """
    清理已标记为删除的文件记录（可选）

    :param db_path: 数据库路径
    """
    try:
        with sqlite3.connect(db_path) as conn:
            # 检查是否有已删除的文件记录
            cursor = conn.execute('''
                SELECT COUNT(*) FROM duplicates WHERE deleted = 1
            ''')
            deleted_count = cursor.fetchone()[0]

            if deleted_count == 0:
                print("没有已删除的文件记录！")
                return

            confirm = input(f"找到 {deleted_count} 条已删除的文件记录，是否要永久移除这些记录？(y/N): ")

            if confirm.lower() == 'y' or confirm.lower() == 'yes':
                conn.execute('DELETE FROM duplicates WHERE deleted = 1')
                conn.commit()
                print(f"已移除 {deleted_count} 条已删除的文件记录。")
            else:
                print("取消操作！")

    except Exception as e:
        print(f"清理记录时出错: {e}")


def get_total_duplicates_size(db_path, deleted=0, location=None):
    """
    计算duplicates表中所有deleted标记为0的文件大小总和

    :param db_path: 数据库路径
    :param deleted: 是否已删除文件
    :param location: 储存的位置 (作为筛选)
    :return: 文件大小总和，如果出错返回None
    """
    try:
        with sqlite3.connect(db_path) as conn:
            # 检查表是否存在deleted字段
            cursor = conn.execute("PRAGMA table_info(duplicates)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'deleted' not in columns:
                print("get_total_duplicates_size: 警告: duplicates表没有deleted字段，将计算所有记录！")
                # 如果没有deleted字段，计算所有记录的大小
                cursor = conn.execute('''
                    SELECT SUM(filesize) 
                    FROM duplicates
                ''')
            else:
                # 计算deleted=0的记录大小总和
                if location is None:
                    cursor = conn.execute('''
                                            SELECT SUM(filesize) 
                                            FROM duplicates
                                            WHERE deleted = ?
                                        ''', (deleted,))
                else:
                    cursor = conn.execute('''
                                            SELECT SUM(filesize) 
                                            FROM duplicates
                                            WHERE deleted = ? AND location_id = ?
                                        ''', (deleted, location,))

            total_size = cursor.fetchone()[0]

            print(f"get_total_duplicates_size: location id: {location} 重复文件总大小 = {get_human_readable_size(total_size)}")

            return total_size if total_size is not None else 0

    except sqlite3.Error as e:
        print(f"get_total_duplicates_size: 数据库错误: {e}")
        return None
    except Exception as e:
        print(f"get_total_duplicates_size: unexpected error: {e}")
        return None


def record_folders2database(db_path, pre_target_dir, target_dir, location):
    """
    检测指定路径的第一层文件夹，并将文件夹名写入SQLite数据库，同时重命名原文件夹

    Args:
        db_path (str): SQLite数据库文件路径
        pre_target_dir: 针对每个系统而不同的路径
        target_dir (str): 要扫描的目录路径(数据库记录的起始路径)
        location (int): 文件夹数据库位置标签🏷️
    """
    # 询问用户确认
    confirm = input(f"record_folders2database: 相同 location id 重复执行只添加新增的文件夹(y确认/N取消): ").strip().lower()

    if confirm == 'y' or confirm == 'yes' or confirm == 'y确认' or confirm == '确认':
        print('record_folders2database: 开始记录📝: ')
    else:
        print('record_folders2database: 操作取消！')
        return

    table_name = target_dir.replace(os.sep, '').replace('.', '')
    target_dir = os.path.normpath(target_dir)
    pre_target_dir = os.path.normpath(pre_target_dir)
    target_dir = os.path.join(pre_target_dir, target_dir)

    # 确保目录存在
    if not os.path.exists(target_dir):
        print(f"record_folders2database: 错误：目录 '{target_dir}' 不存在！")
        return

    # 连接到SQLite数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取目录中的第一层文件夹
    folders = [f for f in Path(target_dir).iterdir() if f.is_dir()]

    for folder_path in folders:
        original_name = folder_path.name
        original_full_path = str(folder_path)
        proposed_name = original_name
        attempt = 1

        while True:
            try:
                # 如果名称有变化，需要重命名文件夹
                if proposed_name != original_name:
                    new_path = os.path.join(target_dir, proposed_name)

                    # 检查新路径是否已存在（避免覆盖）
                    if os.path.exists(new_path):
                        print(f"record_folders2database： 警告：路径 '{new_path}' 已存在，无法重命名！")
                    else:
                        # 重命名文件夹
                        try:
                            os.rename(original_full_path, new_path)
                            print(f"record_folders2database: 已重命名文件夹: '{original_name}' -> '{proposed_name}'")
                        except OSError as e:
                            print(f"record_folders2database: 重命名失败: {e}")

                # 插入数据库记录
                cursor.execute(
                    f"INSERT INTO {table_name} (folder, location_id) VALUES (?, ?)",
                    (proposed_name, location)
                )
                conn.commit()
                print(f"record_folders2database: ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ add : {proposed_name}")
                break

            except sqlite3.IntegrityError:
                # 名称重复，询问用户是否要添加后缀
                print(f"record_folders2database: 文件夹名 '{proposed_name}' 已存在。")

                # 检查是否是同一个location
                cursor = conn.execute('''
                                SELECT location_id FROM aenfer WHERE folder = ?
                            ''', (proposed_name,))
                loca = cursor.fetchone()[0]

                if location != loca:
                    # 询问用户确认
                    action = input(f"record_folders2database: 为 '{original_name}' 添加后缀重试(y/yes), 跳过当前文件夹(s/skip), 或取消其他操作(N): ").strip().lower()
                else:
                    action = 'skip'

                if action == 'y' or action == 'yes':
                    # 生成新名称
                    proposed_name = f"{original_name}(重{attempt})"
                    attempt += 1
                    print(f"record_folders2database: rename: 尝试新名称: '{proposed_name}'")
                elif action == 's' or action == 'skip':
                    print(f"record_folders2database: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ skip : 跳过文件夹: '{original_name}'")
                    break  # 跳出while循环，继续处理下一个文件夹
                    
            except Exception as e:
                print(f"record_folders2database: 处理文件夹 '{original_name}' 时发生错误: {e}")
                break

    # 关闭数据库连接
    conn.close()
    print(f"record_folders2database: '{target_dir.replace(os.sep, '').replace('.', '')}' 处理完成。")


def existed_files_in_database(folder_path, db_file, delete_existed=False):
    """
    检查文件夹中所有文件的哈希值是否存在于数据库中

    Args:
        folder_path: 目标文件夹路径
        db_file: SQLite数据库文件路径
        delete_existed: 是否删除已存在于数据库的文件
    """
    folder_path = Path(folder_path)
    db_file = Path(db_file)

    if not folder_path.exists() or not folder_path.is_dir():
        print(f"错误: 文件夹路径 '{folder_path}' 不存在或不是目录")
        return

    if not db_file.exists():
        print(f"错误: 数据库文件 '{db_file}' 不存在")
        return

    # 连接到数据库
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 确保files表和sha256字段存在
    try:
        cursor.execute("SELECT sha256 FROM files LIMIT 1")
    except sqlite3.OperationalError:
        print("错误: 数据库中不存在files表或sha256字段")
        conn.close()
        return

    # 为sha256字段创建索引（如果不存在的话）以提高查询性能
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sha256 ON files (sha256)")
        conn.commit()
    except Exception as e:
        print(f"警告: 创建索引失败: {e}")

    # 遍历文件夹中的文件
    existing_count = 0
    missing_count = 0
    existing_size = 0
    missing_size = 0
    total_files = 0
    deleted_count = 0
    deleted_size = 0

    print("开始检查文件...")

    for file_path in folder_path.rglob('*'):
        if file_path.name.startswith('.'):
            continue
        if file_path.is_file():
            total_files += 1
            try:
                file_hash = hash_file_fast(file_path)
                file_size = file_path.stat().st_size

                # 逐个查询数据库
                cursor.execute("SELECT COUNT(*) FROM files WHERE sha256 = ?", (file_hash,))
                exists = cursor.fetchone()[0] > 0

                if exists:
                    existing_count += 1
                    existing_size += file_size
                    print(f"✓ 已存在: {file_path.name}")

                    # 如果设置了删除选项，删除已存在的文件
                    if delete_existed:
                        try:
                            file_path.unlink()  # 删除文件
                            deleted_count += 1
                            deleted_size += file_size
                            print(f"  已删除: {file_path.name}")
                        except Exception as e:
                            print(f"  删除失败: {file_path.name} - {e}")
                else:
                    missing_count += 1
                    missing_size += file_size
                    print(f"✗ 不存在: {file_path.name}")

            except Exception as e:
                print(f"错误处理文件 {file_path}: {e}")
                continue

    # 关闭数据库连接
    conn.close()

    # 打印结果
    print("\n" + "=" * 50)
    print("检查结果:")
    print(f"总文件数: {total_files}")
    print(f"已存在于数据库的文件数: {existing_count}")
    print(f"不存在于数据库的文件数: {missing_count}")
    print(f"已存在文件总大小: {existing_size} 字节 ({existing_size / 1024 / 1024:.2f} MB)")
    print(f"不存在文件总大小: {missing_size} 字节 ({missing_size / 1024 / 1024:.2f} MB)")
    print(
        f"所有文件总大小: {existing_size + missing_size} 字节 ({(existing_size + missing_size) / 1024 / 1024:.2f} MB)")

    if delete_existed:
        print(f"\n删除统计:")
        print(f"已删除文件数: {deleted_count}")
        print(f"已删除文件总大小: {deleted_size} 字节 ({deleted_size / 1024 / 1024:.2f} MB)")

    print("=" * 50)


from typing import List, Tuple, Dict, Any
def check_matches_database_disk(database_path, location: int, folder_path, verbose: bool=True, assaini_by_filename=False) -> Dict[str, List[Tuple[int, str]]]:
    """
    检查数据库中的文件路径是否与实际文件夹中的文件匹配

    Args:
        database_path: SQLite数据库文件路径
        location: 要检查的location_id值
        folder_path: 目标文件夹路径
        verbose: 是否print打印检测信息
        assaini_by_filename: 是否根据文件名称标记 assaini 字段

    Returns:
        包含两个列表的字典：
        - 'db_not_in_folder': 在数据库中但不在文件夹中的文件（id, filepath）
        - 'folder_not_in_db': 在文件夹中但不在数据库中的文件（id设为-1, filepath）
    """
    database_path = Path(database_path)
    folder_path = Path(folder_path)

    # 确保文件夹路径存在
    if not os.path.exists(folder_path):
        raise ValueError(f"文件夹路径不存在: {folder_path}")

    # 连接数据库
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    try:
        # 从数据库获取指定location的文件
        cursor.execute(
            "SELECT id, filepath FROM files WHERE location_id = ?",
            (location,)
        )
        db_files = cursor.fetchall()

        # 获取文件夹中的所有文件（包括子目录）
        folder_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.startswith('.'):
                    continue
                # 获取相对路径（相对于目标文件夹）
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, folder_path)
                folder_files.append(relative_path)

        # 转换为集合以便快速查找
        db_filepaths = {filepath for _, filepath in db_files}
        folder_filepaths_set = set(folder_files)

        # 找出在数据库中但不在文件夹中的文件
        db_not_in_folder = [
            (id, filepath) for id, filepath in db_files
            if filepath not in folder_filepaths_set
        ]

        # 找出在文件夹中但不在数据库中的文件
        folder_not_in_db = [
            (-1, filepath) for filepath in folder_files
            if filepath not in db_filepaths
        ]

        if verbose:
            # 打印结果
            print()
            print(f"检查位置ID: {location}")
            print(f"目标文件夹: {folder_path}")
            print(f"数据库总文件数: {len(db_files)}")
            print(f"文件夹总文件数: {len(folder_files)}")
            print(f"\n总结:")
            print(f"数据库中存在但文件夹中缺失的文件数: {len(db_not_in_folder)}")
            print(f"文件夹中存在但数据库中缺失的文件数: {len(folder_not_in_db)}")

            print("\n在数据库中但不在文件夹中的文件:")
            for id, filepath in db_not_in_folder:
                print(f"  ID: {id}, 路径: {filepath}")

            print("\n在文件夹中但不在数据库中的文件:")
            for id, filepath in folder_not_in_db:
                print(f"  路径: {filepath}")

        # 新增功能：如果db_not_in_folder不为空且folder_not_in_db为空，询问用户是否更新assaini字段
        if assaini_by_filename:
            if db_not_in_folder and not folder_not_in_db:
                print("\n" + "-" * 100)
                print("检测到database中有文件被删除，且目标文件夹中没有多余文件")
                print("是否要将database中文件的 assaini 字段设置为1？")
                print("-" * 100)

                user_input = input("请确认 (yes/y/N): ").strip().lower()

                if user_input == 'yes' or user_input == 'y':
                    # 获取所有需要更新的文件ID
                    file_ids = [file_id for file_id, _ in db_not_in_folder]

                    # 使用参数化查询更新assaini字段
                    placeholders = ','.join('?' for _ in file_ids)
                    update_query = f"UPDATE files SET assaini = 1 WHERE id IN ({placeholders})"

                    cursor.execute(update_query, file_ids)
                    conn.commit()

                    print(f"已成功更新 {len(file_ids)} 个文件的 assaini 字段为1")
                else:
                    print("已跳过更新操作! ")

        return {
            'db_not_in_folder': db_not_in_folder,
            'folder_not_in_db': folder_not_in_db
        }

    except Exception as e:
        # 如果出现错误，回滚任何更改
        conn.rollback()
        raise e

    finally:
        conn.close()


if __name__ == '__main__':
    # 使用示例
    DATABASE_PATH = 'database/path/to.db'
    predir = 'path/to/pre/target'

    delete_duplicate_files(
        db_path=DATABASE_PATH,
        pre_target_dir=predir,
        dry_run=True
    )

    cleanup_deleted_files(
        db_path=DATABASE_PATH
    )



    # 插入数据
    legacy_insert_file_data(
        db_path=DATABASE_PATH,
        file_path="/home/user/test.txt",
        mark=1
    )

    # 插入数据
    legacy_insert_file_data(
        db_path=DATABASE_PATH,
        file_path="/home/user/test2.txt",
    )
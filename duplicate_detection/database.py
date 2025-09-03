import os.path
import sqlite3
from pathlib import Path

from tqdm import tqdm

from duplicate_detection.hash import hash_file_complet
from utiles import get_human_readable_size


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
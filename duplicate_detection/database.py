import os.path
import sqlite3

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


def delete_duplicate_files(db_path, pre_target_dir, dry_run=True):
    """
    删除重复文件并将删除状态更新到数据库
    :param db_path: 数据库路径
    :param pre_target_dir: 针对每个系统而不同的路径
    :param dry_run: 是否为干运行（只显示不实际删除）
    """
    pre_target_dir = os.path.normpath(pre_target_dir)
    try:
        with sqlite3.connect(db_path) as conn:
            # 获取所有需要删除的重复文件
            cursor = conn.execute('''
                SELECT df.id, df.filepath, uf.filepath as original_path, df.sha256
                FROM duplicates df
                JOIN files uf ON df.original_id = uf.id
                WHERE df.deleted = 0
            ''')

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



def get_total_duplicates_size(db_path):
    """
    计算duplicates表中所有deleted标记为0的文件大小总和

    :param db_path: 数据库路径
    :return: 文件大小总和，如果出错返回None
    """
    try:
        with sqlite3.connect(db_path) as conn:
            # 检查表是否存在deleted字段
            cursor = conn.execute("PRAGMA table_info(duplicates)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'deleted' not in columns:
                print("警告: duplicates表没有deleted字段，将计算所有记录！")
                # 如果没有deleted字段，计算所有记录的大小
                cursor = conn.execute('''
                    SELECT SUM(filesize) 
                    FROM duplicates
                ''')
            else:
                # 计算deleted=0的记录大小总和
                cursor = conn.execute('''
                    SELECT SUM(filesize) 
                    FROM duplicates
                    WHERE deleted = 0
                ''')

            total_size = cursor.fetchone()[0]

            print(f"重复文件总大小 = {get_human_readable_size(total_size)}")

            return total_size if total_size is not None else 0

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return None
    except Exception as e:
        print(f" unexpected error: {e}")
        return None


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
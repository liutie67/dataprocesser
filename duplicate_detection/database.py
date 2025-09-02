import os.path
import sqlite3

from duplicate_detection.hash import hash_file_complet


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


if __name__ == '__main__':
    # 使用示例
    DATABASE_PATH = "database/path/to.db"

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
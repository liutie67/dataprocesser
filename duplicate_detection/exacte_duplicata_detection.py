import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from duplicate_detection.hash import hash_file_complet


def save_1file(file_info, conn):
    """
    智能保存文件信息：
    - 如果sha256不存在，插入files
    - 如果sha256已存在，插入duplicates并关联原文件

    :param file_info: 文件信息字典
    :param conn: 数据库连接对象
    :return: 操作结果字典
    """
    sha256 = file_info['sha256']

    try:
        # 尝试插入主表
        cursor = conn.execute('''
            INSERT INTO files (sha256, filename, filepath, filesize)
            VALUES (?, ?, ?, ?)
        ''', (sha256, file_info['filename'], file_info['filepath'], file_info['filesize']))

        file_id = cursor.lastrowid
        conn.commit()
        return {'status': 'unique', 'file_id': file_id}

    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: files.sha256" in str(e):
            # 获取已存在的详细信息进行对比
            original_details = conn.execute(
                'SELECT id, filepath, filesize FROM files WHERE sha256 = ?',
                (sha256,)
            ).fetchone()

            if original_details:
                # 检查文件路径和大小是否完全相同
                if (original_details
                        and original_details[1] == file_info['filepath']
                        and original_details[2] == file_info['filesize']):
                    # 完全相同的文件，跳过插入
                    conn.commit()
                    return {'status': 'skip', 'reason': 'identical_to_original', 'original_id': original_details[0]}
                else:
                    # 检查duplicates表中是否已存在相同路径和大小的重复记录
                    existing_duplicate = conn.execute(
                        '''SELECT id FROM duplicates 
                           WHERE sha256 = ? AND filepath = ?'''
                        , (sha256, file_info['filepath'])
                    ).fetchone()

                    if existing_duplicate:
                        # 重复表中已存在相同路径的记录，跳过插入
                        conn.commit()
                        return {'status': 'skip', 'reason': 'duplicate_already_exists',
                                'duplicate_id': existing_duplicate[0]}
                    else:
                        # 插入副表（不同路径的相同内容文件）
                        conn.execute('''
                            INSERT INTO duplicates 
                            (original_id, sha256, filename, filepath, filesize)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (original_details[0], sha256, file_info['filename'], file_info['filepath'], file_info['filesize']))

                        conn.commit()
                        return {'status': 'duplicate', 'original_file_id': original_details[0]}

        # 其他错误重新抛出
        conn.rollback()
        raise e

def add_files2database(
        db_path,
        target_dir,
        pre_target_dir='',
        num_threads=None,
        use_multithreading=False
):
    """
    多线程将目标文件夹中的文件信息加入数据库，支持SHA256去重

    :param db_path: 数据库路径
    :param target_dir: 入库的文件夹路径
    :param pre_target_dir: 针对每个系统而不同的路径
    :param num_threads: 线程数（None=使用默认线程池线程数）
    :param use_multithreading: 是否使用多线程
    """
    target_dir = os.path.normpath(target_dir)
    pre_target_dir = os.path.normpath(pre_target_dir)
    # 线程本地存储，每个线程有自己的数据库连接
    thread_local = threading.local()

    def get_thread_connection():
        """获取或创建线程专用的数据库连接"""
        if not hasattr(thread_local, 'conn'):
            thread_local.conn = sqlite3.connect(db_path)
            thread_local.conn.execute('PRAGMA journal_mode=WAL')  # 启用WAL模式支持并发
        return thread_local.conn

    def close_thread_connections():
        """关闭所有线程的数据库连接"""
        if hasattr(thread_local, 'conn'):
            thread_local.conn.close()
            delattr(thread_local, 'conn')

    def is_video_file(filename):
        """检查是否为视频文件"""
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp'}
        return os.path.splitext(filename)[1].lower() in video_extensions

    def calculate_sha256(file_path):
        """计算文件的SHA256哈希值"""
        try:
            sha256 = hash_file_complet(file_path)
            return sha256
        except Exception as e:
            print(f"计算哈希值时出错 {file_path}: {e}")
            return None

    def process_file(file_info):
        """处理单个文件并插入数据库，支持SHA256去重"""
        root, filename = file_info
        file_path = os.path.join(root, filename)

        try:
            # 获取文件大小
            file_size = os.path.getsize(os.path.join(pre_target_dir, file_path))

            # 计算SHA256哈希
            sha256_hash = calculate_sha256(os.path.join(pre_target_dir, file_path))
            if sha256_hash is None:
                return {'status': 'error', 'reason': 'hash_failed'}

            # 准备文件信息
            file_data = {
                'sha256': sha256_hash,
                'filename': filename,
                'filepath': file_path,
                'filesize': file_size
            }

            # 获取线程专用的数据库连接并保存文件
            conn = get_thread_connection()
            result = save_1file(file_data, conn)

            return result

        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
            try:
                conn.rollback()
            except:
                pass
            return {'status': 'error', 'reason': str(e)}

    def count_valid_files(directory):
        """统计有效的文件数量"""
        total_files = 0
        for root, dirs, files in os.walk(directory):
            # 过滤掉隐藏的目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            # 统计文件
            total_files += len([f for f in files if not f.startswith('.')])
        return total_files

    def get_all_files_path(directory):
        """获取所有文件路径"""
        path_files = []
        for root, dirs, files in os.walk(directory):
            # 过滤掉包含@的目录和隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if not file.startswith('.'):
                    torecord = os.path.join(os.sep, root)
                    torecord = os.path.relpath(torecord, os.path.join(os.sep, pre_target_dir))
                    path_files.append((torecord, file))
        return path_files

    # 主逻辑
    try:
        # 统计总文件数
        total_files = count_valid_files(os.path.join(pre_target_dir, target_dir))
        if total_files == 0:
            print("未找到任何文件！")
            return

        print(f"找到 {total_files} 个文件。")

        # 获取所有文件路径
        path_all_files = get_all_files_path(os.path.join(pre_target_dir, target_dir))

        # 统计结果
        stats = {
            'unique': 0,
            'duplicate': 0,
            'error': 0,
            'skip': 0
        }

        # 使用进度条
        with tqdm(total=total_files, desc="添加文件到数据库", unit="file") as pbar:
            if use_multithreading and num_threads != 1:
                # 多线程处理
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    # 提交所有任务
                    futures = []
                    for file_info in path_all_files:
                        future = executor.submit(process_file, file_info)
                        future.add_done_callback(lambda x: pbar.update(1))
                        futures.append(future)

                    # 等待所有任务完成并统计结果
                    for future in futures:
                        try:
                            result = future.result()
                            if result['status'] in stats:
                                stats[result['status']] += 1
                        except Exception as e:
                            print(f"任务执行出错: {e}")
                            stats['error'] += 1

            else:
                # 单线程处理
                for file_info in path_all_files:
                    result = process_file(file_info)
                    if result['status'] in stats:
                        stats[result['status']] += 1
                    pbar.update(1)

        # 输出统计结果
        print(f"\n处理完成:")
        print(f"唯一文件: {stats['unique']}")
        print(f"重复文件: {stats['duplicate']}")
        print(f"相同文件: {stats['skip']}")
        print(f"错误文件: {stats['error']}")
        print(f"总计: {stats['unique'] + stats['duplicate'] + stats['error'] + stats['skip']}")

    finally:
        # 确保关闭所有数据库连接
        try:
            close_thread_connections()
        except:
            pass


# 使用示例
if __name__ == "__main__":
    DATABASE_PATH = 'path/to/database'
    toadddir = 'path/to/directory'

    add_files2database(
        db_path=DATABASE_PATH,
        target_dir=toadddir,
        num_threads=4
    )
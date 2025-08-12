import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

from video_crypt.crypt import encrypt_folder_name, decrypt_folder_name, encrypt_file_with_name, decrypt_file_with_name
from video_crypt.key_manager import load_key
from video_crypt.utils import string_to_hash


def copy_with_fixed_random_suffix(
        src_dir,
        dst_dir,
        encrypt=True,
        delete_source=False,
        use_multithreading=False,
        num_threads=None
):
    """
    遍历目录并加密/解密文件，支持删除源文件、多线程。
    :param src_dir: 源目录
    :param dst_dir: 目标目录
    :param encrypt: True=加密，False=解密
    :param delete_source: 是否删除源文件
    :param use_multithreading: 是否使用多线程
    :param num_threads: 线程数（None=使用默认线程池线程数）
    """
    dir_map = {}

    # 统计总任务数（排除隐藏文件）
    total_tasks = sum(
        len(dirs) + len([f for f in files if not f.startswith(".")])
        for _, dirs, files in os.walk(src_dir)
    )

    def process_file(src_file, dst_file, encrypt, delete_source):
        """单个文件处理函数"""
        if encrypt:
            encrypt_file_with_name(src_file, dst_file, load_key())
        else:
            decrypt_file_with_name(src_file, os.path.dirname(dst_file), load_key())
        if delete_source:
            try:
                os.remove(src_file)
            except OSError as e:
                print(f"删除文件失败: {src_file} - {e}")

    with tqdm(total=total_tasks, desc="Processing", unit="item") as pbar:
        for root, dirs, files in os.walk(src_dir):
            # 处理目录
            if root == src_dir:
                new_root = dst_dir
            else:
                parent_src = os.path.dirname(root)
                parent_new = dir_map[parent_src]
                dir_name = os.path.basename(root)
                if encrypt:
                    new_dir_name = encrypt_folder_name(dir_name, load_key())
                else:
                    new_dir_name = decrypt_folder_name(dir_name, load_key())
                new_root = os.path.join(parent_new, new_dir_name)

            dir_map[root] = new_root
            os.makedirs(new_root, exist_ok=True)
            pbar.update(1)

            # 过滤隐藏文件
            visible_files = [f for f in files if not f.startswith(".")]

            if use_multithreading and visible_files:
                # 线程池（可指定线程数）
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    futures = []
                    for f in visible_files:
                        new_name = string_to_hash(f)
                        src_file = os.path.join(root, f)
                        dst_file = os.path.join(new_root, new_name)
                        futures.append(executor.submit(process_file, src_file, dst_file, encrypt, delete_source))
                    for future in futures:
                        future.result()  # 等待任务完成
                        pbar.update(1)
            else:
                # 单线程处理
                for f in visible_files:
                    new_name = string_to_hash(f)
                    src_file = os.path.join(root, f)
                    dst_file = os.path.join(new_root, new_name)
                    process_file(src_file, dst_file, encrypt, delete_source)
                    pbar.update(1)



if __name__ == "__main__":
    # 设置源目录和目标目录
    source_directory = '/some/path/2encrypt'
    target_directory = 'encrypted'
    copy_with_fixed_random_suffix(
        source_directory,
        target_directory,
        encrypt=True,
        use_multithreading=True
    )

    # 设置源目录和目标目录
    source_directory = 'encrypted/some/path'
    target_directory = 'decrypted'
    copy_with_fixed_random_suffix(
        source_directory,
        target_directory,
        encrypt=False,
        use_multithreading=True
    )

    print("处理完成!")
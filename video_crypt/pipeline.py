import os
from tqdm import tqdm

from video_crypt.crypt import encrypt_folder_name, decrypt_folder_name, encrypt_file_with_name, decrypt_file_with_name
from video_crypt.key_manager import load_key
from video_crypt.utils import string_to_hash


def copy_with_fixed_random_suffix(src_dir, dst_dir, encrypt=True):
    # 用字典保存目录映射：原目录绝对路径 -> 新目录绝对路径
    dir_map = {}

    # 1. 统计总任务数（文件夹+文件）
    total_tasks = sum(len(dirs) + len(files) for _, dirs, files in os.walk(src_dir))

    with tqdm(total=total_tasks, desc="Processing", unit="item") as pbar:
        # 遍历源目录
        for root, dirs, files in os.walk(src_dir):
            if root == src_dir:
                # 根目录特殊处理
                new_root = dst_dir
            else:
                # 父目录新路径
                parent_src = os.path.dirname(root)
                parent_new = dir_map[parent_src]

                # 当前目录名加固定随机数
                dir_name = os.path.basename(root)
                if encrypt:
                    new_dir_name = encrypt_folder_name(dir_name, load_key())
                else:
                    new_dir_name = decrypt_folder_name(dir_name, load_key())

                # 当前目录的新路径
                new_root = os.path.join(parent_new, new_dir_name)

            # 保存映射并创建目录
            dir_map[root] = new_root
            os.makedirs(new_root, exist_ok=True)
            pbar.update(1)

            # 处理文件
            for f in files:
                # name, ext = os.path.splitext(f)
                new_name = string_to_hash(f)
                src_file = os.path.join(root, f)
                dst_file = os.path.join(new_root, new_name)
                if encrypt:
                    encrypt_file_with_name(src_file, dst_file, load_key())
                else:
                    decrypt_file_with_name(src_file, new_root, load_key())
                pbar.update(1)


if __name__ == "__main__":
    # 设置源目录和目标目录
    source_directory = 'encrypted'
    target_directory = 'decrypted'

    # 验证源目录是否存在
    if not os.path.isdir(source_directory):
        print(f"错误: 源目录 '{source_directory}' 不存在!")
        exit(1)

    # 调用函数处理
    copy_with_fixed_random_suffix(source_directory, target_directory)
    copy_with_fixed_random_suffix(target_directory, 'back_decrypted', encrypt=False)
    print("处理完成!")
import os
import shutil
import random
from pathlib import Path


def move_files_by_count(source_dir, dest_dir, file_count, file_extensions=None, exclude_hidden=True):
    """
    从源目录移动指定数量的文件到目标目录

    参数:
        source_dir (str): 源目录路径
        dest_dir (str): 目标目录路径
        file_count (int): 要移动的文件数量
        file_extensions (list, optional): 指定文件扩展名列表
        exclude_hidden (bool): 是否排除隐藏文件（以.开头的文件）

    返回:
        dict: 包含移动结果信息的字典
    """

    # 确保目标目录存在
    Path(dest_dir).mkdir(parents=True, exist_ok=True)

    # 验证源目录是否存在
    if not os.path.exists(source_dir):
        raise ValueError(f"源目录不存在: {source_dir}")

    # 收集所有符合条件的文件
    all_files = collect_files(source_dir, file_extensions, exclude_hidden)

    print(f"找到 {len(all_files)} 个符合条件的文件")

    # 检查是否有足够的文件
    if len(all_files) < file_count:
        print(f"警告: 源目录中只有 {len(all_files)} 个文件，少于请求的 {file_count} 个")
        file_count = len(all_files)

    # 移动文件
    return move_files(all_files[:file_count], dest_dir, file_count)


def move_random_files(source_dir, dest_dir, file_count, file_extensions=None, exclude_hidden=True, random_seed=None):
    """
    随机移动指定数量的文件到目标目录
    """
    if random_seed is not None:
        random.seed(random_seed)

    # 收集所有符合条件的文件
    all_files = collect_files(source_dir, file_extensions, exclude_hidden)

    print(f"找到 {len(all_files)} 个文件，随机选择 {min(file_count, len(all_files))} 个")

    # 随机打乱文件列表并选择前 file_count 个
    random.shuffle(all_files)
    selected_files = all_files[:file_count]

    # 移动选中的文件
    return move_files(selected_files, dest_dir, file_count)


def collect_files(source_dir, file_extensions=None, exclude_hidden=True):
    """
    收集目录中所有符合条件的文件
    """
    all_files = []

    for root, dirs, files in os.walk(source_dir):
        # 过滤隐藏文件和目录
        if exclude_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

        for file in files:
            file_path = os.path.join(root, file)

            if exclude_hidden and os.path.basename(file_path).startswith('.'):
                continue

            # 检查文件扩展名
            if file_extensions:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext not in [ext.lower() for ext in file_extensions]:
                    continue

            # 确保是文件而不是目录
            if os.path.isfile(file_path):
                all_files.append(file_path)

    return all_files


def move_files(files_to_move, dest_dir, total_count):
    """
    移动文件列表到目标目录
    """

    # 确保目标目录存在
    Path(dest_dir).mkdir(parents=True, exist_ok=True)

    moved_files = []
    skipped_files = []

    for i, file_path in enumerate(files_to_move):
        try:
            # 获取文件名
            filename = os.path.basename(file_path)

            # 检查源文件是否存在
            if not os.path.exists(file_path):
                print(f"文件不存在: {file_path}")
                skipped_files.append(file_path)
                continue

            # 检查文件大小，避免移动空文件或系统文件
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                print(f"跳过空文件: {file_path}")
                skipped_files.append(file_path)
                continue

            dest_path = os.path.join(dest_dir, filename)

            # 处理文件名冲突
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_dir, f"{base_name}_{counter}{ext}")
                counter += 1

            # 移动文件
            print(f"正在移动 ({i + 1}/{total_count}): {filename}", end='\t')
            shutil.move(file_path, dest_path)

            # 验证移动是否成功
            if os.path.exists(dest_path) and not os.path.exists(file_path):
                moved_files.append({
                    'original_path': file_path,
                    'new_path': dest_path,
                    'filename': filename,
                    'size': file_size
                })
                print(f"✓ 成功移动: {filename}")
            else:
                print(f"✗ 移动验证失败: {filename}")
                skipped_files.append(file_path)

        except Exception as e:
            print(f"✗ 移动文件失败 {os.path.basename(file_path)}: {e}")
            skipped_files.append(file_path)

    # 返回结果信息
    result = {
        'total_moved': len(moved_files),
        'total_skipped': len(skipped_files),
        'moved_files': moved_files,
        'skipped_files': skipped_files,
        'dest_dir': dest_dir
    }

    print(f"\n移动完成!")
    print(f"成功移动: {len(moved_files)} 个文件")
    print(f"跳过文件: {len(skipped_files)} 个")
    print(f"目标目录: {dest_dir}")

    return result


# 使用示例和测试
if __name__ == "__main__":
    source_path = "/Volumes/commune/aenfer"
    dest_path = "/Volumes/commune/ready"

    # 方法1: 顺序移动前20个文件
    print("=== 顺序移动文件 ===")
    result1 = move_files_by_count(
        source_dir=source_path,
        dest_dir=dest_path,
        file_count=20,
        exclude_hidden=True
    )

    # 方法2: 随机移动20个文件
    print("\n=== 随机移动文件 ===")
    result2 = move_random_files(
        source_dir=source_path,
        dest_dir=dest_path + "_random",  # 使用不同的目标目录
        file_count=20,
        exclude_hidden=True,
        random_seed=42  # 设置随机种子以便结果可重现
    )

    # 方法3: 只随机移动视频文件
    print("\n=== 随机移动视频文件 ===")
    result3 = move_random_files(
        source_dir=source_path,
        dest_dir=dest_path + "_videos",
        file_count=15,
        file_extensions=['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'],
        exclude_hidden=True
    )
import os
from pathlib import Path

def remove_empty_folders(target_dir):
    """
    遍历目标目录的所有子文件夹，删除所有空文件夹
    忽略.DS_Store文件的存在（如果文件夹中只有.DS_Store，也会被删除）

    参数:
        target_dir (str or Path): 要清理的目标目录路径，可以是字符串或Path对象
    """
    # 转换为Path对象以便统一处理
    target_path = Path(target_dir) if isinstance(target_dir, str) else target_dir
    if not target_path.exists() or not target_path.is_dir():
        print(f"目标目录不存在或不是目录: {target_dir}")
        return

    deleted_count = 0

    # 使用os.walk遍历所有子目录（从最深层开始向上遍历）
    for root, dirs, files in os.walk(target_path, topdown=False):
        # 检查当前目录是否为空（忽略.DS_Store文件）
        relevant_files = [f for f in files if f != '.DS_Store']
        relevant_dirs = dirs  # 子目录会在遍历时被处理

        # 如果当前目录没有文件（除了.DS_Store）且没有子目录
        if len(relevant_files) == 0 and len(relevant_dirs) == 0:
            try:
                # 删除空目录
                ds_store_path = os.path.join(root, '.DS_Store')
                if os.path.exists(ds_store_path) and os.path.isfile(ds_store_path):
                    os.unlink(ds_store_path)
                os.rmdir(root)
                print(f"已删除空文件夹: {root}")
                deleted_count += 1
            except OSError as e:
                print(f"无法删除文件夹 {root}: {e}")

    print(f"清理完成，共删除了 {deleted_count} 个空文件夹")


def get_dir_size(folder) -> int:
    """
    获取文件夹的总大小
    Args:
        folder: 可以是字符串路径或Path对象
    Returns:
        int: 文件夹的总大小（字节）
    """
    folder = Path(folder)
    total_size = 0

    if not folder.exists():
        print(f"路径不存在: {folder}")
        return 0

    if not folder.is_dir():
        print(f"路径不是文件夹: {folder}")
        return 0

    try:
        for item in folder.rglob('*'):
            if item.is_file() and not item.name.startswith('.'):
                try:
                    total_size += item.stat().st_size
                except (OSError, PermissionError) as e:
                    print(f"无法访问文件 {item}: {e}")
                    continue
    except (OSError, PermissionError) as e:
        print(f"无法遍历文件夹 {folder}: {e}")

    return total_size


# 使用示例
if __name__ == "__main__":
    target_directory = "apartition"  # 替换为你的目标目录
    remove_empty_folders(target_directory)
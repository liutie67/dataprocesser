import shutil
from pathlib import Path
from typing import List, Tuple
import time

from folder_partition.utiles import remove_empty_folders, get_dir_size


def split_folder_by_size(folderpath: str, threshsize: float=20, use_decimal=True) -> List[Path]:
    """
    将目标文件夹内的所有子文件夹切分成大小不超过阈值的小文件夹

    参数:
    folderpath (str): 目标文件夹路径
    threshsize (float): 阈值大小，单位GB，默认20GB

    返回:
    list: 包含所有创建的分割文件夹路径的列表
    """

    # 转换GB为字节（使用1024进制）
    if use_decimal:
        threshold = threshsize * 1000 * 1000 * 1000
    else:
        threshold = threshsize * 1024 * 1024 * 1024

    # 确保目标文件夹存在
    folderpath = Path(folderpath)
    if not folderpath.exists() or not folderpath.is_dir():
        raise ValueError(f"目标文件夹不存在或不是文件夹: {folderpath}")

    remove_empty_folders(folderpath)

    print(f"开始处理文件夹: {folderpath}")
    print(f"阈值: {threshsize}GB ({threshold / 1024 / 1024 / 1024:.2f}GB)")

    # 只处理目标文件夹的直接子文件夹，不处理目标文件夹本身
    created_folders = []
    for item in folderpath.iterdir():
        if item.is_dir() and not item.name.startswith('.') and not _is_temp_folder(item):
            created_folders.extend(_process_folder_recursive(item, int(threshold), is_root=True))
    print(f"\n处理完成！共创建了 {len(created_folders)} 个分割文件夹")

    remove_empty_folders(folderpath)

    return created_folders


def _process_folder_recursive(folder: Path, threshold: int, is_root: bool = False) -> List[Path]:
    """
    递归处理文件夹，自底向上确保所有文件夹都不超过阈值
    """
    created_folders = []

    # 首先递归处理所有子文件夹
    for item in list(folder.iterdir()):  # 使用list避免迭代时修改
        if item.is_dir() and not item.name.endswith('.rtfd'):
            # 跳过已创建的分割文件夹和临时文件夹
            if not (_is_split_folder(item) or _is_temp_folder(item)):
                created_folders.extend(_process_folder_recursive(item, threshold))

    # 处理完所有子文件夹后，处理当前文件夹
    # 对于根级子文件夹，我们进行处理；对于其他情况，按原逻辑处理
    if not is_root or (is_root and folder.parent.name != folder.name):
        current_created = _process_current_folder(folder, threshold, is_root)

        created_folders.extend(current_created)

    return created_folders


def _process_current_folder(folder: Path, threshold: int, is_root: bool = False) -> List[Path]:
    """
    处理当前文件夹，确保其内容不超过阈值
    """
    created_folders = []

    # 获取当前文件夹中的所有项目
    items = []
    for item in folder.iterdir():
        if not item.name.startswith('.'):
            if (item.is_file() or item.is_dir()) and not _is_temp_folder(item):
                items.append(item)

    if not items:
        return created_folders

    # 计算当前文件夹总大小
    folder_size = get_dir_size(folder)

    if folder_size <= threshold:
        # 当前文件夹不需要分割
        return created_folders

    print(f"\n需要分割文件夹: {folder.name} (大小: {folder_size / 1024 / 1024 / 1024:.2f}GB)")

    # 计算每个项目的大小并排序（从大到小）
    item_sizes = []
    for item in items:
        size = _get_item_size(item)
        item_sizes.append((item, size, item.name))

    # 按大小降序排序
    item_sizes.sort(key=lambda x: x[1], reverse=True)

    # 检查是否有单个项目超过阈值
    oversized_items = [(item, size) for item, size, name in item_sizes if size > threshold]
    for item, size in oversized_items:
        print(f"警告: {item.name} 的大小 ({size / 1024 / 1024 / 1024:.2f}GB) 超过阈值")

    # 分割逻辑 - 使用优化的装箱算法
    parts = _optimized_bin_packing(item_sizes, threshold)

    if len(parts) <= 1:
        # 不需要分割或无法分割
        return created_folders

    # 创建分割文件夹并移动项目
    base_name = folder.name
    for i, part_items in enumerate(parts, 1):
        if i == 1 and len(parts) == 1:
            # 只有一个部分，不需要分割
            continue

        part_name = f"{base_name}(part{i})"
        part_folder = folder.parent / part_name
        part_folder.mkdir(exist_ok=True)
        created_folders.append(part_folder)

        print(f"  创建分割文件夹: {part_name}")

        # 移动项目到分割文件夹
        for item, size, name in part_items:
            destination = part_folder / item.name
            if item.exists():
                try:
                    if item.is_file():
                        shutil.move(str(item), str(destination))
                    elif item.is_dir():
                        shutil.move(str(item), str(destination))
                    print(f"    移动: {item.name} -> {part_name}/")
                except Exception as e:
                    print(f"    移动失败 {item.name}: {e}")

        # 检查是否只有一个子文件夹，如果是则提前内容
        part_folder = _flatten_single_subfolder(part_folder)
    try:
        ds_store = folder / ".DS_Store"
        ds_store.unlink(missing_ok=True)
        folder.rmdir()
        print(f"成功删除空目录: {folder}")
    except OSError as e:
        print(f"删除失败: {e}")

    return created_folders


def _optimized_bin_packing(item_sizes: List[Tuple[Path, int, str]], threshold: int) -> List[
    List[Tuple[Path, int, str]]]:
    """
    使用优化的装箱算法进行分割
    """
    # 移除超过阈值的单个项目（它们需要单独处理）
    valid_items = [(item, size, name) for item, size, name in item_sizes if size <= threshold]
    oversized_items = [(item, size, name) for item, size, name in item_sizes if size > threshold]

    parts = []

    # 首先处理超大项目，每个单独一个部分
    for item_info in oversized_items:
        parts.append([item_info])

    # 对有效项目使用最佳适应递减算法
    valid_items.sort(key=lambda x: x[1], reverse=True)  # 从大到小排序

    for item_info in valid_items:
        item, size, name = item_info
        placed = False

        # 尝试放入现有的部分
        for part in parts:
            part_size = sum(size for _, size, _ in part)
            if part_size + size <= threshold:
                part.append(item_info)
                placed = True
                break

        # 如果不能放入现有部分，创建新部分
        if not placed:
            parts.append([item_info])

    return parts


def _flatten_single_subfolder(folder: Path) -> Path:
    """
    如果文件夹中只有一个子文件夹，则将子文件夹内容提前
    """
    try:
        items = list(folder.iterdir())
        # 过滤掉隐藏文件
        items = [item for item in items if not item.name.startswith('.')]

        if len(items) == 1 and items[0].is_dir():
            single_subfolder = items[0]
            subfolder_items = list(single_subfolder.iterdir())
            # 过滤掉隐藏文件
            subfolder_items = [item for item in subfolder_items if not item.name.startswith('.')]

            if subfolder_items:  # 确保子文件夹非空
                print(f"    扁平化: {folder.name} -> {single_subfolder.name}")

                # dest_folder = folder.parent / f"{folder.name}-{single_subfolder.name}"
                # dest_folder.mkdir(exist_ok=True)
                # 移动子文件夹中的所有内容到父文件夹
                for item in subfolder_items:
                    destination = folder / item.name
                    if not destination.exists():
                        shutil.move(str(item), str(destination))

                # 删除空的子文件夹
                ds_store = single_subfolder / ".DS_Store"
                ds_store.unlink(missing_ok=True)
                single_subfolder.rmdir()
                print(f"成功删除空目录: {folder}")

                # 重命名文件夹
                new_name = f"{folder.name}-{single_subfolder.name}"
                new_path = folder.parent / new_name
                if not new_path.exists():
                    shutil.move(str(folder), str(new_path))
                    return new_path

    except Exception as e:
        print(f"    扁平化失败 {folder.name}: {e}")

    return folder


def _get_item_size(item: Path) -> int:
    """
    获取文件或文件夹的大小
    """
    try:
        if item.is_file():
            return item.stat().st_size
        elif item.is_dir():
            return get_dir_size(item)
    except Exception as e:
        print(f"无法获取大小 {item}: {e}")
    return 0


def _is_split_folder(item: Path) -> bool:
    """检查是否为分割文件夹"""
    return item.is_dir() and ('(part' in item.name or item.name.startswith('split_part_'))


def _is_temp_folder(item: Path) -> bool:
    """检查是否为临时文件夹"""
    return item.is_dir() and (item.name.startswith('.') or item.name == '__pycache__')


def _display_size(size_bytes: int) -> str:
    """
    将字节数转换为易读的格式
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def verify_folder_sizes(folderpath: str, threshsize: float = 20, scale: int = 1000) -> bool:
    """
    验证文件夹中的所有项目都不超过阈值
    """
    threshold = threshsize * scale * scale * scale
    folderpath = Path(folderpath)

    all_valid = True
    for item in folderpath.rglob('*'):
        if item.is_dir() and not _is_temp_folder(item):
            size = get_dir_size(item)
            if size > threshold:
                print(f"错误: {item} 大小 {_display_size(size)} 超过阈值")
                all_valid = False

    return all_valid

# 使用示例
if __name__ == "__main__":
    try:
        target_folder = "apartition"  # 替换为实际路径
        # 处理文件夹
        result = split_folder_by_size(target_folder, threshsize=10)  # 10GB阈值
        # 验证结果
        print("\n验证结果...")
        if verify_folder_sizes(target_folder, 10):
            print("✓ 所有文件夹大小都不超过阈值")
        else:
            print("✗ 存在超过阈值的文件夹")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

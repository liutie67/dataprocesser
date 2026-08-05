"""按图片尺寸整理门架数据。

分类规则与 PaddleDetection/tools/sort_gantry_images.ps1 保持一致。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TypeAlias

from PIL import Image


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
CATEGORIES = ("front_view", "side_view", "plate_crop", "unclassified")
Counts: TypeAlias = dict[str, int]


def _new_counts() -> Counts:
    return {
        "front_view": 0,
        "side_view": 0,
        "plate_crop": 0,
        "unclassified": 0,
        "skipped": 0,
        "failed": 0,
    }


def _classify_image(width: int, height: int) -> str:
    if width <= 500 and height <= 200:
        return "plate_crop"
    if width == 4096 and height == 2160:
        return "front_view"
    if height == 1920 and width >= 1000:
        return "side_view"
    return "unclassified"


def _next_available_path(path: Path) -> Path:
    """返回不重名的路径，在文件名末尾依次追加 1、2、3……。"""
    if not path.exists():
        return path

    number = 1
    while True:
        candidate = path.with_name(f"{path.stem}{number}{path.suffix}")
        if not candidate.exists():
            return candidate
        number += 1


def sort_gantry_images(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    move: bool = False,
    category_first: bool = False,
) -> Counts:
    """整理一个数据文件夹中的图片。

    图片会递归扫描，并输出到：
    ``output_dir/源相对目录/分类名/图片名``。

    Args:
        input_dir: 待处理的文件夹。
        output_dir: 分类结果的输出文件夹。
        move: 为 True 时移动文件；默认复制文件。
        category_first: 为 True 时将分类目录放在输出路径的最前面，并在
            分类目录下保留原相对路径；默认保持原保存结构。

    Returns:
        各分类成功处理数，以及 skipped、failed 数量。
    """
    source_root = Path(input_dir).expanduser().resolve()
    destination_root = Path(output_dir).expanduser().resolve()

    if not source_root.is_dir():
        raise NotADirectoryError(f"输入文件夹不存在或不是文件夹：{source_root}")
    if source_root == destination_root:
        raise ValueError("输入文件夹和输出文件夹不能相同")

    counts = _new_counts()
    image_paths: list[Path] = []
    destination_is_inside_source = destination_root.is_relative_to(source_root)

    for path in source_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        # 输出目录位于输入目录内时，不重复扫描已经生成的结果。
        if destination_is_inside_source and path.is_relative_to(destination_root):
            continue

        relative_path = path.relative_to(source_root)
        if any(part in CATEGORIES for part in relative_path.parts[:-1]):
            continue
        image_paths.append(path)

    image_paths.sort()

    for image_path in image_paths:
        try:
            with Image.open(image_path) as image:
                width, height = image.size

            category = _classify_image(width, height)
            relative_parent = image_path.relative_to(source_root).parent
            if category_first:
                destination = (
                    destination_root
                    / category
                    / relative_parent
                    / image_path.name
                )
            else:
                destination = (
                    destination_root / relative_parent / category / image_path.name
                )

            if category_first:
                destination = _next_available_path(destination)
            elif destination.exists():
                counts["skipped"] += 1
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            if move:
                shutil.move(str(image_path), str(destination))
            else:
                shutil.copy2(image_path, destination)
            counts[category] += 1
        except Exception as exc:  # 单个坏文件不应中断整批数据处理
            counts["failed"] += 1
            print(f"处理失败：{image_path}：{exc}")

    return counts


def sort_gantry_image_folders(
    input_root: str | Path,
    output_root: str | Path,
    *,
    move: bool = False,
    merge_categories: bool = False,
) -> dict[str, Counts]:
    """批量处理 ``input_root`` 下的所有一级子文件夹。

    默认每个子文件夹独立调用 :func:`sort_gantry_images`，输出到
    ``output_root/子文件夹名``。当 ``merge_categories=True`` 时，所有
    子文件夹的结果合并到同一级分类目录：
    ``output_root/分类名/原相对路径/图片名``。若目标文件重名，则在文件名
    末尾依次添加 1、2、3……。
    """
    source_root = Path(input_root).expanduser().resolve()
    destination_root = Path(output_root).expanduser().resolve()

    if not source_root.is_dir():
        raise NotADirectoryError(f"输入根目录不存在或不是文件夹：{source_root}")
    if source_root == destination_root:
        raise ValueError("输入根目录和输出根目录不能相同")

    results: dict[str, Counts] = {}
    folders = sorted(path for path in source_root.iterdir() if path.is_dir())
    for folder in folders:
        if folder == destination_root:
            continue
        print(f"正在处理：{folder}")
        results[folder.name] = sort_gantry_images(
            folder,
            destination_root if merge_categories else destination_root / folder.name,
            move=move,
            category_first=merge_categories,
        )
    return results


def _print_counts(name: str, counts: Counts) -> None:
    print(f"\n{name}")
    print(f"  Front view:    {counts['front_view']}")
    print(f"  Side view:     {counts['side_view']}")
    print(f"  Plate crop:    {counts['plate_crop']}")
    print(f"  Unclassified:  {counts['unclassified']}")
    print(f"  Already exist: {counts['skipped']}")
    print(f"  Failed:        {counts['failed']}")


if __name__ == "__main__":
    # ==================== 直接修改以下配置 ====================
    INPUT_PATH = r"path\to\ip"
    OUTPUT_PATH = r"path\to\op"

    # True：处理 INPUT_PATH 下的所有一级子文件夹（函数2）
    # False：仅处理 INPUT_PATH 这一个文件夹（函数1）
    BATCH_MODE = True

    # False：复制文件；True：移动文件
    MOVE_FILES = False

    # 仅批量模式生效：
    # False：按原一级文件夹分别保存（默认）
    # True：合并到同一级 front_view、side_view、plate_crop、unclassified 目录
    MERGE_CATEGORIES = True
    # =========================================================

    if BATCH_MODE:
        batch_results = sort_gantry_image_folders(
            INPUT_PATH,
            OUTPUT_PATH,
            move=MOVE_FILES,
            merge_categories=MERGE_CATEGORIES,
        )
        for input_folder_name, folder_counts in batch_results.items():
            _print_counts(input_folder_name, folder_counts)
    else:
        single_counts = sort_gantry_images(
            INPUT_PATH,
            OUTPUT_PATH,
            move=MOVE_FILES,
        )
        _print_counts(str(Path(INPUT_PATH).resolve()), single_counts)

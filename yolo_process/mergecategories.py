"""
Step 4 rewritelabel.py

给我python代码，将指定images_0文件夹的所有图片复制到另一个images_1文件夹，同名的图片则跳过。
同样指定labels_0文件夹的.txt标签文件也复制到labels_1文件夹，但是同名的txt文件合并，
每个txt文件的一行是一个标记，
"""

import os
import shutil
import random
from tqdm import tqdm  # 导入进度条库


def copy_images(src_images, dst_images, nums=0, seed=None):
    """随机复制图片，跳过同名文件
    :param nums: 要移动的图片数量，0表示全部
    :param seed: 随机数种子，用于复现结果
    """
    if not os.path.exists(dst_images):
        os.makedirs(dst_images)

    if seed is not None:
        random.seed(seed)

    # 获取所有图片文件并随机排序
    all_files = [f for f in os.listdir(src_images) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]

    if nums > 0 and nums < len(all_files):
        selected_files = random.sample(all_files, nums)
    else:
        selected_files = all_files

    copied_count = 0
    skipped_count = 0

    # 处理选中的文件（使用tqdm显示进度）
    for filename in tqdm(selected_files, desc="复制图片进度"):
        src_path = os.path.join(src_images, filename)
        dst_path = os.path.join(dst_images, filename)

        if not os.path.exists(dst_path):
            shutil.copy2(src_path, dst_path)
            copied_count += 1
        else:
            skipped_count += 1

    print(f"图片复制完成: 新增 {copied_count} 张, 跳过 {skipped_count} 张")
    return selected_files  # 返回实际处理的文件列表


def merge_labels(src_labels, dst_labels, processed_files, seed=None):
    """合并标签文件，同名文件则追加内容
    :param processed_files: 已处理的图片文件名列表（用于匹配对应的标签文件）
    :param seed: 随机数种子（这里主要用于保持一致性，虽然标签处理顺序不影响结果）
    """
    if not os.path.exists(dst_labels):
        os.makedirs(dst_labels)

    if seed is not None:
        random.seed(seed + 1)  # 使用不同的种子值避免与图片选择相同

    merged_count = 0
    created_count = 0

    # 根据图片文件名获取对应的标签文件名（去掉扩展名加上.txt）
    label_files = []
    for img_file in processed_files:
        base_name = os.path.splitext(img_file)[0] + '.txt'
        src_path = os.path.join(src_labels, base_name)
        if os.path.exists(src_path):
            label_files.append(base_name)

    # 处理标签文件（使用tqdm显示进度）
    for filename in tqdm(label_files, desc="合并标签进度"):
        src_path = os.path.join(src_labels, filename)
        dst_path = os.path.join(dst_labels, filename)

        # 读取源文件内容
        with open(src_path, 'r') as f:
            src_lines = set(f.readlines())  # 使用set去重

        if os.path.exists(dst_path):
            # 如果目标文件存在，读取现有内容
            with open(dst_path, 'r') as f:
                existing_lines = set(f.readlines())

            # 合并内容并去重
            merged_lines = existing_lines.union(src_lines)

            # 写回文件
            with open(dst_path, 'w') as f:
                f.writelines(sorted(merged_lines))  # 排序使结果一致

            merged_count += 1
        else:
            # 目标文件不存在，直接复制
            with open(dst_path, 'w') as f:
                f.writelines(sorted(src_lines))

            created_count += 1

    print(f"标签合并完成: 合并 {merged_count} 个, 新增 {created_count} 个")


if __name__ == "__main__":
    path_0 = './fire-smoke/smoke'
    path_1 = './fire-smoke/combined-15000'
    nums = 2122  # 设置要移动合并的数量，0表示全部
    seed = 6  # 设置随机数种子，None表示不固定随机性

    # 使用示例
    images_0 = os.path.join(path_0, 'images')  # 源图片文件夹
    images_1 = os.path.join(path_1, 'images')  # 目标图片文件夹
    labels_0 = os.path.join(path_0, 'labels')  # 源标签文件夹
    labels_1 = os.path.join(path_1, 'labels')  # 目标标签文件夹

    # 执行复制和合并
    processed_files = copy_images(images_0, images_1, nums, seed)
    merge_labels(labels_0, labels_1, processed_files, seed)
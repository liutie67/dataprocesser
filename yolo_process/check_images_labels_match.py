"""
Step 2

数据集匹配检查模块

功能：检查并清理images和labels文件夹中不匹配的图像和标签文件
确保数据集中的每个图片都有对应的标签文件，每个标签文件都有对应的图片

作者：LIU Tie
版本：2.0
日期：2025-12-05
"""

import os
import shutil
import argparse


def check_mismatches(source_dir, mode='sep'):
    """
    检查数据集中的图像和标签匹配情况，并提供交互式的删除或归档选项。

    该函数扫描指定目录下的 'images' 和 'labels' 文件夹，找出不匹配的文件对。
    如果发现不匹配项，程序将暂停并询问用户如何处理（删除、移动归档或忽略）。

    Parameters
    ----------
    source_dir : str
        包含 'images' 和 'labels' 子文件夹的数据集根目录路径。
    mode : str, optional
        文件组织模式。'sep' 表示图片和标签分开存放（默认）。
        目前仅支持 'sep' 模式。

    Returns
    -------
    tuple
        包含两个集合的元组 (images_without_labels, labels_without_images)：
        - images_without_labels : set
            存在图片但缺少对应标签的文件名集合（不含扩展名）。
        - labels_without_images : set
            存在标签但缺少对应图片的文件名集合（不含扩展名）。

    Raises
    ------
    FileNotFoundError
        当指定的 source_dir 或其子文件夹 images/labels 不存在时抛出。

    Examples
    --------
    >>> # 运行函数，根据提示输入 'd' 删除或 'm' 移动
    >>> unmatched_imgs, unmatched_lbls = check_mismatches('./my_dataset')
    """
    # 定义基础路径
    images_dir = os.path.join(source_dir, 'images')
    labels_dir = os.path.join(source_dir, 'labels')

    # 路径检查
    if not os.path.exists(images_dir):
        raise FileNotFoundError(f"错误: images文件夹不存在于 {source_dir}")
    if not os.path.exists(labels_dir):
        raise FileNotFoundError(f"错误: labels文件夹不存在于 {source_dir}")

    print(f"🔍 开始检查数据集: {source_dir}")
    print(f"📁 图片目录: {images_dir}")
    print(f"📁 标签目录: {labels_dir}")

    # 获取文件列表 (仅根据文件名匹配，忽略大小写)
    # 假设图片为 .jpg, 标签为 .txt (基于原代码逻辑)
    image_files = {os.path.splitext(f)[0] for f in os.listdir(images_dir)
                   if f.lower().endswith('.jpg')}
    label_files = {os.path.splitext(f)[0] for f in os.listdir(labels_dir)
                   if f.lower().endswith('.txt')}

    print(f"📊 统计信息:")
    print(f"   - 图片文件数量: {len(image_files)}")
    print(f"   - 标签文件数量: {len(label_files)}")

    # 计算差集
    images_without_labels = image_files - label_files
    labels_without_images = label_files - image_files

    # -------------------------------------------------
    # 结果展示
    # -------------------------------------------------
    print("\n" + "=" * 50)
    print("📋 检查结果:")
    print("=" * 50)

    has_mismatch = False

    if images_without_labels:
        has_mismatch = True
        print(f"❌ 有图片但无标签 (No Labels): {len(images_without_labels)} 个")
        # 仅显示前5个作为示例，避免刷屏
        for i, file in enumerate(sorted(images_without_labels)):
            if i < 5: print(f"   - {file}.jpg")
        if len(images_without_labels) > 5: print("   ... 等")
    else:
        print("✅ 所有图片都有对应的标签")

    print("-" * 30)

    if labels_without_images:
        has_mismatch = True
        print(f"❌ 有标签但无图片 (No Images): {len(labels_without_images)} 个")
        for i, file in enumerate(sorted(labels_without_images)):
            if i < 5: print(f"   - {file}.txt")
        if len(labels_without_images) > 5: print("   ... 等")
    else:
        print("✅ 所有标签都有对应的图片")

    # -------------------------------------------------
    # 交互处理逻辑
    # -------------------------------------------------
    if not has_mismatch:
        print("\n🎉 完美! 数据集一一对应，无需处理。")
        return images_without_labels, labels_without_images

    print("\n" + "=" * 50)
    print("⚠️  发现不匹配文件，请选择操作:")
    print("   [d] : 删除 (Delete) 所有不匹配的文件")
    print("   [m] : 移动 (Move) 到同级 nolabels/noimages 文件夹")
    print("   [n] : 不做任何操作 (No action)")

    choice = input("\n👉 请输入您的选择 (d/m/n): ").strip().lower()

    if choice == 'd':
        print("\n🗑️  正在删除文件...")
        cnt = 0
        # 删除图片
        for file in images_without_labels:
            try:
                os.remove(os.path.join(images_dir, f"{file}.jpg"))
                cnt += 1
            except OSError as e:
                print(f"   删除失败: {file}.jpg - {e}")

        # 删除标签
        for file in labels_without_images:
            try:
                os.remove(os.path.join(labels_dir, f"{file}.txt"))
                cnt += 1
            except OSError as e:
                print(f"   删除失败: {file}.txt - {e}")
        print(f"✨ 已删除 {cnt} 个文件。")

    elif choice == 'm':
        print("\n📦 正在移动文件...")
        # 定义移动的目标文件夹
        # "nolabels" 存放没有标签的图片
        target_no_labels = os.path.join(source_dir, 'nolabels')
        # "noimages" 存放没有图片的标签
        target_no_images = os.path.join(source_dir, 'noimages')

        # 确保目标文件夹存在
        if images_without_labels and not os.path.exists(target_no_labels):
            os.makedirs(target_no_labels)
            print(f"   创建文件夹: {target_no_labels}")

        if labels_without_images and not os.path.exists(target_no_images):
            os.makedirs(target_no_images)
            print(f"   创建文件夹: {target_no_images}")

        cnt = 0
        # 移动图片
        for file in images_without_labels:
            src = os.path.join(images_dir, f"{file}.jpg")
            dst = os.path.join(target_no_labels, f"{file}.jpg")
            try:
                shutil.move(src, dst)
                cnt += 1
            except Exception as e:
                print(f"   移动失败: {file}.jpg - {e}")

        # 移动标签
        for file in labels_without_images:
            src = os.path.join(labels_dir, f"{file}.txt")
            dst = os.path.join(target_no_images, f"{file}.txt")
            try:
                shutil.move(src, dst)
                cnt += 1
            except Exception as e:
                print(f"   移动失败: {file}.txt - {e}")
        print(f"✨ 已移动 {cnt} 个文件到备份目录。")

    else:
        print("\n🛑 操作已取消，未修改任何文件。")

    return images_without_labels, labels_without_images


if __name__ == "__main__":
    # 直接运行时的测试用例
    path = './fire-smoke/combined'

    try:
        missing_images, missing_labels = check_mismatches(path)

    except FileNotFoundError as e:
        print(f"❌ 目录不存在: {e}")
    except Exception as e:
        print(f"❌ 执行过程中发生错误: {e}")
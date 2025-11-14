"""
Step 2

数据集匹配检查模块

功能：检查并清理images和labels文件夹中不匹配的图像和标签文件
确保数据集中的每个图片都有对应的标签文件，每个标签文件都有对应的图片

作者：LIU Tie
版本：1.0
日期：2025-11-14
"""

import os
import argparse


def check_and_clean_dataset(folder_name, delete=False, mode='sep'):
    """
    检查并清理不匹配的图像和标签文件。

    该函数会：
    1. 检查指定目录下的images和labels文件夹
    2. 找出没有对应标签的图片文件
    3. 找出没有对应图片的标签文件
    4. 可选删除这些不匹配的文件

    Args:
        folder_name (str): 包含images和labels文件夹的父目录路径
        delete (bool): 是否直接删除不匹配的文件，默认为False（只显示不删除）
        mode (str): 文件组织模式，'sep'表示图片和标签分开存放（默认），
                   'tog'表示图片和标签在同一目录（当前版本仅支持'sep'模式）

    Returns:
        tuple: 返回两个集合 (images_without_labels, labels_without_images)
               - images_without_labels: 有图片但无标签的文件名集合（不含扩展名）
               - labels_without_images: 有标签但无图片的文件名集合（不含扩展名）

    Raises:
        FileNotFoundError: 当指定的目录或images/labels文件夹不存在时

    Example:
        >>> # 基本用法：只检查不删除
        >>> missing_images, missing_labels = check_and_clean_dataset('./dataset')
        >>>
        >>> # 检查并删除不匹配的文件
        >>> check_and_clean_dataset('./dataset', delete=True)
        >>>
        >>> # 检查指定目录
        >>> check_and_clean_dataset('./fire-smoke/combined')
    """
    # 定义图片和标签文件夹路径
    images_dir = os.path.join(folder_name, 'images')
    labels_dir = os.path.join(folder_name, 'labels')

    # 确保文件夹存在
    if not os.path.exists(images_dir):
        raise FileNotFoundError(f"错误: images文件夹不存在于 {folder_name}")
    if not os.path.exists(labels_dir):
        raise FileNotFoundError(f"错误: labels文件夹不存在于 {folder_name}")

    print(f"🔍 开始检查数据集: {folder_name}")
    print(f"📁 图片目录: {images_dir}")
    print(f"📁 标签目录: {labels_dir}")

    # 获取所有图片和标签文件（不带扩展名）
    # 使用集合进行快速差集运算
    image_files = {os.path.splitext(f)[0] for f in os.listdir(images_dir)
                   if f.lower().endswith('.jpg')}
    label_files = {os.path.splitext(f)[0] for f in os.listdir(labels_dir)
                   if f.lower().endswith('.txt')}

    print(f"📊 统计信息:")
    print(f"   - 图片文件数量: {len(image_files)}")
    print(f"   - 标签文件数量: {len(label_files)}")

    # 找出不匹配的文件
    # 有图片但无标签的文件
    images_without_labels = image_files - label_files
    # 有标签但无图片的文件
    labels_without_images = label_files - image_files

    # 显示检查结果
    print("\n" + "="*50)
    print("📋 检查结果:")
    print("="*50)

    print(f"❌ 有图片但无标签的文件 ({len(images_without_labels)}个):")
    if images_without_labels:
        for file in sorted(images_without_labels):
            print(f"   - {file}.jpg")
    else:
        print("   ✅ 无此类文件")

    print(f"\n❌ 有标签但无图片的文件 ({len(labels_without_images)}个):")
    if labels_without_images:
        for file in sorted(labels_without_images):
            print(f"   - {file}.txt")
    else:
        print("   ✅ 无此类文件")

    # 如果需要删除文件
    if delete and (images_without_labels or labels_without_images):
        print("\n🗑️ 开始删除不匹配的文件...")
        deleted_count = 0

        # 删除无标签的图片文件
        for file in images_without_labels:
            img_path = os.path.join(images_dir, f"{file}.jpg")
            try:
                os.remove(img_path)
                print(f"   ✅ 已删除图片: {file}.jpg")
                deleted_count += 1
            except Exception as e:
                print(f"   ❌ 删除失败 {file}.jpg: {e}")

        # 删除无图片的标签文件
        for file in labels_without_images:
            label_path = os.path.join(labels_dir, f"{file}.txt")
            try:
                os.remove(label_path)
                print(f"   ✅ 已删除标签: {file}.txt")
                deleted_count += 1
            except Exception as e:
                print(f"   ❌ 删除失败 {file}.txt: {e}")

        print(f"\n✨ 删除完成! 总共删除了 {deleted_count} 个不匹配的文件")

    elif delete:
        print("\nℹ️ 无需删除：没有发现不匹配的文件")

    else:
        if images_without_labels or labels_without_images:
            print(f"\n💡 提示: 发现 {len(images_without_labels) + len(labels_without_images)} 个不匹配的文件")
            print("   如需删除这些文件，请设置 delete=True")
        else:
            print("\n🎉 完美! 所有图片和标签文件都匹配!")

    return images_without_labels, labels_without_images


def main():
    """
    命令行入口函数
    """
    parser = argparse.ArgumentParser(
        description='检查并清理不匹配的图像和标签文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  python checkmatches.py ./dataset              # 只检查不删除
  python checkmatches.py ./dataset --delete     # 检查并删除不匹配文件
  python checkmatches.py ./fire-smoke/combined  # 检查特定目录
        '''
    )
    parser.add_argument('folder', help='包含images和labels文件夹的目录路径')
    parser.add_argument('--delete', action='store_true',
                       help='是否直接删除不匹配的文件（谨慎使用）')

    args = parser.parse_args()

    try:
        check_and_clean_dataset(args.folder, args.delete)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return 1

    return 0


if __name__ == "__main__":
    # 直接运行时的测试用例
    path = './fire-smoke/combined'

    try:
        # 只检查不删除
        print("测试模式：只检查不删除")
        missing_images, missing_labels = check_and_clean_dataset(path, delete=False)

        # 如果需要测试删除功能，取消下面的注释
        # print("\n" + "="*60)
        # print("测试模式：检查并删除")
        # check_and_clean_dataset(path, delete=True)

    except FileNotFoundError as e:
        print(f"❌ 目录不存在: {e}")
    except Exception as e:
        print(f"❌ 执行过程中发生错误: {e}")